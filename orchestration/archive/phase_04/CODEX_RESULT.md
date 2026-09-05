# Phase 04 Package A Result

## Deliverables

- Added `PersonModel` with person-indexed knowledge, disclosures, preferences,
  obligations, reliance-grounded competence and benevolence trust, and
  asymmetric rupture and repair history.
- Enforced hard cross-person privacy isolation: private facts may only be
  disclosed to their owning person, independent of trust.
- Added domain Brier calibration and deterministic metacognitive directives:
  PROCEED, HEDGE, ASK_CLARIFICATION, VERIFY, and ABSTAIN.
- Added AgentState person and capability fields. StateService creates an active
  person model on demand and mirrors its competence and benevolence values to
  legacy scalar fields under the state lock.
- Added focused social and metacognitive regression coverage.

## Verification

- `../.venv/bin/python -m pytest tests/test_social_metacognition.py`: 12 passed.
- `DEBUG=false ../.venv/bin/python -m pytest tests/test_social_metacognition.py
  tests/test_state.py tests/test_phase3_features.py -q --junit-xml=...`:
  36 tests, 0 failures, 0 errors, 0 skipped.
- `../.venv/bin/python -m ruff check .`: passed.
- `../.venv/bin/python -m radon cc app --min D -s`: no D-or-higher functions.
- `git diff --check` and the Phase 04 source/test ASCII byte scan passed.
- Mutation check: replacing the rupture multiplier of `1.5` with `0.5` made
  `test_rupture_and_repair_asymmetry` fail. The required multiplier was restored.

## Not Done

Persistent person-model storage, outcome-event wiring outside StateService,
runtime action integration, remote CI, and GPU benchmarks are outside this
Package A task scope.

## Fix Round: Peer Review Findings

### Delivered

- Removed the eager calibration import from `agent_state.py`. The capability
  model is now created by a deferred factory, so the state suite imports and
  runs independently.
- Added locked `set_active_person()` and `get_active_person_model()` APIs.
  Person selection, lazy seeding, and direct legacy active-person changes now
  synchronize the scalar competence and benevolence mirrors while holding the
  state lock.
- Hardened capability limitation matching against blank entries. Hardened
  person trust methods against NaN and infinite numeric input, normalized and
  validated rupture/repair kinds, and made unowned private facts fail closed.
- Added regressions for the isolated state suite, active-person mirror sync,
  blank limitations, non-finite inputs, invalid rupture kinds, and unowned
  private-fact disclosure.

### Verification

- `DEBUG=false ../.venv/bin/python -m pytest tests/test_state.py -q`:
  20 passed.
- `DEBUG=false ../.venv/bin/python -m pytest
  tests/test_social_metacognition.py -q`: 22 passed.
- `../.venv/bin/python -m ruff check .`: passed.
- `../.venv/bin/python -m radon cc app --min D -s`: no D-or-higher functions.
- `git diff --check` and the Phase 04 source/result ASCII scan passed.
- Mutation check: disabling the reliance finite-input guard made all three
  NaN/Inf/-Inf regression cases fail. The intended guard was restored.

### Not Done

Remote CI, GPU benchmarks, persistent person-model storage, and runtime action
integration remain outside this Package A fix-round scope.
