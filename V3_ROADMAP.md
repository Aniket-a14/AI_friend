# v3.0 Complete Implementation Roadmap
**From Cloud-Dependent to Sovereign Real-Time Mesh**

---

## ✅ Phase 16: Core Infrastructure (COMPLETED)
**Status**: Deployed and Verified

- [x] NATS JetStream event bus
- [x] Neo4j graph database
- [x] BaseAgent abstraction
- [x] GraphDB & TripleExtractor
- [x] Memory Agent demo

---

## ✅ Phase 17: Local Brain Deployment (COMPLETED)
**Goal**: Replace Gemini with local LLM for privacy and latency

### 17.1 LLM Infrastructure
- [x] Deploy **Ollama** or **vLLM** server locally
- [x] Test models: Llama 3.2 (3B/8B), Qwen 2.5, Mistral
- [x] Benchmark latency vs Gemini (target: <500ms first token)

### 17.2 LLM Integration
- [x] Create `BrainAgent` that subscribes to `chat.input` events
- [x] Implement streaming response via NATS pub to `chat.output`
- [ ] Add GraphRAG context injection (deferred to Phase 22)

### 17.3 Hinglish Fine-Tuning (Optional)
- [ ] Collect Hinglish conversation dataset
- [ ] Fine-tune using LoRA on Llama 3.2
- [ ] Benchmark Hinglish fluency vs base model

**Estimated Time**: 1-2 weeks

---

## 🎙️ Phase 18: Local Voice Synthesis
**Goal**: Replace ElevenLabs with local voice cloning

### 18.1 Voice Model Setup
- [ ] Deploy **Coqui XTTS v2** or **GPT-SoVITS**
- [ ] Collect 1-5 minutes of target voice samples
- [ ] Generate speaker embeddings

### 18.2 Voice Integration
- [ ] Create `VoiceAgent` that subscribes to `chat.output`
- [ ] Stream synthesized audio to `audio.stream` topic
- [ ] Benchmark latency (target: <300ms)

### 18.3 Hinglish Voice Training
- [ ] Fine-tune voice model on Hinglish samples
- [ ] Test code-switching quality
- [ ] Compare prosody vs ElevenLabs

**Estimated Time**: 1-2 weeks

---

## 🌐 Phase 19: WebRTC Transport Layer
**Goal**: Replace WebSockets with ultra-low latency WebRTC

### 19.1 WebRTC Server
- [ ] Deploy **LiveKit** SFU or **mediasoup**
- [ ] Configure STUN/TURN servers
- [ ] Test peer connection establishment

### 19.2 Frontend Migration
- [ ] Replace WebSocket with WebRTC DataChannel
- [ ] Implement audio/video track handling
- [ ] Add connection quality monitoring

### 19.3 Backend Integration
- [ ] Create `TransportAgent` bridging NATS ↔ WebRTC
- [ ] Implement jitter buffer and packet loss handling
- [ ] Benchmark end-to-end latency (target: <150ms)

**Estimated Time**: 2-3 weeks

---

## 🧠 Phase 20: Audio-Native Intelligence
**Goal**: Full-duplex audio processing (like Moshi/Ultravox)

### 20.1 Model Deployment
- [ ] Deploy **Moshi** or **Ultravox** (if available)
- [ ] OR: Build custom pipeline (Whisper + LLM + TTS)
- [ ] Test simultaneous listen/speak capability

### 20.2 Full-Duplex Agent
- [ ] Create `AudioBrainAgent` processing raw audio streams
- [ ] Implement interruption handling
- [ ] Add voice activity detection (VAD)

### 20.3 Integration
- [ ] Connect to WebRTC audio tracks
- [ ] Stream to/from NATS audio topics
- [ ] Benchmark conversation naturalness

**Estimated Time**: 3-4 weeks

---

## 👁️ Phase 21: Visual Intelligence
**Goal**: Local vision processing for screen/camera

### 21.1 Vision Model
- [ ] Deploy **Llama 3.2 Vision** (11B/90B) via vLLM
- [ ] OR: Deploy **Molmo** for lighter weight
- [ ] Test image understanding quality

### 21.2 Vision Agent
- [ ] Create `VisionAgent` capturing frames at 1 FPS
- [ ] Publish to `vision.frame` topic
- [ ] Implement frame compression and caching

### 21.3 Multimodal Fusion
- [ ] Merge vision context into BrainAgent prompts
- [ ] Test screen-aware conversations
- [ ] Optimize context window usage

**Estimated Time**: 1-2 weeks

---

## 🗺️ Phase 22: GraphRAG Evolution
**Goal**: Advanced knowledge graph operations

### 22.1 Enhanced Extraction
- [ ] Implement entity disambiguation
- [ ] Add temporal relationships (when events happened)
- [ ] Support multi-hop reasoning

### 22.2 Memory Retrieval
- [ ] Implement semantic search over graph
- [ ] Add relevance ranking
- [ ] Create memory summarization

### 22.3 Proactive Memory
- [ ] Agent suggests relevant memories during chat
- [ ] Implement "remember when..." queries
- [ ] Add memory consolidation (merge similar nodes)

**Estimated Time**: 2-3 weeks

---

## 🎮 Phase 23: Spatial AI (Future)
**Goal**: AR/VR presence and on-device inference

### 23.1 Unity Integration
- [ ] Deploy **Unity Sentis** for on-device inference
- [ ] Create 3D avatar with lip-sync
- [ ] Implement spatial audio

### 23.2 WebXR
- [ ] Build WebXR interface
- [ ] Add hand tracking
- [ ] Implement gaze-based interaction

**Estimated Time**: 4-6 weeks

---

## 📊 Total Timeline Estimate
- **Minimum Viable v3.0** (Phases 17-19): 4-7 weeks
- **Full v3.0** (Phases 17-22): 12-16 weeks
- **v3.0 + Spatial** (All phases): 16-22 weeks

---

## 🎯 Recommended Next Phase
**Phase 17: Local Brain Deployment**

This gives you:
1. **Privacy**: All conversations stay local
2. **Cost**: No API fees
3. **Customization**: Fine-tune for Hinglish
4. **Foundation**: Required for all other phases

Start with deploying Ollama and testing Llama 3.2 (3B) for speed.
