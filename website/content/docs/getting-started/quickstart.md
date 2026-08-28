# Quickstart

Once the mesh is up (see [Installation](/docs/getting-started/installation)),
creating your friend is four commands.

## 1. Describe them

```bash
cd backend
../.venv/bin/python -m scripts.create_friend      # macOS/Linux
../.venv/Scripts/python.exe -m scripts.create_friend  # Windows
```

Describe your friend in your own words — freeform prose, not a template
picker. "She's blunt, hates small talk, gets genuinely annoyed when I dodge
a question, grew up somewhere cold" is a complete description. The wizard
compiles it into a persona and shows you exactly what it inferred — every
numeric temperament choice with its reasoning — before anything is written.

## 2. Preview before committing

Persona seeding is a one-way door: it applies once, on first boot, and
never again. Everything before you confirm is free to redo as many times as
you like; nothing after it is. The wizard lets you try a dry-run
conversation against the compiled persona first.

Your persona is written to the fully gitignored `personal/` directory —
never to a tracked file.

## 3. Give them a voice

```bash
../.venv/bin/python backend/scripts/audio/record_voice.py --duration 8
```

Eight seconds of your own voice (with consent guidance shown first — this
should be your own voice or one you have the right to use). It's
transcribed automatically with the in-repo Whisper, validated for
duration/loudness/clipping, and saved. You don't have to do this before
talking to your friend — a bundled default voice speaks first.

## 4. Talk

```bash
../.venv/bin/python -m scripts.talk
```

`scripts/talk.py` is a REPL against the real cognitive pipeline —
memory, affect, everything — with no LiveKit/STT/TTS required. It's the
fastest way to check whether a compiled persona actually feels like what
you described, and works with no microphone at all.

Once you're ready for voice, the same conversation runs through the full
mesh — LiveKit WebRTC, dual-path STT, and your cloned voice — with nothing
else to configure.
