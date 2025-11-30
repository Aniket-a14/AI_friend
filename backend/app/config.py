import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    PORCUPINE_ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
    
    # Audio Settings
    SAMPLE_RATE = 16000
    FRAME_LENGTH_MS = 20  # ms
    
    # Paths
    WAKE_WORD_PATH = "wake_up_file/Hello-love_en_windows_v3_0_0.ppn"

    @staticmethod
    def validate():
        missing = []
        if not Config.PORCUPINE_ACCESS_KEY: missing.append("PORCUPINE_ACCESS_KEY")
        if not Config.GEMINI_API_KEY: missing.append("GEMINI_API_KEY")
        if not Config.ELEVENLABS_API_KEY: missing.append("ELEVENLABS_API_KEY")
        if not Config.ELEVENLABS_VOICE_ID: missing.append("ELEVENLABS_VOICE_ID")
        
        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")
