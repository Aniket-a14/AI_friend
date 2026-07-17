import logging
import json
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from livekit import api
import nats

from app.config import Config
from app.network import is_lan_client_allowed
# scripts.bootstrap, not scripts: the old import pointed at a module that does not
# exist, so main.py could not even be imported — the Provisioning Guard below,
# together with its "models verified and locked" log, had never once run.
from scripts.bootstrap.provision_models import ensure_models_provisioned
from app.logging_config import setup_logging

# Configure logging
setup_logging(level=logging.INFO, json_format=getattr(Config, "LOG_JSON", False))
logger = logging.getLogger("ai_friend_backend")


class AIBackend:
    """
    Sovereign signaling server for the AI Friend Voice Mesh.
    Manages WebRTC tokens and broadcasts control signals via NATS.
    """

    def __init__(self):
        self.vision_source = "screen"  # screen | camera
        self.is_ready = False
        self.nc = None

    async def initialize(self):
        """Minimal initialization for signaling server with Provisioning Guard."""
        logger.info("Initializing Sovereign Signaling Backend...")

        # 1. CVS-3.5 Provisioning Guard (Solid State Mesh Requirement)
        try:
            ensure_models_provisioned()
            logger.info("✅ Sensory Mesh models verified and locked.")
        except Exception as e:
            logger.error(f"❌ Provisioning Guard Failure: {e}")
            # In a production identity system, we might halt boot here.

        # 2. Network Mesh Discovery
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


async def require_lan_client(request: Request):
    if not Config.LAN_ONLY:
        return

    # In a local-only system, x-forwarded-for should not be trusted as it can be spoofed.
    # We strictly check the direct client host connection.
    host = request.client.host if request.client else None
    if not is_lan_client_allowed(host):
        raise HTTPException(status_code=403, detail="LAN clients only")


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
    lifespan=lifespan,
    dependencies=[Depends(require_lan_client)],
)

# CORS Middleware (Sovereign Local Access)
#
# Credentials must never be combined with a wildcard origin. The CORS spec forbids
# it, and Starlette reacts by reflecting back whichever Origin the caller sent —
# which would let any website on the internet make credentialed requests against
# this host. Resolve the origin policy explicitly rather than always passing
# allow_credentials=True.
_lan_default = Config.LAN_ONLY and Config.ALLOWED_ORIGINS == ["*"]

if _lan_default:
    # Local-first default: permit loopback / private-range origins via regex.
    _cors_policy = {
        "allow_origins": [],
        "allow_origin_regex": Config.LAN_CORS_ORIGIN_REGEX,
        "allow_credentials": True,
    }
elif "*" in Config.ALLOWED_ORIGINS:
    logger.warning(
        "ALLOWED_ORIGINS is '*' while LAN_ONLY is disabled. Disabling credentialed "
        "CORS, since wildcard-plus-credentials would reflect arbitrary origins. "
        "Set an explicit origin allowlist to re-enable credentials."
    )
    _cors_policy = {
        "allow_origins": ["*"],
        "allow_origin_regex": None,
        "allow_credentials": False,
    }
else:
    _cors_policy = {
        "allow_origins": Config.ALLOWED_ORIGINS,
        "allow_origin_regex": None,
        "allow_credentials": True,
    }

app.add_middleware(
    CORSMiddleware,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    **_cors_policy,
)


@app.get("/")
async def root():
    return {
        "status": "online",
        "identity": "Sovereign Mesh Bridge",
        "ready": backend.is_ready,
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
