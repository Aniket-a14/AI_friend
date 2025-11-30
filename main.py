import asyncio
import logging
import time
import sys
from app.config import Config
from app.audio import AudioStream, AudioPlayer
from app.wake_word import WakeWordDetector
from app.vad import VAD
from app.whisper_stt_service import WhisperSTTService
from app.llm import LLMService
from app.tts import TTSService
from app.state_manager import StateManager, AppState

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AIBackend:
    def __init__(self):
        try:
            Config.validate()
        except ValueError as e:
            logger.error(e)
            sys.exit(1)

        self.state_manager = StateManager()
        self.audio_stream = AudioStream()
        self.audio_player = AudioPlayer()
        self.wake_word = WakeWordDetector()
        self.vad = VAD() 
        
        self.stt = WhisperSTTService()
        self.llm = LLMService()
        self.tts = TTSService()
        
        self.last_speech_time = time.time()
        self.silence_timeout = 5.0 # seconds
        self.running = True

    async def run(self):
        logger.info("Starting AI Friend Backend...")
        self.audio_stream.start()
        
        try:
            while self.running:
                # 1. Read Audio
                frame = self.audio_stream.get_frame()
                if not frame:
                    await asyncio.sleep(0.01)
                    continue

                current_state = self.state_manager.state

                # 2. State Machine
                if current_state == AppState.IDLE:
                    # Wake Word Detection
                    if self.wake_word.process(frame):
                        self.state_manager.wake_detected()
                        self.last_speech_time = time.time()
                        logger.info("Wake word detected! Starting Session...")
                        await self.handle_wake_greeting()

                elif current_state == AppState.ACTIVE_SESSION:
                    # Feed audio to Whisper STT
                    # It handles VAD and buffering internally
                    result = self.stt.process_frame(frame)
                    
                    if result:
                        text, is_final = result
                        if is_final:
                            self.last_speech_time = time.time()
                            await self.process_user_input(text)
                    
                    # Check overall session silence timeout
                    # We can check if STT is speaking (buffering)
                    if not self.stt.is_speaking and (time.time() - self.last_speech_time > self.silence_timeout):
                        logger.info("Silence timeout. Ending session.")
                        await self.end_session()
                        continue

                elif current_state == AppState.SPEAKING:
                    # While speaking, we pause STT or just ignore input
                    pass

                await asyncio.sleep(0.001)

        except KeyboardInterrupt:
            logger.info("Stopping...")
        finally:
            self.running = False
            await self.cleanup()

    async def end_session(self):
        """Ends the current session, stops STT, and resets state."""
        self.stt.stop()
        self.state_manager.session_end()
        self.llm.clear_memory()
        logger.info("Session ended. IDLE.")

    async def handle_wake_greeting(self):
        """Generates and plays a greeting on wake word detection"""
        logger.info("Generating greeting...")
        greeting_text = await self.llm.generate_greeting()
        logger.info(f"AI Greeting: {greeting_text}")
        self.llm.add_to_memory("assistant", greeting_text)

        # TTS & Playback
        self.state_manager.start_speaking()
        self.stt.stop() # Ensure STT is stopped while speaking
        
        audio_stream = self.tts.stream_audio(greeting_text)
        if audio_stream:
            await asyncio.to_thread(self.audio_player.play_stream, audio_stream)
        
        self.state_manager.finish_speaking()
        self.stt.start() # Start listening for user response
        self.last_speech_time = time.time()

    async def process_user_input(self, text):
        """Called when STT returns final text"""
        logger.info(f"User said: {text}")
        
        if not text.strip():
            return

        # Check stop commands
        if text.lower().strip() in ["bye", "stop", "goodnight", "you can rest now", "end", "shutdown"]:
            await self.handle_stop_command(text)
            return

        self.llm.add_to_memory("user", text)
        
        # Generate Response
        response_text = await self.llm.generate_response(text)
        logger.info(f"AI says: {response_text}")
        self.llm.add_to_memory("assistant", response_text)

        # TTS & Playback
        self.state_manager.start_speaking()
        self.stt.stop() # Stop listening while speaking
        
        # We run playback in a separate thread to avoid blocking the asyncio loop completely
        audio_stream = self.tts.stream_audio(response_text)
        if audio_stream:
            await asyncio.to_thread(self.audio_player.play_stream, audio_stream)
        
        self.state_manager.finish_speaking()
        self.stt.start() # Resume listening
        self.last_speech_time = time.time() # Reset silence timer

    async def handle_stop_command(self, text):
        logger.info("Generating farewell...")
        response_text = await self.llm.generate_farewell(text)
        logger.info(f"AI Farewell: {response_text}")
        self.state_manager.start_speaking()
        self.stt.stop()
        audio_stream = self.tts.stream_audio(response_text)
        if audio_stream:
            await asyncio.to_thread(self.audio_player.play_stream, audio_stream)
        await self.end_session()

    async def cleanup(self):
        self.audio_stream.close()
        self.audio_player.close()
        self.wake_word.delete()
        self.stt.stop()

if __name__ == "__main__":
    backend = AIBackend()
    try:
        asyncio.run(backend.run())
    except KeyboardInterrupt:
        pass
