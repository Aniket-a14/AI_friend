# GPT-SoVITS Installation Guide

This guide covers the local installation of GPT-SoVITS, the self-hosted TTS
engine this project's voice-agent renders every utterance through.

---

## 💻 Recommended Method: Windows Integrated Package

### Step 1: Download V4 Base

1. Go to the [Official Releases](https://github.com/RVC-Boss/GPT-SoVITS/releases).
2. Download the **V4 Integrated Package** (`GPT-SoVITS-v4.zip`).

### Step 2: Compatibility Notes

Before launching, a few dependency pins avoid known breakage:

1. **FFmpeg**: Ensure `ffmpeg.exe` and `ffprobe.exe` are in the root folder.
2. **Audio Fix**: Install `libsox` to your system (on Windows, this is usually bundled in the prezip).
3. **CPU-only fallback**: If running without a CUDA GPU, explicitly set `--device cpu --half False` in your launch script. The voice-agent's startup check for a missing reference clip and its healthcheck are what actually degrade gracefully here — see `docs/ARCHITECTURE.md`'s Signal Rendering section.
4. **Language**: The bundled default voice and the STT pipeline are both English-only in this project by default.

### Step 3: Launch

Double-click `go-webui.bat`. The UI will launch at `http://localhost:9874`.

---

## 🐧 Alternative: Manual Linux/WSL2 Installation

If using manual `pip` installation, these pins are known to work with this project's integration:

```bash
# 1. System Dependencies
sudo apt-get install -y ffmpeg libsox-dev cmake

# 2. Known-working pins
pip install "numpy<2.0" numba librosa==0.10.2
pip install --no-binary=opencc opencc-python-reimplemented
pip install -r requirements.txt

# 3. Model Download (V4)
python download_models.py --v4
```

---

## 🔌 Integration with the voice-agent

Once the WebUI is running, the Rust **voice-agent** communicates via the local API.

1. **API Port**: Default is `9871`.
2. **Format**: Ensure the WebUI is configured for **32kHz Raw PCM** for maximum fidelity.
3. **Streaming Mode**: Enable raw streaming responses where supported. The voice-agent queues chunks as they arrive rather than waiting for complete synthesis.
4. **Local Sync**: Put your trained models in the `backend/models/` directory using the renaming convention from the [Cheatsheet](./COLAB_PATHS_CHEATSHEET.md).

### Runtime Expectations

The TTS API should return audio only. Do not rely on GPT-SoVITS to interpret this project's expression markup. The voice-agent handles timing tags such as `<pause=300ms>` and `<hesitate>` by injecting PCM silence directly, and strips legacy emotion wrappers before synthesis.

---

## 🛠️ Troubleshooting

### Issue: `ImportError: cannot import name 'soft_unicode'`

- **Fix**: `pip install markupsafe==2.0.1`

### Issue: `ModuleNotFoundError: No module named 'opencc'`

- **Fix**: Reinstall with the `--no-binary` flag as shown in the manual install section.

---

**For training workflows, see [_archive/docs/TRAINING_GUIDE.md](../_archive/docs/TRAINING_GUIDE.md)**
