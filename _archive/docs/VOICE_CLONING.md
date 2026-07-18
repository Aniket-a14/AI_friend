> [!NOTE]
> **LEGACY ARCHIVE FOR REFERENCE - CVS-3.0 BASELINE**
> This document is maintained for historical context and architectural reference. The current live production runtime implements **CVS-3.5 Premium Edition** featuring Rust FFI acceleration and a 4-tier storage mesh.

# 🎙️ CVS-1.0: Real-time Voice Identity

> **Engineering human-like vocal presence through V4 architecture and Signal Mastery.**

---

## 🏗️ The CVS-1.0 Voice Stack

In **CVS-1.0**, the VoiceAgent is no longer a simple synthesis worker. It is a **Persistent Signal Runtime** that maintains a stable voice identity and produces high-fidelity, perception-aligned audio in real-time.

### 1. V4 Architecture & Native PCM

The system is optimized for **GPT-SoVITS V4**, providing studio-quality results without the latency of legacy headers.

- **Waveform Fidelity**: 32kHz sampling rate (native V4 output).
- **Zero-Header Streaming**: Raw 16-bit PCM buffers are streamed directly, eliminating **44-byte WAV header tax** and reducing client-side parsing by **~60ms**.
- **Chunk-First Playback**: VoiceAgent queues PCM chunks as they arrive from GPT-SoVITS, so the listener can hear first audio before the full segment finishes synthesizing.
- **One-Time Identity Load**: Model weights (`GPT_weights` and `SoVITS_weights`) are loaded into VRAM once at startup, ensuring subsequent synthesis turns are mathematically pure text-to-audio operations without cloning overhead.

### 2. Signal Rendering (Audio Engine)

The CVS-1.0 Signal Engine ensures every audio chunk sounds natural and consistent:

- **Adaptive Normalization**: A **100ms rate-aware RMS window** stabilizes loudness across emotional intensities.
- **Peak Control**: Strictly capped at **-1 dBFS** to prevent digital clipping in high-arousal states.
- **Energy-Matched Cross-fading**: 15ms linear gain ramps align the energy of adjacent speech chunks to ensure perfectly smooth transitions.

### 3. Stylistic Cache Clustering

Conventional caching is too rigid for expressive speech. CVS-1.0 uses **Multidimensional Perceptual Clustering**:

- **Similarity Metric**: $\alpha(EmotionDiff)^2 + \beta|RateDiff|$.
- **Safe Reuse**: Audio is only reused if the emotional intensity and speaking rate match the stylistic target within a tight perceptual threshold.

### 4. Text vs Expression Boundary

The voice layer should synthesize natural speech, not control markup.

- Supported timing markers: `<pause=300ms>` and `<hesitate>`.
- Legacy `<emotion ...>` wrappers are stripped before TTS.
- Emotion, rate, and intensity should be carried as structured metadata from `chat.output`.

This boundary matters because the user should hear a person speaking, not the system leaking its control protocol into the cloned voice.

---

## 🛠️ Professional Fine-Tuning (Custom Voice)

For the highest quality and lowest latency, we utilize a fine-tuned **V4 model**. This "bakes" the target identity into the model weights, removing the need for reference WAVs and providing superior emotional range.

### 🚀 Benefits of V4 Fine-Tuning

- **Sub-300ms Perceived Latency**.
- **Elite Prosody**: Natural inflection during complex social reasoning.
- **Zero Hallucinations**: Fine-tuning significantly stabilizes the synthesis against metallic artifacts.

### 📖 The Training Guide

For full instructions on generating your own V4 weights using our one-click Colab workflow, see:

- [TRAINING_GUIDE.md](./TRAINING_GUIDE.md) — Step-by-step model creation.
- [LATENCY_IMPROVEMENT.md](./LATENCY_IMPROVEMENT.md) — Timing and scheduling deep-dive.

---

## 🛡️ Avoiding Synthesis Artifacts ("Random Lines")

GPT-SoVITS is a few-shot model. To prevent "hallucinations" or random lines being synthesized, follow these rules:

1. **Golden Reference Sample**: Even with a trained model, SoVITS requires a **Reference Audio** clip. This clip **MUST** match the vocal signature of your trained model exactly.
2. **Precision Text Matching**: The `ref_text` in `Config` must match the spoken words in the `ref_audio` perfectly. Any mismatch will cause the model to synthesize gibberish or hallucinate random segments.
3. **PCM Purity**: Always use raw PCM for reference audio to avoid header-corruption in the embedding calculation.

## 🎭 The Social Mesh (Filler Service)

AI Friend utilizes a pre-synthesized "Social Mesh" of fillers (Hmm, Accha, Haan). These are played from memory when synthesis takes longer than 350ms to maintain conversational presence.

### 🚀 Benefits of V4 Fine-Tuning

- **Sub-300ms Perceived Latency**.
- **Elite Prosody**: Natural inflection during complex social reasoning.
- **Zero Hallucinations**: Fine-tuning significantly stabilizes the synthesis against metallic artifacts.

### 📖 The Training Guide

For full instructions on generating your own V4 weights using our one-click Colab workflow, see:

- [TRAINING_GUIDE.md](./TRAINING_GUIDE.md) — Step-by-step model creation.
- [LATENCY_IMPROVEMENT.md](./LATENCY_IMPROVEMENT.md) — Timing and scheduling deep-dive.

---

**Designed for Identity. Refined for Emotion.**
