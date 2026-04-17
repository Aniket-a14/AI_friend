# GPT-SoVITS Installation Guide for Windows

## Recommended Method: Direct Installation (No Docker)

### Step 1: Download Integrated Package

1. Go to the official GPT-SoVITS releases page:
   https://github.com/RVC-Boss/GPT-SoVITS/releases

2. Download the latest **Windows integrated package** (prezip file)
   - Look for files like `GPT-SoVITS-windows-package-v*.zip`
   - Size: ~2-3GB

### Step 2: Extract Package

1. Extract the downloaded ZIP file using WinRAR or 7-Zip
2. Extract to a location with no spaces in path (e.g., `C:\GPT-SoVITS`)

### Step 3: Verify FFmpeg

1. Check if `ffmpeg.exe` and `ffprobe.exe` are in the extracted folder
2. If missing, download from: https://ffmpeg.org/download.html
3. Place both files in the GPT-SoVITS root directory

### Step 4: Launch WebUI

1. Navigate to the extracted folder
2. Double-click `go-webui.bat`
3. Wait for the web interface to open (usually at http://localhost:9880)

### Step 5: Change Language (if needed)

If the UI appears in Chinese:
1. Right-click `go-webui.bat` → Edit with Notepad
2. Find the line with language setting
3. Change to `_.US` for English
4. Save and restart

### Step 6: Verify Installation

1. WebUI should open in your browser
2. You should see tabs for training, inference, etc.
3. Test by uploading a short audio file

---

## Alternative: Manual Python Installation

If the integrated package doesn't work:

```bash
# Clone repository
git clone https://github.com/RVC-Boss/GPT-SoVITS.git
cd GPT-SoVITS

# Install dependencies
pip install -r requirements.txt

# Download pretrained models
python download_models.py

# Launch WebUI
python webui.py
```

---

## Next Steps After Installation

1. **Collect Voice Samples**: Record 1-5 minutes of target voice
2. **Upload to WebUI**: Use the training tab
3. **Generate Speaker Embedding**: Follow WebUI instructions
4. **Test Synthesis**: Try generating speech from text

---

## Troubleshooting

### Issue: WebUI won't start
- Check if port 9880 is already in use
- Try running as Administrator

### Issue: Missing dependencies
- Install Visual C++ Redistributable
- Update Python to 3.9 or 3.10

### Issue: CUDA errors (GPU)
- Install CUDA Toolkit 11.8 or 12.x
- Update NVIDIA drivers

---

## Integration with AI Friend AI

Once GPT-SoVITS is running:
1. API will be available at `http://localhost:9871`
2. We'll create VoiceAgent to connect to this API
3. Voice synthesis will happen locally via NATS

Let me know when you've completed the installation!
