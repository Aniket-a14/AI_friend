import asyncio
from typing import Optional
import logging
import time
import sys
import random
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import Config
from app.audio import AudioStream, AudioPlayer
from app.wake_word import WakeWordDetector
from app.vad import VAD
from app.whisper_stt_service import WhisperSTTService
from app.llm import LLMService
from app.tts import TTSService
from app.state_manager import StateManager, AppState
from app.conversation_history_store import ConversationHistoryStore
from fastapi import WebSocket, WebSocketDisconnect

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AIBackend:
    def __init__(self):
        self.state_manager = StateManager()
        self.audio_stream = AudioStream()
        self.audio_player = AudioPlayer()
        self.wake_word = WakeWordDetector()
        self.vad = VAD()
        
        # Defer heavy loading
        self.stt = WhisperSTTService()
        self.llm = LLMService()
        self.tts = TTSService()
        self.db = ConversationHistoryStore()
        
        self.last_speech_time = time.time()
        self.silence_timeout = 30.0
        self.running = True
        self.active_websocket: Optional[WebSocket] = None
        self.is_ready = False
        self.active_response_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Asynchronous initialization of services."""
        logger.info("Initializing AI Backend services...")
        try:
            Config.validate()
        except ValueError as e:
            logger.error(e)
            sys.exit(1)

        try:
            await self.db.initialize()
            await self.llm.reload_context(self.db)
            # Start model loading in the background so the server is "up" quickly
            asyncio.create_task(self.stt.load_model())
            self.is_ready = True
            logger.info("AI Backend services initialized (STT loading in background).")
        except Exception as e:
            logger.error(f"Failed to initialize AI Backend: {e}")

    async def run(self):
        logger.info("Starting AI Friend Backend Loop...")
        
        # Update AudioStream with the current running loop
        self.audio_stream.loop = asyncio.get_running_loop()
        self.audio_stream.start()
        
        try:
            while self.running:
                # 1. Read Audio (Now Async)
                frame = await self.audio_stream.get_frame()
                if not frame:
                    continue # asyncio.Queue.get() will block anyway, so no need for sleep here

                current_state = self.state_manager.state

                # 2. Global STT & Interruption logic (whenever awake)
                if current_state != AppState.IDLE:
                    result = self.stt.process_frame(frame)
                    if result:
                        text, is_final = result
                        if is_final:
                            self.last_speech_time = time.time()
                            # If we were already thinking or speaking, this is a barge-in/interruption
                            if self.active_response_task and not self.active_response_task.done():
                                logger.info("Barge-in detected! Canceling current response.")
                                self.active_response_task.cancel()
                                if self.active_websocket:
                                    await self.active_websocket.send_json({"type": "stop"})
                            
                            # Start new response as a background task
                            self.active_response_task = asyncio.create_task(self.process_user_input(text))
                    
                    # Session Timeout Check (prevent timeout during AI speech)
                    if not self.stt.is_speaking and current_state != AppState.SPEAKING and current_state != AppState.THINKING:
                        if time.time() - self.last_speech_time > self.silence_timeout:
                            logger.info("Silence timeout. Ending session.")
                            await self.end_session()
                            continue

                # 3. State-Specific logic
                if current_state == AppState.IDLE:
                    # Wake Word Detection
                    if self.wake_word.process(frame):
                        self.state_manager.wake_detected()
                        self.last_speech_time = time.time()
                        logger.info("Wake word detected! Starting Session...")
                        await self.db.start_session()
                        await self.handle_wake_greeting()

                elif current_state == AppState.ACTIVE_SESSION:
                    pass

                elif current_state == AppState.THINKING:
                    pass

                elif current_state == AppState.SPEAKING:
                    pass

                await asyncio.sleep(0.001)

        except Exception as e:
            logger.error(f"Error in backend loop: {e}")
        finally:
            logger.info("Backend loop stopped.")
            await self.cleanup()

    async def end_session(self):
        """Ends the current session, reflects on growth, and resets state."""
        # 1. Reflect and learn from this session (Human Growth)
        await self.llm.reflect_on_session(self.db)
        
        # 2. Cleanup session
        self.stt.stop()
        self.state_manager.session_end()
        self.llm.clear_memory()
        await self.db.end_session()
        logger.info(f"Session ended. {Config.AI_NAME} has evolved and is now IDLE.")

    async def handle_wake_greeting(self):
        """Generates and plays a greeting on wake word detection"""
        logger.info("Generating greeting...")
        raw_greeting = await self.llm.generate_greeting()
        # Strip hidden reasoning
        greeting_text = raw_greeting.split("</emotion_thought>")[-1].strip()
        
        logger.info(f"{Config.AI_NAME} Greeting: {greeting_text}")
        self.llm.add_to_memory("assistant", greeting_text)
        await self.db.log_message("assistant", greeting_text)

        # TTS & Playback
        self.state_manager.start_speaking()
        # self.stt.stop() # REMOVED: Keep STT active for Barge-in support
        
        audio_stream = self.tts.stream_audio(greeting_text)
        if audio_stream:
            if self.active_websocket:
                # Stream to WebSocket (Web/Mobile)
                for chunk in audio_stream:
                    if chunk:
                        await self.active_websocket.send_bytes(chunk)
            else:
                # Play locally (Desktop only if PyAudio available)
                await asyncio.to_thread(self.audio_player.play_stream, audio_stream)
        
        self.state_manager.finish_speaking()
        self.stt.start() # Start listening for user response
        self.last_speech_time = time.time()

    async def process_user_input(self, text):
        """Called when STT returns final text. Uses streaming for low latency."""
        logger.info(f"User said: {text}")
        
        if not text.strip():
            return
        
        # Check stop commands
        if text.lower().strip() in ["bye", "stop", "goodnight", "you can rest now", "end", "shutdown"]:
            await self.handle_stop_command(text)
            return

        self.llm.add_to_memory("user", text)
        await self.db.log_message("user", text)
        
        # Set state to THINKING
        self.state_manager.start_thinking()
        
        # HUMAN NATURE: Simulated Thinking Latency
        # Humans take longer to process deep/long thoughts
        base_delay = 0.4 # Minimum human reaction
        complexity_delay = min(2.5, len(text) / 50.0) # More text = more "thought"
        total_delay = base_delay + (complexity_delay * random.uniform(0.5, 1.5))
        logger.debug(f"Simulating human thought delay: {total_delay:.2f}s")
        await asyncio.sleep(total_delay)

        full_response = ""
        sentence_buffer = ""
        sentence_end_chars = [".", "?", "!", "\n"]
        in_reasoning = False

        try:
            # 1. Stream from LLM
            async for token in self.llm.generate_response_stream(text):
                full_response += token
                
                # Check for reasoning block tags
                if "<emotion_thought>" in full_response and not in_reasoning:
                    in_reasoning = True
                    continue
                
                if "</emotion_thought>" in full_response and in_reasoning:
                    in_reasoning = False
                    # Extract only the content AFTER the reasoning block
                    full_response = full_response.split("</emotion_thought>")[-1]
                    sentence_buffer = full_response
                    continue

                if in_reasoning:
                    continue

                sentence_buffer += token

                # 2. If we have a complete sentence, stream it to TTS
                if any(char in sentence_buffer for char in sentence_end_chars) and len(sentence_buffer.strip()) > 30:
                    if self.state_manager.state == AppState.THINKING:
                        self.state_manager.start_speaking()

                    await self._stream_sentence_to_voice(sentence_buffer.strip())
                    sentence_buffer = ""

            # 3. Stream any remaining text
            if sentence_buffer.strip() and not in_reasoning:
                if self.state_manager.state == AppState.THINKING:
                    self.state_manager.start_speaking()
                    # self.stt.stop() # REMOVED: Keep STT active for Barge-in support
                await self._stream_sentence_to_voice(sentence_buffer.strip())

            # Log final response (cleaned)
            final_clean = full_response.split("</emotion_thought>")[-1].strip()
            self.llm.add_to_memory("assistant", final_clean)
            await self.db.log_message("assistant", final_clean)
            logger.info(f"AI full response: {final_clean}")

        except asyncio.CancelledError:
            logger.info("Response task cancelled (Barge-in).")
            raise # Re-raise to let the task system handle it
        except Exception as e:
            logger.error(f"Error in streaming response: {e}")
        finally:
            self.state_manager.finish_speaking()
            self.stt.start() # Resume listening
            self.last_speech_time = time.time() # Reset silence timer

    async def _stream_sentence_to_voice(self, sentence):
        """Helper to stream a single sentence to the active output."""
        # Extra safety: strip any lingering tags if the logic missed them
        clean_sentence = sentence.split("</emotion_thought>")[-1].strip()
        if not clean_sentence:
            return

        logger.debug(f"Pipelining sentence to TTS: {clean_sentence}")
        audio_stream = self.tts.stream_audio(clean_sentence)
        if audio_stream:
            if self.active_websocket:
                for chunk in audio_stream:
                    if chunk:
                        await self.active_websocket.send_bytes(chunk)
            else:
                await asyncio.to_thread(self.audio_player.play_stream, audio_stream)

    async def handle_stop_command(self, text):
        logger.info("Generating farewell...")
        self.state_manager.start_thinking()
        raw_farewell = await self.llm.generate_farewell(text)
        # Strip hidden reasoning
        response_text = raw_farewell.split("</emotion_thought>")[-1].strip()
        
        logger.info(f"AI Farewell: {response_text}")
        await self.db.log_message("assistant", response_text)
        
        self.state_manager.start_speaking()
        self.stt.stop()
        audio_stream = self.tts.stream_audio(response_text)
        if audio_stream:
            if self.active_websocket:
                for chunk in audio_stream:
                    if chunk:
                        await self.active_websocket.send_bytes(chunk)
            else:
                await asyncio.to_thread(self.audio_player.play_stream, audio_stream)
        await self.end_session()

    async def cleanup(self):
        await self.db.close()
        self.audio_stream.close()
        self.audio_player.close()
        self.wake_word.delete()
        self.stt.stop()

    async def start_manual_session(self):
        """Manually starts a session (e.g. from API)"""
        if self.state_manager.state == AppState.IDLE:
            self.state_manager.wake_detected()
            self.last_speech_time = time.time()
            # We need to schedule the greeting, but we can't await here easily if called from sync context
            # But since this will be called from async API handler, we can return a coroutine or just let the loop handle it?
            # Actually, handle_wake_greeting is async.
            # Better approach: Just set state, and let the loop or a separate task handle the greeting.
            # But handle_wake_greeting is not called in the loop for ACTIVE_SESSION.
            # So we should return the coroutine to be awaited by the caller.
            await self.handle_wake_greeting()
        return None

# Global backend instance
backend = AIBackend()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await backend.initialize()
    loop_task = asyncio.create_task(backend.run())
    yield
    # Shutdown
    backend.running = False
    await backend.cleanup() # Using cleanup method
    await loop_task

app = FastAPI(title=f"{Config.AI_NAME} Backend", lifespan=lifespan)

# CORS Setup - Hardened for Production
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

@app.get("/status")
async def get_status():
    if not backend.is_ready or backend.stt.is_loading:
        return {"state": "loading"}
    
    # Map AppState to frontend expected strings
    state_map = {
        AppState.IDLE: "idle",
        AppState.ACTIVE_SESSION: "listening",
        AppState.THINKING: "thinking",
        AppState.SPEAKING: "speaking"
    }
    return {"state": state_map.get(backend.state_manager.state, "idle")}

@app.post("/start-session")
async def start_session(background_tasks: BackgroundTasks):
    if not backend.is_ready or backend.stt.is_loading:
        return {"status": "loading_models", "message": "Please wait, AI is still waking up..."}

    if backend.state_manager.state == AppState.IDLE:
        # Trigger greeting in background
        background_tasks.add_task(backend.start_manual_session)
        return {"status": "started"}
    return {"status": "already_active"}

@app.websocket("/ws/audio")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected via WebSocket.")
    backend.active_websocket = websocket
    
    try:
        while True:
            # Receive binary audio data (PCM 16k mono)
            data = await websocket.receive_bytes()
            if data:
                # Inject frame into the AI logic
                await backend.audio_stream.put_frame(data)
    except WebSocketDisconnect:
        logger.info("Client disconnected from WebSocket.")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        backend.active_websocket = None

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
