# 🎙️ AI Friend: Rust Migration & Decoupling Strategy (CVS-2.0)

This document provides a comprehensive execution roadmap, folder topology, and code blueprint for migrating the high-latency real-time subsystems of AI Friend (**STT Agent** and **Voice Agent**) from Python to **Rust**.

By separating concerns, we retain Python's massive agility in LLM prompting and memory appraisal while gaining Rust's absolute safety, lock-free memory layout, and deterministic execution speed for WebRTC streams and voice synthesis.

---

## 🧭 1. Architectural Motivation

1.  **Garbage Collection Elimination**: Python's GC can trigger unpredictable pauses (up to 50-100ms) during memory cleanups. In a 32kHz real-time audio pipeline, a 50ms pause results in audibly broken voice chunks. Rust has zero garbage collection, ensuring 100% stable audio delivery.
2.  **Concurrency at Scale**: Rust's asynchronous thread scheduling (`tokio`) can handle high-frequency NATS traffic (such as constant speculative interruption validation ticks) with a fraction of Python's CPU and RAM footprint.
3.  **Standalone Native Binaries**: Compiling the media layer to native statically linked binaries means we can compile optimized Windows (`.exe`/`.msi`), macOS (`.dmg`/`.pkg`), and Linux (`.deb`/`.rpm`) installers that do not require Python, PyTorch, or complex virtual environment packages to run on consumer desktops.

---

## 📁 2. Workspace & Crate Structure

To maintain clean module boundaries, we will establish a Cargo workspace inside the `backend` folder:

```text
backend/
├── Cargo.toml               # Workspace root file
├── app/                     # Python Cognitive Core (Retained)
│   ├── agents/
│   │   ├── brain_agent.py   # RETAINED: OCC & BDI Models
│   │   └── pulse_agent.py   # RETAINED: Heartbeat & maturation logic
│   └── ...
└── crates/                  # NEW: High-performance Rust workspace
    ├── contracts/           # Event structures & JSON schemas (no other code)
    ├── stt-agent/           # Real-time Speech-to-Text NATS agent
    └── voice-agent/         # Real-time Text-to-Speech NATS agent
```

### The Root Workspace Configuration (`backend/Cargo.toml`)
```toml
[workspace]
members = [
    "crates/contracts",
    "crates/stt-agent",
    "crates/voice-agent"
]
resolver = "2"
```

---

## 🛠️ 3. Crate Blueprint: `contracts`
This crate acts as the absolute single source of truth for all events routed through NATS. It translates exactly to the Pydantic schemas defined in Python.

### `backend/crates/contracts/Cargo.toml`
```toml
[package]
name = "contracts"
version = "2.0.0"
edition = "2021"

[dependencies]
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
uuid = { version = "1.0", features = ["v4", "serde"] }
```

### `backend/crates/contracts/src/lib.rs`
```rust
use serde::{Serialize, Deserialize};
use uuid::Uuid;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AffectVector {
    pub valence: f32,
    pub arousal: f32,
    pub dominance: f32,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct TimingParams {
    pub pause_ms: u32,
    pub hesitate: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ChatOutputEvent {
    pub content: String,
    pub affect: AffectVector,
    pub timing: TimingParams,
    pub utterance_id: Uuid,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ControlEvent {
    pub stop_signal: bool,
    pub speculative: bool,
    pub timestamp: u64,
}
```

---

## 🔊 4. Crate Blueprint: `voice-agent`
This agent subscribes to `chat.output`, queries the local GPT-SoVITS HTTP/gRPC server, modulates the amplitude/speed based on the `AffectVector`, and writes raw PCM audio streams back to NATS.

### `backend/crates/voice-agent/Cargo.toml`
```toml
[package]
name = "voice-agent"
version = "2.0.0"
edition = "2021"

[dependencies]
contracts = { path = "../contracts" }
tokio = { version = "1.35", features = ["full"] }
async-nats = "0.31"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
reqwest = { version = "0.11", features = ["json", "stream"] }
ringbuf = "0.3"
```

