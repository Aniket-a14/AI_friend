
import asyncio
import os
import sys
from pathlib import Path

# Add backend to path to import app modules
# Script is in backend/scripts/generate_fillers.py
# We need to add backend/ to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.tts.sovits_client import SoVITSClient
from app.config import Config

async def generate_fillers():
    """
    Generates a set of filler audio files for latency masking.
    """
    print("🎙️ Initializing SoVITS Client...")
    sovits = SoVITSClient(base_url=Config.SOVITS_URL)
    
    # Define fillers with distinct emotions/styles if possible, 
    # for now we use the default reference.
    fillers = [
        "Hmm...",
        "Let me see...",
        "Just a moment...",
        "Thinking...",
        "Oh, interesting...",
        "Right...",
        "Okay...",
        "Well...",
    ]
    
    output_dir = Path("app/assets/fillers")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a shorter reference audio to prevent hallucinations/long silence
    # We'll slice the first 4.0 seconds to meet SoVITS requirement (3-10s)
    short_ref_audio_host = "voice_samples/short_ref.wav"
    short_ref_audio_container = "output/short_ref.wav" # Path inside Docker container
    short_ref_text = "At the end of the exam, the program shows" # Approximate text for first 4.0s
    
    import wave
    
    gold_path = "voice_samples/sample_en_gold.wav"
    if not os.path.exists(short_ref_audio_host):
        print(f"✂️ Slicing {gold_path} to create short reference...")
        try:
            with wave.open(gold_path, 'rb') as source:
                params = source.getparams()
                # params: (nchannels, sampwidth, framerate, nframes, comptype, compname)
                framerate = source.getframerate()
                
                # Slice first 4.0 seconds (needs to be >= 3s)
                frames_to_read = int(framerate * 4.0)
                frames = source.readframes(frames_to_read)
                
                with wave.open(short_ref_audio_host, 'wb') as dest:
                    dest.setparams(params)
                    dest.setnframes(len(frames))
                    dest.writeframes(frames)
            print("✅ Created short_ref.wav")
        except Exception as e:
            print(f"⚠️ Failed to slice audio: {e}. Using original.")
            short_ref_audio_container = "output/sample_en_gold.wav" # Fallback container path
            short_ref_text = "At the end of the exam, the program shows the performance summary which includes the total number of questions."
    else:
        print("ℹ️ short_ref.wav already exists, using it.")

    import time

    print(f"📂 Output directory: {output_dir.absolute()}")
    
    for text in fillers:
        filename = text.lower().replace("...", "").replace(" ", "_").replace(",", "") + ".wav"
        filepath = output_dir / filename
        
        # FORCE REGENERATION: Delete if exists to fix the "long silence" issue
        if filepath.exists():
            print(f"🔄 Deleting old {filename}...")
            filepath.unlink()
            
        print(f"🗣️ Synthesizing: '{text}' -> {filename}")
        
        try:
            with open(filepath, "wb") as f:
                async for chunk in sovits.synthesize_stream(
                    text=text,
                    ref_audio_path=short_ref_audio_container,
                    ref_text=short_ref_text,
                    text_lang="en",
                    ref_lang="en"
                ):
                    if chunk:
                        f.write(chunk)
            print(f"✅ Saved {filename}")
            time.sleep(1) # Be gentle to local server
        except Exception as e:
            print(f"❌ Failed to synthesize '{text}': {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(generate_fillers())
