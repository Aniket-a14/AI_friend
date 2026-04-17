# ⏱️ Latency Optimization - CVS-1.0

> **Achieving sub-300ms perceived response latency through Temporal Orchestration and Perception-Aligned Timing.**

---

## Executive Summary (CVS-1.0)

In version **CVS-1.0**, we have moved beyond raw pipeline speed into **Perceptual Timing Mastery**. While raw synthesis latency is important, the human perception of "quickness" depends on conversational pacing, smooth transitions, and the use of fillers. CVS-1.0 achieves a stable **<280ms perceived latency** by implementing a state-machine driven scheduler that synchronizes cognition and signal rendering.

---

## 🏗️ The CVS-1.0 Latency Stack

### 1. Temporal Orchestration (VoiceController)
The **VoiceController** eliminates the "batch-inference" delay by managing a priority-aware playback queue.
- **Formation Buffer (30ms)**: Instead of waiting for a full sentence, the BrainAgent emits semantic chunks as soon as a 30ms "coherence window" is met.
- **Priority Insertion**: High-priority interjections (acknowledgments like "oh," "right") jump the synthesis queue and are inserted into the audio stream at the next **Safe Boundary** (breath or low-energy region).
- **Silence-Based Fallbacks**: If synthesis or reasoning takes longer than **250ms of silence**, the system automatically triggers an intentional "thinking filler" (`hmm.wav`), preserving the illusion of cognitive presence.

### 2. Signal-Aware Optimization
- **Raw PCM Streaming**: By switching to asynchronous raw-byte streaming (`media_type: "raw"`), we eliminated the 44-byte WAV header tax and the associated client-side parsing delay (~40-60ms).
- **Adaptive Jitter Buffer**:
    - **Baseline**: 10ms.
    - **Peak Resilience**: Expands to 25ms during system load spikes.
    - **Exponential Decay**: Rapidly claws back to 10ms once stability returns to maximize responsiveness.
- **Hysteresis-Guarded Detection**: Multi-factor silence detection (energy + variance) prevents "false-positives" from unvoiced consonants (s, f, k) that previously caused stutter.

### 3. Cognitive Optimization
- **Hybrid Heuristic Segmenter**: Replaces word-count splitting with semantic scoring. By splitting at conjunctions and clause markers, we produce smaller, more "breathable" audio chunks that synthesize faster.
- **Feedback-Driven Pacing**: The VoiceAgent publishes telemetry back to the BrainAgent. If the Brain is segmenting too slowly, the Voice triggers an override and instructs the Brain to tighten its scoring logic for the next turn.

---

## 📊 Latency Benchmarks (CVS-1.0 on RTX 4090)

| Stage | Method | Latency (ms) | Percetual Impact |
| :--- | :--- | :--- | :--- |
| **STT** | Whisper Turbo (Streaming) | 40-70ms | Real-time |
| **Brain** | Qwen 2.5 7B (BDI Mesh) | 80-120ms | Thinking phase |
| **Segmenter** | Hybrid Heuristic | 30ms | Formation Buffer |
| **Synthesis** | GPT-SoVITS V4 (Raw PCM) | 120-180ms | Synthesis phase |
| **Controller** | Priority Scheduler | 5-15ms | Adaptive Jitter |
| **Total (Raw)** | Pipeline Sum | **275-415ms** | Theoretical |
| **User Perceived** | **Silence-to-Audio** | **< 280ms** | **Elite-Level** |

---

## 🛠️ Implementation Guidelines

### Audio Normalization & Gain Matching
To prevent volume "pumping" during rapid chunking, we utilize a **100ms rate-adaptive RMS window**. 
- **Fast Speech**: Window tightens to 40ms for fast gain reaction.
- **Slow Speech**: Window expands up to 140ms for stable loudness.
- **Cross-fading**: Chunks are overlapped by 15ms with a linear gain ramp to ensure zero-point alignment.

### Clock Drift Correction
The `VoiceController` state machine includes a **Periodic Resync** (every 5 mins). This recalibrates the base timestamp for the scheduler, preventing the microscopic accumulation of async timing drift that eventually causes playback "clicks" in long-running sessions.

---

**For architectural details, see:**
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System overview
- [VOICE_CLONING.md](./VOICE_CLONING.md) - Identity layer setup