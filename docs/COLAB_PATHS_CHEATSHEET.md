# 🎙️ Master Guide: AI Friend Voice Training on Colab (V4)

This guide takes you from a raw recording to a fully trained "AI Friend" voice model. Follow these steps exactly to avoid the common "File Not Found" errors.

---

## 📂 Phase 1: Preparing Your Data
Before touching the WebUI, your audio files must be inside Google Colab.

1.  **Open the Files Sidebar**: Click the 📁 folder icon on the extreme left of your Colab screen.
2.  **Create Folder**: Right-click in the whitespace and select "New Folder". Name it `training_data`.
3.  **Upload**: Drag your voice recordings (WAV or MP3) from your computer into this `training_data` folder.
    > [!IMPORTANT]
    > Wait for the little blue circle icon at the bottom to finish spinning before starting Step 2!

---

## ✂️ Phase 2: Processing (The "0-Preprocessing" Tab)
Go to the **"0-Preprocessing Dataset Acquisition Tool"** tab at the top.

### Step 2A: Slicing (Tab 0b)
*The AI needs short 5-10 second clips, not one long file.*
1.  **Input audio directory**: Paste `/content/training_data`
2.  **Output slicing directory**: Paste `/content/GPT-SoVITS/output/slicer_output`
3.  **Action**: Click the big **"Start Slicing"** button.
4.  **Confirm**: Wait for the "Slicing Process Terminated" message in the console.

### Step 2B: Transcription (Tab 0c)
*The AI needs to know what words are being spoken.*
1.  **Input folder**: Paste `/content/GPT-SoVITS/output/slicer_output`
2.  **Output folder**: Paste `/content/GPT-SoVITS/output/asr`
3.  **Language**: Choose **"English"**.
4.  **Action**: Click **"Start ASR"**.
5.  **Confirm**: Check your `Files` sidebar. You should now see `/content/GPT-SoVITS/output/asr/slicer_output.list`.

---

## 🛠️ Phase 3: Formatting (The "1-GPT-SoVITS-TTS" Tab)
Go to the **"1-GPT-SoVITS-TTS"** tab, then the **"1A-Dataset Formatting"** sub-tab.

1.  **Experiment Name**: Type `ai_friend_v1`.
2.  **Dataset list**: Paste `/content/GPT-SoVITS/output/asr/slicer_output.list`
3.  **Audio dataset path**: Paste `/content/GPT-SoVITS/output/slicer_output`
4.  **Action**: Click **"One-click formatting"**.
    > [!TIP]
    > If this fails, double-check that you didn't leave a dummy "D:/" in any other hidden box!

---

## ⚒️ Phase 4: Training (Sub-tab 1B)
Go to the **"1B-Fine-tuning Training"** sub-tab.

1.  **SoVITS Training**: 
    - Set **Batch Size** to `12` (if you have a good GPU).
    - Set **Total Epochs** to `8`.
    - Click **"Start SoVITS Training"**.
2.  **GPT Training**:
    - Set **Total Epochs** to `15`.
    - Click **"Start GPT Training"**.
3.  **Wait**: Training usually takes 10-20 minutes. Look for the "Training Completed" logs.

---

## 🎙️ Phase 5: Inference (Sub-tab 1C)
*The fun part—actually hearing the voice.*

1.  **Refresh**: Click the **"Refresh Model Paths"** button.
2.  **Load GPT**: In the dropdown, select `ai_friend_v1-e15.ckpt`.
3.  **Load SoVITS**: In the dropdown, select `ai_friend_v1_e8.pth`.
4.  **Reference Audio**: Click the upload box and select a 5s clip from your `/content/training_data` folder.
5.  **Synthesis Text**: Type what you want the AI to say.
6.  **Action**: Click **"Start Inference"** and wait for the player to appear!

---

## 🚩 Phase 6: Exporting to Local App
Once you are happy with the voice:
1.  **Download GPT**: Go to `GPT-SoVITS/GPT_weights/` in Colab and download your `.ckpt` file.
2.  **Download SoVITS**: Go to `GPT-SoVITS/SoVITS_weights/` in Colab and download your `.pth` file.
3.  **Move to project**: Put them in your local `models/` folder as `ai_friend_voice.ckpt` and `ai_friend_voice.pth`.
