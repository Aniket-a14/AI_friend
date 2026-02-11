import asyncio
import logging
from google import genai
from google.genai import types
from .config import Config

logger = logging.getLogger(__name__)

class GeminiLiveClient:
    def __init__(self):
        self.api_key = Config.GEMINI_API_KEY
        self.model = "gemini-2.5-flash-native-audio-latest" 
        self.client = genai.Client(api_key=self.api_key, http_options={'api_version': 'v1beta'})
        self.session = None
        self._session_lock = asyncio.Lock()
        self.running = False
        self.ready_event = asyncio.Event() 
        self.config = None
        
    def set_config(self, personality_prompt, voice_name="Puck", tools=None):
        """Sets the initial session configuration using explicit SDK types."""
        self.config = types.LiveConnectConfig(
            system_instruction=personality_prompt,
            generation_config=types.GenerationConfig(
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_name
                        )
                    )
                )
            ),
            response_modalities=["AUDIO"]
        )
        if tools:
            self.config.tools = tools

    async def connect(self):
        return True

    async def start_session(self):
        """The main loop that starts the SDK session and manages I/O."""
        self.ready_event.clear()
        try:
            async with self.client.aio.live.connect(model=self.model, config=self.config) as session:
                async with self._session_lock:
                    self.session = session
                    self.running = True
                
                logger.info(f"🧠 [Gemini Live] Session Established: {self.model}")
                self.ready_event.set()

                async for message in session.receive():
                    yield message
                    
        except Exception as e:
            logger.error(f"Gemini Live Session Error: {e}")
        finally:
            async with self._session_lock:
                self.running = False
                self.session = None
                self.ready_event.clear()
            logger.info("Gemini Live Session Closed.")

    async def send_audio(self, audio_chunk):
        """Sends raw PCM audio to Gemini."""
        if not self.running or not self.session:
            return

        async with self._session_lock:
            try:
                # Use simplified dictionary format verified in 2025/2026 SDKs
                await self.session.send(
                    input={"data": audio_chunk, "mime_type": "audio/pcm"},
                    end_of_turn=False
                )
            except Exception as e:
                if "1000" not in str(e):
                    logger.error(f"Error sending audio: {e}")
                self.running = False

    async def send_video(self, jpeg_bytes):
        """Sends JPEG image data to Gemini."""
        if not self.running or not self.session:
            return

        async with self._session_lock:
            try:
                await self.session.send(
                    input={"data": jpeg_bytes, "mime_type": "image/jpeg"},
                    end_of_turn=False
                )
            except Exception as e:
                if "1000" not in str(e):
                    logger.error(f"Error sending video: {e}")
                self.running = False

    async def send_text(self, text):
        """Sends text input to Gemini."""
        if not self.running or not self.session:
            return

        async with self._session_lock:
            try:
                await self.session.send(input=text, end_of_turn=True)
            except Exception as e:
                logger.error(f"Error sending text: {e}")

    async def send_tool_response(self, responses):
        """Sends tool execution results back to Gemini."""
        if not self.running or not self.session:
            return

        async with self._session_lock:
            try:
                tool_responses = [
                    types.LiveClientToolResponse(
                        function_responses=[
                            types.FunctionResponse(name=r["name"], response=r["response"])
                            for r in responses
                        ]
                    )
                ]
                await self.session.send(input=tool_responses, end_of_turn=False)
            except Exception as e:
                logger.error(f"Error sending tool response: {e}")

    async def close(self):
        async with self._session_lock:
            self.running = False
            self.session = None
            self.ready_event.clear()
