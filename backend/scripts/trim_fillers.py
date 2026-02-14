import os
import subprocess

def trim_wav_files():
    """
    Trims the start of WAV files in app/assets/fillers using ffmpeg,
    keeping only the last 1.5 seconds.
    """
    filler_dir = "app/assets/fillers"
    if not os.path.exists(filler_dir):
        print(f"❌ Directory not found: {filler_dir}")
        return

    files = [f for f in os.listdir(filler_dir) if f.endswith(".wav")]
    print(f"✂️ Trimming {len(files)} files in {filler_dir} using ffmpeg...")

    for filename in files:
        filepath = os.path.join(filler_dir, filename)
        temp_path = filepath + ".temp.wav"
        
        # Command: ffmpeg -y -sseof -1.5 -i input.wav -c:a pcm_s16le output.wav
        # -sseof -1.5: Seek to 1.5 seconds before EOF
        cmd = [
            "ffmpeg",
            "-y",
            "-sseof", "-1.5",
            "-i", filepath,
            "-c:a", "pcm_s16le",
            temp_path
        ]
        
        try:
            # Capture output to avoid clutter, check return code
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if result.returncode == 0:
                os.replace(temp_path, filepath)
                print(f"✅ Trimmed {filename} (kept last 1.5s)")
            else:
                # If sseof fails (e.g. file too short), it might error or copy whole file
                # Check stderr
                err = result.stderr.decode()
                print(f"⚠️ ffmpeg warning for {filename}: {err[:100]}...")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        except Exception as e:
            print(f"❌ Failed to run ffmpeg for {filename}: {e}")

if __name__ == "__main__":
    trim_wav_files()
