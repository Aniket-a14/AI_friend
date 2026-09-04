# Phase 05 Codex Package A Result

Status: COMPLETE - LOCAL VALIDATION

Branch: `codex/phase-05`

Implemented the provider-neutral voice and external action boundary, then
applied the arbitrated peer-review fixes:

- Added the complete versioned Section 23 `SpeechIntent` schema and constructor.
- Legacy trajectory migration samples and averages steady-state frames at or
  after 150 ms for energy, clamped to the `SpeechDelivery` range. This avoids
  the APRA fade-in volume of 0.10 causing a validation crash.
- Compilers now declare epistemic and relationship limitations and report every
  non-default unrenderable dimension. GPT-SoVITS also reports non-neutral
  affect it cannot modulate.
- GPT-SoVITS emphasis rendering now selects non-overlapping source spans before
  inserting tags, so duplicate or overlapping emphasis cues cannot nest tags.
- Added external-action risk/reversibility authorization gates, safe simulated
  dispatch for unregistered tools, and terminal `OutcomeRecord` creation. A
  simulated result now names the missing adapter, and registered executors are
  bounded by `timeout_s`.
- Retained the stable `SpeechRelationship.register` wire field while narrowly
  suppressing Pydantic's known field-shadow warning at schema construction.
- Added focused tests covering Rust APRA trajectory migration, complete loss
  telemetry, emphasis safety, low-risk simulation, simulated outcomes, adapter
  exceptions, timeout failure, and 7-bit ASCII purity.

Local verification:

- `pytest tests/test_voice_external_action.py`: 20 passed, 0 failures, and 0
  errors (JUnit XML).
- `ruff check .`: passed.
- `radon cc app/ -s -n D`: passed; no D, E, or F functions reported.
- Mutation checks: restoring frame-0 energy, removing the simulated outcome
  message, and removing executor timeout enforcement each failed its dedicated
  focused regression; the intended implementation was restored before final
  checks.

The dedicated worktree has no `.venv`; equivalent commands used the shared
project virtual environment at `/Users/aniketsaha/Projects/AI_friend/.venv`.

Not done:

- No live cloud TTS, local synthesis service, real actuator, or NATS wiring
  was introduced. The new code is intentionally a provider and embodiment
  boundary for later integration work.
- A timed-out Python thread cannot be forcibly stopped safely. Dispatch returns
  a terminal failure at `timeout_s`; future adapters should additionally honor
  cooperative cancellation for physical side effects.
