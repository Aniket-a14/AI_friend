# Phase 04 Benchmark Plan

Phase: PHASE_04
Architecture Source: FINAL_HUMANOID_BRAIN_ARCHITECTURE.md (Sections 38, 40)
Hardware: Local Apple Silicon / Remote RTX 2060 Super 8GB (home-gpu)

---

## 1. Benchmark Suite Overview

| Benchmark ID | Environment | Description | Metric | Target Threshold |
|---|---|---|---|---|
| **BM-LOC-P4-01** | Local Mac | Calibration and directive evaluation throughput (10,000 iterations) | Mean latency per evaluation | < 0.05 ms |
| **BM-LOC-P4-02** | Local Mac | Multi-person isolation stress test (1,000 queries across 10 simulated persons) | Cross-person private leakage rate | Strictly 0.0% |
| **BM-LOC-P4-03** | Local Mac | Background job preemption latency under concurrent execution | Time to cancel background job | < 5.0 ms |
| **BM-GPU-P4-01** | Remote GPU | TTFT delta with metacognition & social state enabled (`qwen2.5:3b`) | TTFT difference vs Phase 03 baseline | Delta < 15.0 ms |
| **BM-GPU-P4-02** | Remote GPU | Social rupture-repair trajectory fidelity (10-turn interaction) | Expected stance transitions | 100% trajectory adherence |

---

## 2. Local Execution Protocol

Execute from `backend/`:
```bash
../.venv/bin/python -m pytest tests/test_social_metacognition.py tests/test_background_governed_learning.py
```

## 3. Remote GPU Execution Protocol

Execute on `home-gpu`:
```bash
bash scripts/remote/gpu.sh "cd AI_friend && .venv/bin/python -m pytest backend/tests/test_social_metacognition.py backend/tests/test_background_governed_learning.py"
```

