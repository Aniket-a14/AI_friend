# GPT-SoVITS Installation Guide (CVS-3.5 Optimized)

This guide covers the local installation of GPT-SoVITS, hardened for **CVS-3.5 (April 2026)** requirements.

---

## 💻 Recommended Method: Windows Integrated Package

### Step 1: Download V4 Base

1. Go to the [Official Releases](https://github.com/RVC-Boss/GPT-SoVITS/releases).
2. Download the **V4 Integrated Package** (`GPT-SoVITS-v4.zip`).

### Step 2: CVS-3.5 Hardening (Required)

Before launching, ensure your local Python environment won't crash due to 2026 dependency shifts:

1. **FFmpeg**: Ensure `ffmpeg.exe` and `ffprobe.exe` are in the root folder.
2. **Audio Fix**: Install `libsox` to your system (on Windows, this is usually bundled in the prezip).
3. **Hardware-Agnostic FP32 Fallback**: If running in a CPU-only environment (no CUDA), explicitly set `--device cpu --half False` in your launch script. The CVS-3.5 Rust integration will detect this and fallback gracefully without crashing.
4. **Language Enforcement**: To maximize deterministic throughput, the TTS engine (along with SenseVoice) is strictly restricted to English by default.

### Step 3: Launch

Double-click `go-webui.bat`. The UI will launch at `http://localhost:9874`.

---

## 🐧 Alternative: Manual Linux/WSL2 Installation

If using manual `pip` installation, you **must** use the CVS-3.5 hardened pins:

```bash
# 1. System Dependencies
sudo apt-get install -y ffmpeg libsox-dev cmake

# 2. Hardened Python Pins (April 2026 Standard)
pip install "numpy<2.0" numba librosa==0.10.2
pip install --no-binary=opencc opencc-python-reimplemented
pip install -r requirements.txt

# 3. Model Download (V4)
python download_models.py --v4
```

---

## 🔌 Integration with CVS-3.5

Once the WebUI is running, the **Voice Agent** communicates via the local API.

1. **API Port**: Default is `9871`.
2. **Format**: Ensure the WebUI is configured for **32kHz Raw PCM** for maximum fidelity.
3. **Streaming Mode**: Enable raw streaming responses where supported. The CVS VoiceAgent is optimized to queue chunks as they arrive rather than waiting for complete synthesis.
4. **Local Sync**: Put your trained models in the `backend/models/` directory using the renaming convention from the [Cheatsheet](./COLAB_PATHS_CHEATSHEET.md).

### Runtime Expectations

The TTS API should return audio only. Do not rely on GPT-SoVITS to interpret CVS expression markup. The VoiceAgent handles timing tags such as `<pause=300ms>` and `<hesitate>` by injecting PCM silence directly, and strips legacy emotion wrappers before synthesis.

---

## 🛠️ Troubleshooting (2026 Edition)

### Issue: `ImportError: cannot import name 'soft_unicode'`

- **Fix**: `pip install markupsafe==2.0.1`

### Issue: `ModuleNotFoundError: No module named 'opencc'`

- **Fix**: Reinstall with the `--no-binary` flag as shown in the manual install section.

---

**For training workflows, see [_archive/docs/TRAINING_GUIDE.md](../_archive/docs/TRAINING_GUIDE.md)**
