# Phase 01: Acceptance Criteria & Gate Requirements

**Phase:** `PHASE_01` — Authoritative Causal Slice  
**Target Reference:** `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` (§38 & §39)  
**Status:** Frozen Criteria for Phase Gate Evaluation  
**Note on GPU Criteria:** GPU-dependent criteria are marked `PENDING_GPU — server expected online tomorrow`. The phase gate CANNOT pass until both local and GPU criteria are satisfied tomorrow.

---

## 1. Local Acceptance Criteria (Mac Environment)

These criteria will be evaluated on the integration branch on the local development machine tomorrow:

| ID | Category | Requirement | Validation Method | Threshold / Expected Outcome | Status |
|---|---|---|---|---|---|
| **AC-01** | Workspace Authority | Every cognitive turn must read from exactly one `CognitiveWorkspaceSnapshot` revision and commit a bounded delta. | Unit & Integration tests (`test_causal_slice.py`) | 100% of turns reference a valid `(epoch, revision)` tuple. | `PENDING_EXECUTION` |
| **AC-02** | CAS Concurrency Guard | Stale writes with mismatched expected revision must be deterministically rejected. | Concurrent race test with 20 parallel tasks (`test_workspace_store.py`) | Exactly 1 success, 19 `StaleWorkspaceError` rejections; zero state corruption. | `PENDING_EXECUTION` |
| **AC-03** | Restart Epoch Isolation | Restarting a process increments the persisted epoch; any pending write from a previous epoch is rejected. | Crash/restart simulation test (`test_workspace_store.py`) | Rejection of prior epoch commands; zero spurious overwrites. | `PENDING_EXECUTION` |
| **AC-04** | Percept Normalization | All incoming sensory/system events (chat, vision description, facial reflex, audio stop, ticks) map losslessly to `PerceptEnvelope`. | Parametrized unit tests across all modalities (`test_causal_slice.py`) | `PerceptEnvelope` validated with modality, source, confidence, timestamp, and payload. | `PENDING_EXECUTION` |
| **AC-05** | Explicit Action Intent | Behavior decision commits a typed `ActionIntent` before text generation occurs. | Pipeline trace inspection (`test_causal_slice.py`) | `ActionIntent` emitted with `workspace_epoch`, `workspace_revision`, and `turn_id`. | `PENDING_EXECUTION` |
| **AC-06** | Terminal Outcome Tracking | Completed and interrupted turns must produce a terminal `OutcomeRecord`. | End-to-end turn execution & interruption simulation | `OutcomeRecord` status matches outcome (`COMPLETED`, `TRUNCATED`, `CANCELLED`); exact character offset matches heard speech. | `PENDING_EXECUTION` |
| **AC-07** | Dual-Write Compatibility | Workspace dual-writing can be enabled or disabled via `Config.WORKSPACE_AUTHORITATIVE` without breaking legacy `SessionState`. | Regression test run with flag set to False and True | 100% backward compatibility maintained. | `PENDING_EXECUTION` |
| **AC-08** | Full Local Regression Suite | The entire repository test suite must remain completely green. | `../.venv/bin/python -m pytest` | 1,834+ tests pass without regression. | `PENDING_EXECUTION` |
| **AC-09** | Quality Tooling & Complexity Gate | All configured code quality gates, pre-commit hooks, static analysis, and mutation tests must pass cleanly. | `pre-commit run --all-files`, `radon cc app/ --min D -s`, `radon mi app/`, `mypy app`, `mutmut run`, `bandit -r app/ -c pyproject.toml`, `ruff check .`, `ruff format --check .`, `codespell` | Zero pre-commit failures; zero Radon D/E/F cyclomatic complexity findings; zero Mypy type errors; zero mutation test survivors on critical logic; zero Bandit security warnings; zero Ruff/Codespell errors. | `PENDING_EXECUTION` |

---

## 2. Remote GPU Acceptance Criteria (RTX 2060 Super 8GB)

These criteria evaluate live runtime and timing characteristics on the connected GPU server once powered online tomorrow:

| ID | Category | Requirement | Validation Method | Threshold / Expected Outcome | Status |
|---|---|---|---|---|---|
| **AC-GPU-01** | Cognitive Commit Latency | Adding workspace CAS commits and percept envelope normalization must not introduce meaningful latency on live LLM streaming. | Measure p50 and p95 turn latency on Ollama with live model streaming (`qwen2.5:3b` / `llama3.2:3b`). | CAS commit overhead $\le 5$ ms (p95); total TTFT regression $\le 10$ ms. | **PENDING_GPU — server expected online tomorrow** |
| **AC-GPU-02** | Live Barge-In Truncation | When an audio stop signal is received during live voice playback, actual acoustic playback is halted and an `OutcomeRecord` is logged with exact heard characters. | Stream live TTS output to `voice-agent`, issue `audio.stop`, measure truncation offset against audio playback progress. | History truncated exactly at heard offset; `OutcomeRecord(status='TRUNCATED')` emitted within $\le 50$ ms. | **PENDING_GPU — server expected online tomorrow** |
| **AC-GPU-03** | Longitudinal State Stability | 20 consecutive live conversational turns must execute without memory growth, state divergence, or spurious CAS conflicts. | Automated 20-turn live dialog runner against Ollama on RTX 2060 Super. | 20/20 turns complete; 20 sequential revisions committed; 0 spurious rejections; memory footprint flat. | **PENDING_GPU — server expected online tomorrow** |

---

## 3. Architecture Invariant Gates (Non-Negotiable)

* **INV-01:** Identity-bearing state must never exist only in prompt context or model weights. (Workspace must durably record active state).
* **INV-02:** Hard constraints filter before utility scoring; no affect or control signal can override boundary refusals.
* **INV-03:** Fast reflex actions (e.g. startle/stop) and slow deliberative actions update the same causal workspace.
* **INV-04:** No synthetic or placeholder benchmark numbers are permitted in result files.

