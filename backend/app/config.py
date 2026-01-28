import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    
    PORCUPINE_ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # Audio Settings
    SAMPLE_RATE = 16000
    FRAME_LENGTH_MS = 20  # ms
    
    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    WAKE_WORD_PATH = os.path.join(BASE_DIR, "..", "wake_up_file", "Hello-love_en_windows_v3_0_0.ppn")

    @staticmethod
    def validate():
        missing = []
        if not Config.PORCUPINE_ACCESS_KEY: missing.append("PORCUPINE_ACCESS_KEY")
        if not Config.GEMINI_API_KEY: missing.append("GEMINI_API_KEY")
        if not Config.ELEVENLABS_API_KEY: missing.append("ELEVENLABS_API_KEY")
        if not Config.ELEVENLABS_VOICE_ID: missing.append("ELEVENLABS_VOICE_ID")
        
        if not Config.DEBUG and not Config.DATABASE_URL:
            # Database is required in production
            missing.append("DATABASE_URL")
            
        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")
