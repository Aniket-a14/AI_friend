# Quickstart Guide

Creating your companion requires no manual JSON/TOML editing. You describe who they are in natural human prose, give them a voice sample, and start talking.

---

## Step 1: Describe Your Friend (CLI or Web)

### Option A: Web Onboarding Wizard (Recommended)
Open your browser to `http://localhost:3000/onboarding`. The guided wizard walks you through:
1. **Describing your friend** in freeform prose.
2. **Reviewing the compiled persona preview** and trying a dry-run chat.
3. **Recording an 8-second voice sample** directly in the browser via Web Audio API.

### Option B: Terminal CLI Wizard
Run the Python persona compiler from the repository root:

```bash
cd backend
../.venv/bin/python -m scripts.create_friend      # macOS / Linux
..\.venv\Scripts\python.exe -m scripts.create_friend  # Windows
```

---

## Step 2: The Persona Compilation Process

When prompted by the wizard, describe your friend in plain, natural language:

```text
> She's a blunt, sarcastic systems engineer who hates corporate buzzwords.
> She grew up in Montreal, reads vintage sci-fi, and gets genuinely annoyed
> when someone dodges a technical question. She's loyal once trust is earned.
```

The Persona Compiler (`app/persona/compiler.py`) automatically maps your description into:
1. **Constitutional Temperament**: Baseline valence, arousal, dominance, and neurochemical sensitivity.
2. **Adaptive Traits**: Seed traits (e.g., *Sarcasm*, *Systems Thinking*, *Directness*) capped at 5.
3. **Biography Context**: Structured biographical background stored into episodic memory.
4. **Authentic Friction Scaffolding**: Linguistic guidelines ensuring the model never degrades into sycophantic flattery.

---

## Step 3: Preview Before Committing

Persona seeding is a **one-way door**: it seeds the database on first boot and is never overwritten by configuration files again. This ensures your friend grows and evolves organically with you.

The wizard displays:
* Full 3-tier boundary breakdown.
* Inferred numeric temperament parameters with plain-English rationales.
* Interactive **Dry-Run Conversation** to verify tone before saving.

Upon confirmation, the persona is written to the gitignored `personal/persona.toml` and `personal/biography.md`.

---

## Step 4: Voice Enrollment (8 Seconds)

Record eight seconds of clear reference audio:

```bash
../.venv/bin/python backend/scripts/audio/record_voice.py --duration 8
```

The enrollment script:
1. Displays clear **consent guidance** (use your own voice or one you have rights to).
2. Captures 8 seconds of clean 16kHz audio.
3. Transcribes the audio automatically using Rust `stt-agent` (Whisper).
4. Validates waveform quality (RMS energy, clipping, background silence ratio).
5. Sets `REF_AUDIO_PATH` and `REF_TEXT` in `.env`.

*(Note: If you skip this step, AI Friend boots with a high-quality bundled CC0-licensed default voice).*

---

## Step 5: Start Talking

### Terminal REPL Mode
Test your friend immediately over the direct NATS message bus:

```bash
../.venv/bin/python -m scripts.talk
```

Example interaction:
```text
$ Talk REPL ready. Connecting to NATS JetStream...
> hey, rough day at work today.
friend: Yeah? What happened this time? Did someone push to production on a Friday again?
```

### Web & Voice Mode
Open `http://localhost:3000/chat` for the real-time streaming text interface, or join the LiveKit WebRTC audio room to talk and observe the reactive viseme pulse aura.

---

Next: [Configuration Reference](/docs/getting-started/configuration).
