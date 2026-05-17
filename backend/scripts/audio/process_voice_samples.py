"""
Voice Sample Processor & Manager
Helps organize multiple voice files for GPT-SoVITS cloning.
"""

import os

# Move to the project root for relative paths to work correctly
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES_DIR = os.path.join(BASE_DIR, "voice_samples")


def list_samples():
    if not os.path.exists(SAMPLES_DIR):
        os.makedirs(SAMPLES_DIR, exist_ok=True)
        return []
    wavs = [f for f in os.listdir(SAMPLES_DIR) if f.endswith(".wav")]
    extras = [
        f
        for f in os.listdir(SAMPLES_DIR)
        if f.lower().endswith((".mp3", ".mp4", ".ogg"))
    ]
    return wavs, extras


def main():
    print("🎙️ AI Friend Voice Sample Manager")
    print("-" * 30)

    wavs, extras = list_samples()

    if not wavs and not extras:
        print("❌ No voice samples found in backend/voice_samples/")
        print("Please place your audio files (mp3, mp4, ogg, wav) there first.")
        return

    if extras:
        print(f"📦 Found {len(extras)} files that need conversion to WAV for the AI:")
        for e in extras:
            # Handle extensions
            ext = os.path.splitext(e)[1]
            wav_name = e.replace(ext, ".wav")
            print(f"  👉 To convert '{e}', run:")
            # Wrap in quotes for spaces
            print(
                f'     ffmpeg -i "voice_samples/{e}" -ac 1 -ar 22050 "voice_samples/{wav_name}"'
            )
        print("-" * 30)

    if wavs:
        print(f"✅ Found {len(wavs)} WAV voice samples (Ready for AI):")
        for i, s in enumerate(wavs, 1):
            size_mb = os.path.getsize(os.path.join(SAMPLES_DIR, s)) / (1024 * 1024)
            print(f"  {i}. {s} ({size_mb:.2f} MB)")

    print("\n💡 Strategy Guide:")
    print(
        "1. [Quick] Zero-Shot: Pick the CLEARest 5-10 second clip (Best for instant use)"
    )
    print(
        "2. [Quality] Fine-Tuning: Use all clips (3-5 mins total) for a custom model (Requires WebUI)"
    )

    # Check for transcripts
    for s in wavs:
        txt_file = s.replace(".wav", ".txt")
        if not os.path.exists(os.path.join(SAMPLES_DIR, txt_file)):
            print(f"\n⚠️  Missing transcript for: {s}")
            print(
                f"   Please create a text file named '{txt_file}' containing exactly what is said in the audio."
            )

    print("\n🚀 Ready to go!")
    print(f"Files are located at: {SAMPLES_DIR}")


if __name__ == "__main__":
    main()
