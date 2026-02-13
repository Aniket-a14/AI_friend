import json
import base64
import logging
import asyncio
from livekit import rtc
from livekit.api import AccessToken, VideoGrants
from typing import Dict, Any
from .base import BaseAgent

from ..config import Config

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
        lk_api_secret: str = Config.LIVEKIT_API_SECRET
    ):
        super().__init__(name="transport_agent", nats_url=nats_url)
        self.lk_url = lk_url
        self.lk_api_key = lk_api_key
        self.lk_api_secret = lk_api_secret
        
        self.room = rtc.Room()
        
        # Audio Source for WebRTC (GPT-SoVITS output usually: 22050Hz, 1 channel)
        self.audio_source = rtc.AudioSource(22050, 1)
        self.audio_track = rtc.LocalAudioTrack.create_audio_track("ai-voice", self.audio_source)

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
        
        await self.room.connect(self.lk_url, token)
        logger.info(f"Connected to LiveKit Room: ai-friend-room")

        # 2. Publish Audio Track
        publication = await self.room.local_participant.publish_track(self.audio_track)
        logger.info(f"Published Audio Track: {publication.sid}")

        # 3. Subscribe to NATS Audio Stream (Outbound - AI Speech)
        await self.subscribe(
            "audio.stream", 
            callback=self._on_nats_audio, 
            durable="transport_bridge",
            deliver_policy="new"
        )
        logger.info("Subscribed to NATS audio.stream. Outbound Bridge Active.")

        # 4. Listen for Remote Tracks (Inbound - User Speech)
        self.room.on("track_subscribed", self._on_track_subscribed)
        logger.info("Listening for remote tracks (Inbound Bridge enabled).")

    def _on_track_subscribed(self, track: rtc.Track, publication: rtc.TrackPublication, participant: rtc.RemoteParticipant):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info(f"Subscribed to remote audio track: {track.sid} from {participant.identity}")
            asyncio.create_task(self._process_remote_audio(track))

    async def _process_remote_audio(self, track: rtc.RemoteAudioTrack):
        """Convert WebRTC audio frames to NATS events for STT"""
        audio_stream = rtc.AudioStream(track)
        async for event in audio_stream:
            frame = event.frame
            audio_data = frame.data
            payload = {
                "audio": base64.b64encode(audio_data).decode('utf-8'),
                "sample_rate": frame.sample_rate,
                "channels": frame.num_channels,
                "participant": track.sid
            }
            # Publish to mesh
            await self.publish("audio.inbound", payload)

    async def _on_nats_audio(self, data: dict):
        """Convert NATS audio events to WebRTC frames for User"""
        try:
            audio_b64 = data.get("audio", "")
            is_done = data.get("done", False)

            if audio_b64:
                audio_bytes = base64.b64decode(audio_b64)
                
                # Strip WAV header if present (44 bytes)
                if audio_bytes.startswith(b'RIFF'):
                    pcm_data = audio_bytes[44:]
                else:
                    pcm_data = audio_bytes
                
                if pcm_data:
                    num_samples = len(pcm_data) // 2
                    frame = rtc.AudioFrame(
                        data=pcm_data,
                        sample_rate=22050,
                        num_channels=1,
                        samples_per_channel=num_samples
                    )
                    await self.audio_source.capture_frame(frame)

            if is_done:
                logger.info("AI Utterance stream complete.")
                
        except Exception as e:
            logger.error(f"Error bridging audio: {e}")

    async def stop(self):
        await self.room.disconnect()
        await super().stop()
        logger.info("Transport Agent Stopped.")

async def main():
    agent = TransportAgent()
    try:
        await agent.start()
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())
