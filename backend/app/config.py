import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    
    # NATS Configuration
    NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
    
    # LiveKit Configuration (Sovereign Mesh)
    LIVEKIT_URL = os.getenv("LIVEKIT_URL", "http://localhost:7880")
    LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
    LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "devsecret-at-least-thirty-two-characters-long")
    
    # Memory & Personality
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # Still used for embeddings
    DATABASE_URL = os.getenv("DATABASE_URL")
    AI_NAME = os.getenv("AI_NAME", "AI Friend")
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    SOVITS_URL = os.getenv("SOVITS_URL", "http://localhost:9871")
    STT_MODEL_SIZE = os.getenv("STT_MODEL_SIZE", "small")
    STT_DEVICE = os.getenv("STT_DEVICE", "cpu")
    
    # Audio Settings
    SAMPLE_RATE = 16000
    
    @staticmethod
    def validate():
        missing = []
        if not Config.GEMINI_API_KEY: missing.append("GEMINI_API_KEY")
        if not Config.DATABASE_URL: missing.append("DATABASE_URL")
        if not Config.LIVEKIT_API_KEY: missing.append("LIVEKIT_API_KEY")
        
        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")
