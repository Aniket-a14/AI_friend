# 🎙️ Master Guide: Voice Training on Colab

This guide takes you from a raw recording to a fully trained voice model
compatible with this project's voice-agent. Follow these steps exactly to
avoid common "File Not Found" errors.

---

## 📂 Phase 1: Preparing Your Data

Before touching the WebUI, your audio files must be inside Google Colab.

1. **Open the Files Sidebar**: Click the 📁 folder icon on the extreme left of your Colab screen.
2. **Create Folder**: Right-click and select "New Folder". Name it `training_data`.
3. **Upload**: Drag clean recordings (minimum 10-15 mins for a quick clone, 30-60+ mins for a stronger full voice model) into the `training_data` folder.
    - *Must be 32kHz or higher for good training fidelity.*
    - *Prefer mono audio, consistent loudness, minimal noise/reverb, and no clipped words.*

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
4. **Synthesize**: Verify the voice sounds clean at **32kHz**.

---

## 🚩 Phase 6: Exporting for local use (Naming Convention)

To make your voice active in the local app, you **must** rename the files exactly:

1. **GPT Weight**:
    - Download `.ckpt` from `GPT-SoVITS/GPT_weights/`.
    - Rename to: **`ai_friend_voice.ckpt`**.
    - Local Path: `models/GPT_weights/`.

2. **SoVITS Weight**:
    - Download `.pth` from `GPT-SoVITS/SoVITS_weights/`.
    - Rename to: **`ai_friend_voice.pth`**.
    - Local Path: `models/SoVITS_weights/`.

3. **Vocoder**:
    - Download `vocoder.pth` from `GPT-SoVITS/pretrained_models/gsv-v4-pretrained/`.
    - Local Path: `models/SoVITS_weights/`.

---

**The voice-agent loads weights from configured paths on startup (defaults point to `models/GPT_weights/ai_friend_voice.ckpt` and `models/SoVITS_weights/ai_friend_voice.pth`, unless overridden by env vars).**

---

## ✅ Phase 7: Validation and Safe Promotion

Before replacing production voice weights, run this quick gate:

1. **A/B Prompt Set**: Generate 20 fixed prompts with old vs new weights.
2. **Quality Check**: Compare pronunciation, pacing, emotion stability, and artifacts.
3. **Latency Check**: Confirm startup and first-audio latency remain acceptable.
4. **Promote**: Keep only the approved pair as `ai_friend_voice.ckpt` and `ai_friend_voice.pth`.
5. **Rollback Plan**: Keep previous stable files (for example `ai_friend_voice_prev.ckpt/.pth`) and restore immediately if regression appears.

---

## 💭 Prosody and Filler Verification

The delivered voice is modulated per turn by the agent's real endocrine/affect
state (see `docs/ARCHITECTURE.md`'s Signal Rendering section) — this is live
in the shipped pipeline today, not a future feature.

1. **Prosody Consistency**: Verify that your voice model handles high-energy/arousal (faster rate) and low-energy (slower rate) without sounding robotic.
2. **Filler Hydration**: Ensure your `backend/voice_samples/` contains clean recordings of your trained voice for fillers like "hmm", "let me think", etc., to maintain identity continuity during subconscious reflections.
3. **Mock Fallback**: If testing on CPU-only hardware, set `VOICE_TTS_MOCK=true` in `.env` to verify the mesh logic without waiting for heavy synthesis.
