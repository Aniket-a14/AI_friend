# 🎙️ Master Guide: AI Friend Voice Training on Colab (CVS-1.0 / V4)

This guide takes you from a raw recording to a fully trained **CVS-1.0 compatible** voice model. Follow these steps exactly to avoid common "File Not Found" errors.

---

## 📂 Phase 1: Preparing Your Data

Before touching the WebUI, your audio files must be inside Google Colab.

1. **Open the Files Sidebar**: Click the 📁 folder icon on the extreme left of your Colab screen.
2. **Create Folder**: Right-click and select "New Folder". Name it `training_data`.
3. **Upload**: Drag clean recordings (10-15 mins of WAV/MP3) into the `training_data` folder.
    - *Must be 32kHz or higher for CVS-1.0 fidelity.*

---

## ✂️ Phase 2: Processing (The "0-Preprocessing" Tab)

Go to the **"0-Preprocessing Dataset Acquisition Tool"** tab.

### Step 2A: Slicing (Tab 0b)

1. **Input audio directory**: Paste `/content/training_data`
2. **Output slicing directory**: Paste `/content/GPT-SoVITS/output/slicer_output`
3. **Action**: Click **"Start Slicing"**.

### Step 2B: Transcription (Tab 0c)

1. **Input folder**: Paste `/content/GPT-SoVITS/output/slicer_output`
2. **Output folder**: Paste `/content/GPT-SoVITS/output/asr`
3. **Language**: Choose **"English"**.
4. **Action**: Click **"Start ASR"**.
5. **Confirm**: Check sidebar for `/content/GPT-SoVITS/output/asr/slicer_output.list`.

---

## 🛠️ Phase 3: Formatting (The "1-GPT-SoVITS-TTS" Tab)

Go to the **"1-GPT-SoVITS-TTS"** tab → **"1A-Dataset Formatting"** sub-tab.

1. **Experiment Name**: Type `ai_friend_voice`.
2. **Dataset list**: Paste `/content/GPT-SoVITS/output/asr/slicer_output.list`
3. **Audio dataset path**: Paste `/content/GPT-SoVITS/output/slicer_output`
4. **Action**: Click **"One-click formatting"**.

---

## ⚒️ Phase 4: Training (Sub-tab 1B)

Go to the **"1B-Fine-tuning Training"** sub-tab.

1. **SoVITS Training**: 
    - Set **Batch Size** to `12`.
    - Set **Total Epochs** to `8`.
    - Click **"Start SoVITS Training"**.
2. **GPT Training**:
    - Set **Total Epochs** to `15`.
    - Click **"Start GPT Training"**.

---

## 🎙️ Phase 5: Inference (Sub-tab 1C)

1. **Refresh**: Click **"Refresh Model Paths"**.
2. **Load GPT**: Select `ai_friend_voice-e15.ckpt`.
3. **Load SoVITS**: Select `ai_friend_voice_e8.pth`.
2. **Synthesize**: Verify the voice sounds clean at **32kHz**.

---

## 🚩 Phase 6: Exporting for CVS-1.0 (Naming Governance)

To make your voice active in the local app, you **must** rename the files exactly:

1. **GPT Weight**:
    - Download `.ckpt` from `GPT-SoVITS/GPT_weights/`.
    - Rename to: **`ai_friend_voice.ckpt`**.
    - Local Path: `backend/models/GPT_weights/`.

2. **SoVITS Weight**:
    - Download `.pth` from `GPT-SoVITS/SoVITS_weights/`.
    - Rename to: **`ai_friend_voice.pth`**.
    - Local Path: `backend/models/SoVITS_weights/`.

3. **Vocoder**:
    - Download `vocoder.pth` from `GPT-SoVITS/pretrained_models/gsv-v4-pretrained/`.
    - Local Path: `backend/models/SoVITS_weights/`.

---

**CVS-1.0 Runtime will automatically detect and load these weights on startup.**
