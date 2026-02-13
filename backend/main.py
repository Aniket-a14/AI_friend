import logging
import json
import asyncio
import random
import uvicorn
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from livekit import api
import nats

from app.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ai_friend_backend")

class AIBackend:
    """
    Sovereign signaling server for the AI Friend Voice Mesh.
    Manages WebRTC tokens and broadcasts control signals via NATS.
    """
    def __init__(self):
        self.vision_source = "screen" # screen | camera
        self.is_ready = False
        self.nc = None

    async def initialize(self):
        """Minimal initialization for signaling server."""
        logger.info("Initializing Sovereign Signaling Backend...")
        try:
            # Check NATS connection
            self.nc = await nats.connect(Config.NATS_URL)
            logger.info(f"Connected to NATS at {Config.NATS_URL}")
            self.is_ready = True
        except Exception as e:
            logger.error(f"Failed to connect to NATS during init: {e}")
            # We don't crash here, but is_ready will stay False
        
        logger.info("Signaling server ready.")

    async def get_livekit_token(self, participant_name: str):
        """Generate a token for a user to join the mesh room."""
        token = (
            api.AccessToken(Config.LIVEKIT_API_KEY, Config.LIVEKIT_API_SECRET)
            .with_identity(participant_name)
            .with_name(participant_name)
            .with_grants(api.VideoGrants(room_join=True, room="ai-friend-room"))
        )
        return token.to_jwt()

    async def toggle_vision_source(self, source: str):
        """Broadcast vision source change to the mesh."""
        self.vision_source = source
        if self.nc:
            js = self.nc.jetstream()
            payload = {"action": "switch_source", "source": source}
            await js.publish("vision.control", json.dumps(payload).encode())
            logger.info(f"Broadcasted vision switch: {source}")
        else:
            logger.warning("NATS not connected, cannot broadcast vision switch")
        return {"status": "ok", "source": source}

    async def cleanup(self):
        """Close connections."""
        if self.nc:
            await self.nc.close()
            logger.info("NATS connection closed.")

backend = AIBackend()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await backend.initialize()
    yield
    # Shutdown
    await backend.cleanup()

app = FastAPI(
    title="AI Friend Sovereign Mesh",
    description="Signaling and Control Hub for the Agentic Voice Mesh",
    lifespan=lifespan
)

# CORS Middleware (Sovereign Local Access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "status": "online",
        "identity": "Sovereign Mesh Bridge",
        "ready": backend.is_ready
    }

@app.get("/status")
async def get_status():
    """Health check endpoint for Docker/K8s"""
    return {"status": "ok", "ready": backend.is_ready}

@app.get("/token")
async def get_token(participant: str = "user"):
    """LiveKit Token Endpoint"""
    try:
        token = await backend.get_livekit_token(participant)
        return {"token": token, "url": Config.LIVEKIT_URL}
    except Exception as e:
        logger.error(f"Token generation failed: {e}")
        raise HTTPException(status_code=500, detail="Token generation failed")

@app.post("/start-session")
async def start_session(participant: str = "user"):
    """Alias for token generation to support legacy frontend calls."""
    try:
        token = await backend.get_livekit_token(participant)
        return {"token": token, "url": Config.LIVEKIT_URL, "status": "session_started"}
    except Exception as e:
        logger.error(f"Session start failed: {e}")
        raise HTTPException(status_code=500, detail="Session start failed")

@app.post("/vision/toggle")
async def toggle_vision(source: str):
    """Vision Control Endpoint"""
    if source not in ["screen", "camera"]:
        raise HTTPException(status_code=400, detail="Invalid vision source")
    return await backend.toggle_vision_source(source)

@app.get("/health")
async def health():
    return {"status": "healthy", "nats": backend.is_ready}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
