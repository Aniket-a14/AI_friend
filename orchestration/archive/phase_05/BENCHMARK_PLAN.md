# Phase 05 Benchmark Plan

Phase: PHASE_05
Architecture Source: FINAL_HUMANOID_BRAIN_ARCHITECTURE.md (Sections 38, 40)
Hardware: Local Apple Silicon / Remote RTX 2060 Super 8GB (home-gpu)

---

## 1. Benchmark Suite Overview

| Benchmark ID | Environment | Description | Metric | Target Threshold |
|---|---|---|---|---|
| **BM-LOC-P5-01** | Local Mac | Voice compiler throughput and intent loss telemetry fidelity (1,000 intents) | Mean latency & loss capture rate | < 0.05 ms, 100% capture |
| **BM-LOC-P5-02** | Local Mac | Vision adapter normalization and brain invariant stress test (1,000 percepts) | Normalization latency & mutation rate | < 0.05 ms, strictly 0% mutation |
| **BM-LOC-P5-03** | Local Mac | Model role capability negotiation and fallback evaluation (1,000 checks) | Mean evaluation latency | < 0.01 ms |
| **BM-LOC-P5-04** | Local Mac | External action risk and authorization gating throughput (1,000 actions) | Unauthorized block rate & latency | 100% block, < 0.01 ms |
| **BM-GPU-P5-01** | Remote GPU | Model provider swap TTFT delta and state continuity (llama3.2:3b vs qwen2.5:3b) | TTFT delta & state invariance | Delta <= 25.0 ms, 100% invariant |
| **BM-GPU-P5-02** | Remote GPU | End-to-end SpeechIntent voice compilation and workspace isolation | Workspace isolation & compiler latency | 0% provider leak, < 5.0 ms |

---

## 2. Local Execution Protocol

Execute from backend/:
```bash
../.venv/bin/python -m pytest tests/test_voice_external_action.py tests/test_model_roles_vision.py
```

## 3. Remote GPU Execution Protocol

Execute on home-gpu:
```bash
bash scripts/remote/gpu.sh "cd AI_friend && .venv/bin/python -m pytest backend/tests/test_voice_external_action.py backend/tests/test_model_roles_vision.py"
```
