import asyncio
from typing import Optional
import logging
import time
import sys
import random
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import Config
from app.audio import AudioStream, AudioPlayer
from app.state_manager import StateManager, AppState
from app.conversation_history_store import ConversationHistoryStore
from fastapi import WebSocket, WebSocketDisconnect
from app.gemini_live import GeminiLiveClient
from app.vision import ScreenLink, CameraLink
from app.tools import ToolRegistry
from app.autonomy import AutonomyEngine
from app.llm import LLMService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AIBackend:
    def __init__(self):
        self.state_manager = StateManager()
        self.audio_stream = AudioStream()
        self.audio_player = AudioPlayer()
        
        # New Brain: Gemini Live + Vision + Tools
        self.gemini_client = GeminiLiveClient()
        self.screen_link = ScreenLink()
        self.camera_link = CameraLink()
        self.vision_source = "screen" # screen | camera
        
        self.tool_registry = ToolRegistry()
        self.db = ConversationHistoryStore()
        
        self.memory_store = None
        self.llm = None 
        self.autonomy = None
        
        self.running = True
        self.active_websocket: Optional[WebSocket] = None
        self.is_ready = False
        
        # Tasks
        self.send_audio_task: Optional[asyncio.Task] = None
        self.receive_audio_task: Optional[asyncio.Task] = None
        self.send_video_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Asynchronous initialization of services."""
        logger.info("Initializing AI Backend (Gemini Live + Vision + Agency Mode)...")
        try:
            Config.validate()
        except ValueError as e:
            logger.error(e)
            sys.exit(1)

        try:
            await self.db.initialize()
            
            from app.memory_store import MemoryStore
            self.memory_store = MemoryStore(self.db.pool)
            self.tool_registry.set_memory_store(self.memory_store)
            
            self.llm = LLMService(memory_store=self.memory_store)
            
            loop = asyncio.get_running_loop()
            self.autonomy = AutonomyEngine(
                self.llm,
                self.db,
                loop=loop,
                interaction_callback=self.trigger_proactive_interaction
            )

            persona = self.llm.get_live_system_instruction()
            
            self.gemini_client.set_config(
                personality_prompt=persona,
                tools=self.tool_registry.definitions
            )
            
            self.is_ready = True
            logger.info("AI Backend services initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize AI Backend: {e}")

    async def trigger_proactive_interaction(self, context_type="bored"):
        """Called by AutonomyEngine. Sends a prompt to Gemini to speak."""
        logger.info(f"🤖 Autonomy Triggered: {context_type}")
        
        if not self.gemini_client.running:
            logger.info("Gemini not connected, cannot be proactive.")
            return

        prompt = f"""
        [SYSTEM EVENT: PROACTIVE INTERACTION]
        Your 'Life Simulator' indicates you are feeling {context_type}.
        Please initiate a conversation with the user based on this feeling.
        Do not acknowledge this system message. Just speak to the user.
        """
        await self.gemini_client.send_text(prompt)

    async def run(self):
        logger.info("Starting AI Friend Backend Loop...")
        self.running = True
        
        if self.autonomy:
            self.autonomy.start()

        try:
            self.audio_stream.loop = asyncio.get_running_loop()
            self.audio_stream.start()
        except Exception as e:
            logger.error(f"Error starting audio stream: {e}")
        
        conn_status = await self.gemini_client.connect()
        if not conn_status:
            logger.error("Failed to connect to Gemini Live client.")
            return

        self.send_audio_task = asyncio.create_task(self._send_audio_loop())
        self.receive_audio_task = asyncio.create_task(self._receive_audio_loop())
        self.send_video_task = asyncio.create_task(self._send_video_loop())
        
        logger.info("AI Friend Backend Loop Running.")
        
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Main loop cancelled.")
        finally:
            await self.cleanup()

    async def cleanup(self):
        self.running = False
        if self.autonomy:
            self.autonomy.stop()
        await self.gemini_client.close()
        await self.db.close()
        self.audio_stream.close()
        self.audio_player.close()
        self.camera_link.close()
        if self.send_audio_task: self.send_audio_task.cancel()
        if self.receive_audio_task: self.receive_audio_task.cancel()
        if self.send_video_task: self.send_video_task.cancel()

    async def _send_audio_loop(self):
        logger.info("🎤 Audio Upload Loop Started")
        try:
            await self.gemini_client.ready_event.wait()
            while self.running:
                chunk = await self.audio_stream.get_frame()
                if chunk:
                    await self.gemini_client.send_audio(chunk)
        except Exception as e:
            logger.error(f"Error in audio upload loop: {e}")

    async def _send_video_loop(self):
        logger.info("📸 Video Upload Loop Started")
        try:
            await self.gemini_client.ready_event.wait()
            while self.running:
                # Select source based on vision_source flag
                if self.vision_source == "camera":
                    frame = self.camera_link.capture_frame()
                else:
                    frame = self.screen_link.capture_frame()

                if frame:
                    # Re-enabling vision with safety cap
                    await self.gemini_client.send_video(frame)
                await asyncio.sleep(1.0) # 1 FPS for efficiency
        except Exception as e:
            logger.error(f"Error in video upload loop: {e}")

    async def _receive_audio_loop(self):
        """Main interaction loop with Gemini Live SDK."""
        logger.info("🔊 Gemini Live Session Loop Started")
        while self.running:
            try:
                async for message in self.gemini_client.start_session():
                    if not self.running:
                        break
                    
                    # 1. Handle Audio Content (Binary message from session.receive)
                    server_content = getattr(message, 'server_content', None)
                    if server_content and server_content.model_turn:
                        parts = server_content.model_turn.parts
                        for part in parts:
                            if part.inline_data:
                                audio_data = part.inline_data.data
                                
                                # Play locally (Async/Non-blocking)
                                asyncio.create_task(self.audio_player.play_chunk(audio_data))
                                
                                # Send to Frontend WS
                                if self.active_websocket:
                                    await self.active_websocket.send_bytes(audio_data)

                    # 2. Handle Tool Calls
                    tool_call = getattr(message, 'tool_call', None)
                    if tool_call:
                        tool_calls = tool_call.function_calls
                        responses = []
                        
                        for call in tool_calls:
                            fname = call.name
                            fargs = call.args
                            call_id = getattr(call, "id", "")
                            logger.info(f"AI Tool Call: {fname}({fargs})")
                            
                            # Execute Tool
                            result = await self.tool_registry.execute(fname, fargs)
                            
                            responses.append({
                                "name": fname,
                                "id": call_id,
                                "response": {"result": result}
                            })
                        
                        # Send results back to Gemini
                        await self.gemini_client.send_tool_response(responses)
                
                if self.running:
                    logger.warning("Gemini session ended. Restarting in 3s...")
                    await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Error in Gemini session loop: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(5)

# Global backend instance
backend = AIBackend()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await backend.initialize()
    loop_task = asyncio.create_task(backend.run())
    yield
    backend.running = False
    await backend.cleanup()
    await loop_task

app = FastAPI(title=f"{Config.AI_NAME} Backend", lifespan=lifespan)

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
    if not backend.is_ready:
        return {"state": "loading"}
    return {"state": "ready"}

@app.post("/start-session")
async def start_session():
    """Dummy endpoint for frontend compatibility."""
    return {"status": "success"}

@app.post("/vision/toggle")
async def toggle_vision(source: str):
    """source: 'screen' or 'camera'"""
    if source not in ["screen", "camera"]:
        return {"error": "Invalid source"}
    
    backend.vision_source = source
    logger.info(f"Vision source switched to: {source}")
    return {"status": "success", "source": source, "current": backend.vision_source}

@app.websocket("/ws/audio")
async def websocket_endpoint(websocket: WebSocket):
    if backend.active_websocket:
        # Silent handoff: replace older socket if exists
        try:
            await backend.active_websocket.close()
        except:
            pass
            
    await websocket.accept()
    logger.info("Client connected via WebSocket.")
    backend.active_websocket = websocket
    try:
        while True:
            data = await websocket.receive_bytes()
            if data:
                await backend.audio_stream.put_frame(data)
    except WebSocketDisconnect:
        logger.info("Client disconnected.")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Only clear if we are still the active reference
        if backend.active_websocket == websocket:
            backend.active_websocket = None

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
