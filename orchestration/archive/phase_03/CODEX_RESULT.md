# Phase 03 Package A Result

## Deliverables

- Added bounded immutable global controls and legacy endocrine adapters.
- Extended the legacy appraisal module with a pure AppraisalRecord reducer.
- Added atomic affect-delta to global-control updates in StateService.
- Added causal affect, content isolation, immutability, and ASCII tests.

## Fix Round

- Refresh global controls while holding the state lock after an adrenaline
  burst, so urgency_gain incorporates startle arousal immediately.
- Treat NaN and infinity control inputs as neutral before clamping, preventing
  non-finite values from becoming maximum intensity.
- Include positive arousal in exploration_budget with the Architecture Section
  10 weights: 0.15 baseline, 0.20 arousal, 0.20 valence, 0.25 prediction
  error, and 0.20 available capacity.
- Freeze AppraisalRecord.affect_delta with a read-only mapping proxy.
- Add StateService.appraise_and_apply_event(), which returns the genuine
  AppraisalRecord and controls after applying its goal-incongruence urgency,
  novelty prediction error, and affect delta.

## Verification

- `../.venv/bin/python -m pytest tests/test_causal_affect.py -v`: 10 passed.
- `../.venv/bin/python -m pytest tests/test_appraisal.py tests/test_state.py -q`:
  37 passed.
- `../.venv/bin/python -m ruff check app/cognitive/global_controls.py
  app/cognitive/appraisal.py app/state/agent_state.py tests/test_causal_affect.py`:
  passed.
- `../.venv/bin/python -m pytest -q --junit-xml=/tmp/codex_p3_fix_test.xml`:
  2,000 tests, 0 failures, 8 errors, 0 skipped. The errors are all existing
  NATS account-fixture setup failures: this environment denies binding
  `127.0.0.1` with `PermissionError: [Errno 1] Operation not permitted`.
  No assertion failure was observed.
- Mutation check: replacing the positive-arousal exploration coefficient with
  `0.00` made `test_exploration_budget_includes_positive_arousal_at_full_saturation`
  fail. The intended `0.20` coefficient was restored.
- `git diff --check` and byte scans of all changed Phase 03 code and result
  documentation passed with only 7-bit ASCII bytes.
- `git diff --check` and the focused ASCII byte scan passed.

## Not Done

Package B action-selection modulation, integration merge, remote GPU benchmarks,
remote CI, and a full NATS-enabled local test run are outside this Package A
worktree scope.
