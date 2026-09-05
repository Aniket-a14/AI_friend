# Codex Review of Claude Phase 01

Target: `bad24de3c93b88cbeb52e6b556eda292d4e4c5ea`

Baseline: `bb5be86ba7c14ab7f8afa056707597a37d3bdd86`

## Findings

### BLOCKER-01 — Production turns never receive a percept or workspace revision

Evidence:

- `backend/app/cognitive/core.py:423-425` calls `pipeline.execute()` with only
  `raw_event` and `surfaced_memories`; it does not pass `percept=` or
  `workspace=`.
- `backend/app/agents/brain_agent.py:590` and `:854-915` only assign the new
  envelopes to the single mutable `last_percept` slot. They never thread the
  envelope into `CognitiveService.process_event()`.
- `backend/app/cognitive/pipeline.py:492-503` consequently writes
  `percept_id=None` and `(workspace_epoch, workspace_revision)=(0, 0)` on the
  normal production path.
- `backend/app/cognitive/pipeline.py:641-647` yields an `ActionIntent`, but
  performs no workspace transition or CAS commit.

The `WorkspaceSnapshotLike` protocol itself is structurally compatible with
Codex's `CognitiveWorkspaceSnapshot` (`epoch` and `revision` are present), so
the interface shape is fine. The missing wiring is integration work in terms of
ownership, but it is a blocker for the Phase 01 completion gate: a live turn
does not cite the workspace revision from which it was derived and does not
enter cognition through the normalized percept path. The `(0, 0)` fallback is
useful for backward-compatible unit callers, but cannot be the production
trace.

### BLOCKER-02 — Action and outcome records are diagnostic-only, not emitted or stored

Evidence:

- `backend/app/cognitive/pipeline.py:647` emits an in-process async-generator
  chunk only.
- `backend/app/agents/brain_agent.py:394-409` constructs an outcome, assigns it
  to one `_last_outcome_record` field, and logs it. There is no durable store,
  append-only audit write, or mesh publication.
- A second outcome overwrites the first, and process restart discards both the
  active intent and the outcome.

The plan requires the `ActionIntent`/`OutcomeRecord` trace to be emitted and
stored, and Section 39 requires an appendable causal record usable by later
evaluation. In the current implementation a downstream evaluator cannot
recover a completed or interrupted trace after the handler returns. This is
also why the records cannot yet support duplicate/reordered delivery or restart
recovery claims.

### BLOCKER-03 — The normal playback path never produces `COMPLETED`

Evidence:

- `backend/app/agents/transport_agent.py:503-509` creates and publishes every
  playback progress event with `completed=False`.
- `backend/app/agents/transport_agent.py:406-407` handles the end of the NATS
  audio stream by logging `AI Utterance stream complete`; it does not publish a
  terminal `AudioPlaybackProgress` event.
- The only completion hook is
  `backend/app/agents/brain_agent.py:871-882`, which requires a
  `completed=True` progress event.

Therefore a normal full voice turn reaches transport stream completion without
calling `_emit_outcome_record(status="COMPLETED")`. The added completion test
passes only because it injects a terminal progress event that the real
transport does not send. This leaves ordinary foreground actions without a
terminal outcome, violating the causal-trace and completion invariants.

### HIGH-01 — A completed outcome records generated length, not playback offset

Evidence:

`backend/app/agents/brain_agent.py:876-882` sets
`character_offset=len(delivered)` and stores the entire generated response,
ignoring `progress.character_offset`. The shared contract defines the offset as
the playback position (`backend/app/contracts.py:464-471`).

If a terminal progress event reports an offset different from the generated
string length (for example because a final chunk was queued, normalized, or
partially drained), the record claims more text was heard than the playback
event reports. The test uses equal values and cannot distinguish this bug. The
completion branch should use the validated progress offset and derive the
delivered prefix consistently with the truncation path.

### HIGH-02 — Several cancellation paths bypass terminal outcome recording

Evidence:

- `backend/app/agents/brain_agent.py:556-574` directly cancels the prior
  generation in `_replace_active_generation`; it does not call
  `_cancel_active_generation` or emit an outcome.
- This is a real foreground path: the `confirmed_user_speech` stop returns
  early at `:920-924` specifically so the new turn is not cancelled, after
  which `_replace_active_generation` cancels the old turn.
- Even when `_cancel_active_generation` is used,
  `backend/app/agents/brain_agent.py:450-454` can only emit if an active intent
  has already been captured. That capture occurs later at `:1227-1237`, after
  the pipeline has completed its earlier perception/appraisal/decision awaits.
- The pipeline itself returns before Stage 6 on the VAP abort and confirmed
  conflict paths (`backend/app/cognitive/pipeline.py:551-575`).

Consequently, a user barge-in during an in-flight pre-commit decision, or a
new chat input that replaces an old generation, can cancel work after the
state reset while producing no `CANCELLED`/`TRUNCATED` record. The test seeds an
already-captured intent and therefore does not exercise either race. Cancellation
must be tracked per turn and every cancellation owner must close or explicitly
record the corresponding causal state.

### MEDIUM-01 — Non-finite confidence can become maximum confidence

Evidence: `backend/app/cognitive/percept.py:53-58` converts arbitrary input to
`float` and clamps with `max/min`, but does not reject non-finite values. In
Python, `_clamp_confidence("nan", default=0.9)` returns `1.0`, so malformed
sensor metadata is treated as maximally reliable rather than falling back or
failing closed. The tests cover numeric bounds and non-numeric strings, but not
NaN or infinity. Use an explicit `math.isfinite()` check before clamping.

### MEDIUM-02 — Percept IDs are not stable across redelivery

Evidence: `backend/app/cognitive/percept.py:49-50` generates a fresh UUID for
every converter call, and each converter calls it unconditionally. Replaying
the same `chat.input`, stop, or vision event therefore creates a different
`percept_id`; the raw event's available `utterance_id`/`turn_id` is not used as
an idempotency key.

The Phase 01 architecture explicitly requires duplicate/reordered delivery
experiments and an auditable causal trace. With fresh IDs on redelivery,
downstream workspace or outcome code cannot distinguish a duplicate from a new
observation and may admit it twice. Preserve a source event ID when available
and derive or carry a stable fallback identity at the adapter boundary.
