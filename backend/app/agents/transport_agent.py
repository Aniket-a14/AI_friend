import asyncio
import base64
import logging
import time

from livekit import rtc
from livekit.api import AccessToken, VideoGrants

from ..config import Config
from .base import BaseAgent

logger = logging.getLogger("transport_agent")


class TransportAgent(BaseAgent):
    """
    Bridges NATS Events to WebRTC Tracks (LiveKit).
    Inherits from BaseAgent for consistent mesh connectivity.
    """

    def __init__(
        self,
        nats_url: str = Config.NATS_URL,
        lk_url: str = Config.LIVEKIT_URL,
        lk_api_key: str = Config.LIVEKIT_API_KEY,
        lk_api_secret: str = Config.LIVEKIT_API_SECRET,
    ):
        super().__init__(name="transport_agent", nats_url=nats_url)
        self.lk_url = lk_url
        self.lk_api_key = lk_api_key
        self.lk_api_secret = lk_api_secret
        self.output_sample_rate = Config.SAMPLE_RATE
        self.output_channels = 1

        self.room = rtc.Room()

        # Match the voice agent's PCM output contract.
        self.audio_source = rtc.AudioSource(
            self.output_sample_rate,
            self.output_channels,
        )
        self.audio_track = rtc.LocalAudioTrack.create_audio_track(
            "ai-voice", self.audio_source
        )
        self.audio_queue = asyncio.Queue(
            maxsize=max(32, int(getattr(Config, "TRANSPORT_AUDIO_QUEUE_SIZE", 256)))
        )
        self.audio_worker_task = None
        self.dropped_audio_frames = 0

    async def _connect_livekit_with_retry(self, token: str):
        """Connect to LiveKit with bounded retries for transient SFU startup gaps."""
        max_attempts = 8
        for attempt in range(1, max_attempts + 1):
            try:
                await self.room.connect(self.lk_url, token)
                logger.info("Connected to LiveKit Room: ai-friend-room")
                return
            except Exception as e:
                if attempt == max_attempts:
                    raise

                delay = min(10.0, 1.5 * attempt)
                logger.warning(
                    "LiveKit connection failed (attempt %s/%s): %s. Retrying in %.1fs",
                    attempt,
                    max_attempts,
                    e,
                    delay,
                )
                await asyncio.sleep(delay)

    async def start(self):
        """Initialize NATS and connect to LiveKit"""
        await self.connect()

        # 1. Connect to LiveKit Room
        token = (
            AccessToken(self.lk_api_key, self.lk_api_secret)
            .with_identity("transport-agent")
            .with_name("AI Bridge")
            .with_grants(VideoGrants(room_join=True, room="ai-friend-room"))
            .to_jwt()
        )

        await self._connect_livekit_with_retry(token)

        # 2. Publish Audio Track
        publication = await self.room.local_participant.publish_track(self.audio_track)
        logger.info(f"Published Audio Track: {publication.sid}")

        # Capture frames on a dedicated worker so NATS callback can return fast.
        self.audio_worker_task = asyncio.create_task(self._audio_playback_worker())

        # 3. Subscribe to NATS Audio Stream (Outbound - AI Speech)
        await self.subscribe(
            "audio.stream",
            callback=self._on_nats_audio,
            durable=f"{self.name}_audio_stream_live",
            deliver_policy="new",
            pending_msgs_limit=200000,
            pending_bytes_limit=268435456,
        )
        logger.info("Subscribed to NATS audio.stream. Outbound Bridge Active.")

        # 4. Listen for Remote Tracks (Inbound - User Speech)
        self.room.on("track_subscribed", self._on_track_subscribed)
        logger.info("Listening for remote tracks (Inbound Bridge enabled).")

    def _on_track_subscribed(
        self,
        track: rtc.Track,
        publication: rtc.TrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info(
                f"Subscribed to remote audio track: {track.sid} from {participant.identity}"
            )
            asyncio.create_task(self._process_remote_audio(track))

    async def _process_remote_audio(self, track: rtc.RemoteAudioTrack):
        """Convert WebRTC audio frames to NATS events for STT"""
        audio_stream = rtc.AudioStream(track)
        async for event in audio_stream:
            frame = event.frame
            audio_data = bytes(frame.data)
            metadata = {
                "sample_rate": frame.sample_rate,
                "channels": frame.num_channels,
                "participant": track.sid,
                "captured_at": time.time(),
            }
            # Publish raw PCM to the binary mesh path. STT still accepts the
            # legacy JSON/base64 shape for compatibility.
            await self.publish("audio.inbound", audio_data, metadata=metadata)

    async def _on_nats_audio(self, data, metadata: dict | None = None):
        """Convert NATS audio events to WebRTC frames for User."""
        try:
            audio_bytes = b""
            sample_rate = self.output_sample_rate
            num_channels = self.output_channels
            is_done = False

            if isinstance(data, (bytes, bytearray)):
                audio_bytes = bytes(data)
            elif isinstance(data, dict):
                audio_b64 = data.get("audio", "")
                is_done = data.get("done", False)
                sample_rate = data.get("sample_rate", sample_rate)
                num_channels = data.get("channels", num_channels)
                if audio_b64:
                    audio_bytes = base64.b64decode(audio_b64)
            else:
                logger.warning(
                    "Unsupported audio payload type from NATS: %s",
                    type(data).__name__,
                )
                return

            if audio_bytes:
                # Strip WAV header if present (44 bytes)
                if audio_bytes.startswith(b"RIFF"):
                    pcm_data = audio_bytes[44:]
                else:
                    pcm_data = audio_bytes

                if pcm_data:
                    try:
                        self.audio_queue.put_nowait(
                            (pcm_data, sample_rate, num_channels)
                        )
                    except asyncio.QueueFull:
                        # Drop the oldest frame to keep playout near real-time.
                        try:
                            _ = self.audio_queue.get_nowait()
                            self.audio_queue.task_done()
                        except asyncio.QueueEmpty:
                            pass

                        try:
                            self.audio_queue.put_nowait(
                                (pcm_data, sample_rate, num_channels)
                            )
                        except asyncio.QueueFull:
                            pass

                        self.dropped_audio_frames += 1
                        if self.dropped_audio_frames % 50 == 1:
                            logger.warning(
                                "Transport audio queue overloaded; dropped %s frames.",
                                self.dropped_audio_frames,
                            )

            if is_done:
                logger.info("AI Utterance stream complete.")

        except Exception as e:
            logger.error(f"Error bridging audio: {e}")

    async def _audio_playback_worker(self):
        """Drain queued PCM frames and push to LiveKit at sink pace."""
        while True:
            try:
                pcm_data, sample_rate, num_channels = await self.audio_queue.get()
                try:
                    if not pcm_data or num_channels <= 0:
                        continue

                    samples_per_channel = len(pcm_data) // (2 * num_channels)
                    if samples_per_channel <= 0:
                        continue

                    frame = rtc.AudioFrame(
                        data=pcm_data,
                        sample_rate=sample_rate,
                        num_channels=num_channels,
                        samples_per_channel=samples_per_channel,
                    )
                    await self.audio_source.capture_frame(frame)
                finally:
                    self.audio_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Transport playback worker error: {e}")
                await asyncio.sleep(0.01)

    async def stop(self):
        if self.audio_worker_task:
            self.audio_worker_task.cancel()
            try:
                await self.audio_worker_task
            except asyncio.CancelledError:
                pass
        await self.room.disconnect()
        await super().stop()
        logger.info("Transport Agent Stopped.")


async def main():
    agent = TransportAgent()
    try:
        await agent.start()
        shutdown_trigger = asyncio.Event()
        await shutdown_trigger.wait()
    except KeyboardInterrupt:
        await agent.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
