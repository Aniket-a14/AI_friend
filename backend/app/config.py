import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    
    PORCUPINE_ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpg8ndEao7m8D")
    LOCATION_CONTEXT = os.getenv("LOCATION_CONTEXT", "Jalandhar, Punjab") # For weather and local grounding
    DATABASE_URL = os.getenv("DATABASE_URL")
    AI_NAME = os.getenv("AI_NAME", "AI Friend")
    
    # Audio Settings
    SAMPLE_RATE = 16000
    FRAME_LENGTH_MS = 20  # ms
    
    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    @staticmethod
    def get_wake_word_path():
        """Find the correct .ppn file for the current platform."""
        folder = os.path.join(Config.BASE_DIR, "..", "wake_up_file")
        if not os.path.exists(folder):
            return None
        
        # Look for .ppn files
        files = [f for f in os.listdir(folder) if f.endswith(".ppn")]
        platform_suffix = "windows" if os.name == "nt" else "linux"
        
        # Priority 1: Match the platform exactly
        for f in files:
            if platform_suffix in f.lower():
                return os.path.join(folder, f)
        
        # Priority 2: Return the first .ppn found
        if files:
            return os.path.join(folder, files[0])
            
        return None

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