### `backend/crates/voice-agent/src/playback.rs`
```rust
use ringbuf::{HeapRb, Rb, Producer, Consumer};
use std::sync::{Arc, Mutex};

pub struct AudioPlaybackQueue {
    producer: Arc<Mutex<Producer<i16, Arc<HeapRb<i16>>>>>,
    consumer: Arc<Mutex<Consumer<i16, Arc<HeapRb<i16>>>>>,
    sample_rate: u32,
}

impl AudioPlaybackQueue {
    pub fn new(capacity: usize, sample_rate: u32) -> Self {
        let ring_buffer = HeapRb::<i16>::new(capacity);
        let (prod, cons) = ring_buffer.split();
        
        Self {
            producer: Arc::new(Mutex::new(prod)),
            consumer: Arc::new(Mutex::new(cons)),
            sample_rate,
        }
    }

    /// Feeds processed i16 PCM samples into our playback thread
    pub fn push_samples(&self, samples: &[i16]) -> Result<(), &'static str> {
        let mut prod = self.producer.lock().unwrap();
        if prod.free_len() < samples.len() {
            return Err("Audio buffer overflow! Frame delivery too slow.");
        }
        prod.push_slice(samples);
        Ok(())
    }

    /// Flush the entire audio playback buffer in <1ms on speculative user interruption
    pub fn speculative_interruption_flush(&self) {
        let mut cons = self.consumer.lock().unwrap();
        let skipped = cons.occupied_len();
        cons.skip(skipped);
        println!("Speculative Interruption Handled: Dropped {} buffered audio frames.", skipped);
    }
}
```

### `backend/crates/voice-agent/src/main.rs`
```rust
use contracts::ChatOutputEvent;
use tokio::sync::mpsc;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 1. Establish high-speed async NATS connection
    let nats_url = std::env::var("NATS_URL").unwrap_or_else(|_| "nats://127.0.0.1:4222".to_string());
    let client = async_nats::connect(nats_url).await?;
    println!("Voice Agent (Rust) successfully connected to NATS signal bus.");

    // 2. Subscribe to cognitive chat outputs
    let mut subscriber = client.subscribe("chat.output".to_string()).await?;

    // 3. Audio queue setup (32kHz sample rate)
    let audio_queue = playback::AudioPlaybackQueue::new(64000, 32000);

    // 4. Listen and process incoming decisions
    while let Some(message) = subscriber.next().await {
        let event: ChatOutputEvent = serde_json::from_slice(&message.payload)?;
        println!("Received chat output for synthesis: {}", event.content);

        // TODO: Async HTTP request to local GPT-SoVITS container
        // TODO: Apply digital prosody filters based on event.affect values
        // TODO: Write modulated output to audio.stream
    }

    Ok(())
}
```

---

## 🎙️ 5. Crate Blueprint: `stt-agent`
Listens for binary WebRTC voice input from NATS stream `audio.inbound`. Runs a fast-path speculation check using a local SenseVoice ONNX model, and a high-accuracy semantic parse using Whisper C++.

### `backend/crates/stt-agent/Cargo.toml`
```toml
[package]
name = "stt-agent"
version = "2.0.0"
edition = "2021"

[dependencies]
contracts = { path = "../contracts" }
tokio = { version = "1.35", features = ["full"] }
async-nats = "0.31"
ort = "1.16"              # Rust bindings to ONNX Runtime for SenseVoice
whisper-rs = "0.11"       # Safe Rust bindings to whisper.cpp
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
```

---

## 🗺️ 6. Staged Phase-by-Phase Rollout Plan

Because your agents communicate entirely over independent NATS topics, **there is zero downtime during migration**. We will swap out Python modules for Rust binaries one at a time:

### 📍 Phase 1: Contract Baseline & Workspace Integration
1.  Initialize the Cargo workspace under the `backend/` folder.
2.  Write `crates/contracts/lib.rs` and verify that all serialized fields align 100% with the Python contracts in `backend/app/contracts.py`.

### 📍 Phase 2: Rust Voice Agent & DSP Optimization
1.  Build the async HTTP client inside `voice-agent` to dispatch requests to the local SoVITS engine.
2.  Implement the OLA audio blending algorithm and emotional pitch scaling in `playback.rs` and `prosody.rs`.
3.  Deploy the Rust `voice-agent` container. **Observe absolute voice smoothness: zero audio clipping even during high CPU load!**

### 📍 Phase 3: Rust STT Agent & ONNX Fast-Path
1.  Implement `whisper-rs` bindings and fast-path ONNX SenseVoice triggers.
2.  Route raw PCM signals from NATS directly into the Rust STT thread pool.
3.  **Observe cognitive latency dropping from ~250ms down to <100ms!**

---

## 🔒 7. Verification & Performance Benchmarking

### Automated Stability Checks
*   **Audio Buffering Test**: Validate that `speculative_interruption_flush()` completes in under 1ms and clears memory entirely.
*   **Signal Contention Test**: Verify that both Rust agents and remaining Python agents run concurrently without NATS subject lockups.

### Latency Performance Target Benchmarks
| Measurement | Python Legacy (CVS-1.0) | Rust Optimized (CVS-2.0 Target) |
| :--- | :--- | :--- |
| **First-Frame Synthesis Delay** | ~180ms | **<60ms** |
| **Interruption Stop Latency** | ~120ms | **<15ms** |
| **Total perceived system lag** | ~250ms | **<100ms** |
