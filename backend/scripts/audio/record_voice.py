"""
Record Voice Sample
Simple script to record audio from microphone for voice cloning
"""

import sounddevice as sd
import soundfile as sf
import time
import os


def record_audio(duration: int = 120, filename: str = "voice_sample.wav"):
    """
    Record audio from default microphone

    Args:
        duration: Seconds to record
        filename: Output filename
    """
    print(f"🎙️ Recording for {duration} seconds...")
    print("Speak naturally! Tell a story or read a book.")
    print("3...")
    time.sleep(1)
    print("2...")
    time.sleep(1)
    print("1...")
    time.sleep(1)
    print("🔴 GO!")

    fs = 22050  # Sample rate for SoVITS
    audio = sd.rec(int(duration * fs), samplerate=fs, channels=1)

    # Show progress
    for i in range(duration):
        if i % 10 == 0:
            print(f"⏳ {duration - i}s remaining...")
        time.sleep(1)

    sd.wait()
    print("⏹️ Recording complete!")

    # Save file
    output_dir = os.path.join(os.path.dirname(__file__), "voice_samples")
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)

    sf.write(filepath, audio, fs)
    print(f"✅ Saved to: {filepath}")


if __name__ == "__main__":
    try:
        seconds = int(input("Enter duration in seconds (default 120): ") or 120)
        name = (
            input("Enter filename (default: voice_sample.wav): ") or "voice_sample.wav"
        )
        record_audio(seconds, name)
    except KeyboardInterrupt:
        print("\n❌ Cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print(
            "Tip: You might need to install sounddevice: pip install sounddevice soundfile numpy"
        )
