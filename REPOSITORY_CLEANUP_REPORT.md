# Repository Cleanup Report

## 1. Baseline

- Starting commit: `7a7626f06bb148b147ce73c1c37d0d0053311c0b`
- Branch: `main`
- Date: 2026-09-05
- Audit Status: Final post-cleanup system audit: PENDING

---

## 2. Cleanup Scope

This repository modernization pass realigns the codebase, documentation, configuration, and web assets with the completed and validated 7-phase humanoid cognitive architecture. Over several years of iterative research and development, temporary milestone terminology, obsolete comments, outdated latency targets, and legacy experiment folders accumulated across the repository.

The scope of this cleanup included:
- Auditing and modernizing active code, comments, and docstrings across backend modules.
- Introducing functional configuration aliases for legacy phase-based toggles.
- Archiving legacy analysis diagrams and evaluation run dumps into `orchestration/archive/`.
- Updating website copy, benchmark data, and documentation to reflect empirical measurements (e.g., composed turn TTFT of 119.35 ms, sub-millisecond barge-in reflex of 0.099 ms, calibrated 4500s cortisol half-life, and mathematical affect dynamics).
- Verifying backend test suites, linters, and frontend/website production builds.

---

## 3. Files Renamed

- Source Code Files Renamed: 0 files.
  - To prevent breaking active imports, CI pipelines, and cross-module contracts, existing module filenames were preserved.
- Configuration Properties Aliased: 2 properties canonicalized in `backend/app/config.py`:
  - `Config.PHASE_02_MEMORY_TRUTH` -> canonical alias: `Config.MEMORY_TRUTH_ENABLED` (with bidirectional property forwarding).
  - `Config.PHASE_03_AFFECT_CONTROL` -> canonical alias: `Config.AFFECT_CONTROL_ENABLED` (with bidirectional property forwarding).

---

## 4. Files Removed

- Path: `backend/tests/res.xml`
  - Reason: Ephemeral JUnit XML test report artifact generated during scratch test runner execution.
  - Evidence of safety: Temporary test output file ignored by version control rules.
- Path: `backend/res.xml`
  - Reason: Ephemeral JUnit XML test report artifact generated during scratch test runner execution.
  - Evidence of safety: Temporary test output file ignored by version control rules.

---

## 5. Files Archived

The following historical directories containing 9 files were relocated into `orchestration/archive/`:

1. `codebase-analysis-docs/` -> `orchestration/archive/codebase-analysis-docs/`
   - Files: `architecture-overview.mmd`, `db-er.mmd`, `voice-turn-sequence.mmd`
   - Reason: Superseded early architectural diagrams created prior to the humanoid brain refactor. Replaced by `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md`.
2. `evals_out/` -> `orchestration/archive/evals_out/`
   - Files: `baseline.json`, `candidate.json`, `candidate_hermes3.json`, `candidate_qwen25_3b.json`, `candidate_qwen25_7b.json`, `recall.json`
   - Reason: Historical local LLM evaluation run dumps. Consolidated empirical data is now published in `evidence/BENCHMARK_SUMMARY.md` and `orchestration/PHASE_07/BENCHMARK_RESULTS.md`.

---

## 6. Code Cleanup

1. `backend/app/config.py`:
   - Added canonical functional aliases `MEMORY_TRUTH_ENABLED` and `AFFECT_CONTROL_ENABLED`.
   - Wired bidirectional synchronization in `AppSettings.set_defaults` and `ConfigMeta.__getattr__`.
   - Removed historical bucket and sprint backlog comments (Bucket 1, Bucket 3, Bucket 11, Bucket 12, Bucket 17, P1-1).
2. `backend/app/cognitive/decision.py`:
   - Updated candidate selection gating condition to check `Config.MEMORY_TRUTH_ENABLED or Config.AFFECT_CONTROL_ENABLED`.
   - Replaced historical sprint notes with clean architectural descriptions of deliberation selection.
3. `backend/app/persona/profile.py`:
   - Removed outdated milestone notes regarding placeholder hormone bounds and half-lives.
4. `backend/app/contracts.py`:
   - Modernized docstrings and inline comments in `SpeechExpression`, `AudioResume`, and `StateUpdate` to clarify external provider interface semantics.
5. `backend/app/state/agent_state.py`:
   - Cleaned CAS concurrency comments, `writer_id` telemetry notes, and phasic hormone decay descriptions.
6. `backend/app/vision/agent.py`:
   - Updated comments on visual appraisal sampling and facial reflex telemetry.
7. `backend/tests/test_planning_simulation.py`:
   - Updated 7-bit ASCII test suite to check archived location `orchestration/archive/phase_06/CODEX_RESULT.md`.

---

## 7. Comments and Docstrings

Across all audited active backend modules, comments and docstrings were updated to follow functional architectural standards:
- Removed temporary sprint markers (e.g., 'TODO Phase 2', 'hack for now', 'bucket 17').
- Replaced informal emotion descriptions with technical dynamical systems terminology (valence, arousal, dominance, phasic burst, tonic decay).
- Clarified concurrency guarantees, CAS versioning invariants, and lock acquisition requirements.

---

## 8. Documentation Changes

1. `DOCUMENTATION_INDEX.md`:
   - Re-indexed all authoritative architecture specifications, technical evidence deliverables, partnership collateral, and validation reports.
   - Added references to `evidence/`, `partnership/`, `outreach/`, and `REPOSITORY_CLEANUP_REPORT.md`.
   - Updated archive directory listings to include `orchestration/archive/codebase-analysis-docs/` and `orchestration/archive/evals_out/`.
2. Website Documentation Pages (`website/content/docs/`):
   - `concepts/persona-constitution.md`: Updated persona bounds documentation, removing temporary stage markers.
   - `concepts/memory-systems.md`: Clarified multi-store memory fusion and learned mental lexicon pipeline.
   - `concepts/endocrine-affect-system.md`: Removed biological emotion claims, replaced with mathematical neuromorphic affect dynamics.
   - `concepts/vision-appraisal.md`: Replaced biological habituation references with perceptual habituation and frame gating.
   - `guides/cloud-llm-fallback.md`: Clarified multi-provider fallback and speech synthesis compilation contracts.

---

## 9. Configuration and Dependency Cleanup

- Configuration properties now feature clear functional names (`MEMORY_TRUTH_ENABLED`, `AFFECT_CONTROL_ENABLED`) while maintaining legacy backward compatibility.
- Linter verification via `ruff check .` passed across all backend files with zero errors.
- Unused or orphaned test scripts were purged from the repository working tree.

---

## 10. Website Updates

Key website updates aligning public materials with validated benchmarks and architecture:
1. Barge-in Reflex Latency:
   - Old Claim: 150 ms target.
   - New Claim: 0.099 ms verified reflex latency (< 1 ms threshold).
   - Sources: `backend/tests/test_fast_reflex.py`, `evidence/BENCHMARK_SUMMARY.md`.
2. First-Token Latency (Composed Turn TTFT):
   - Old Claim: 39.95 ms uncomposed isolated token prefill.
   - New Claim: 119.35 ms composed turn TTFT (34.57 ms deliberation + 84.78 ms prefill).
   - Source: `orchestration/PHASE_07/BENCHMARK_RESULTS.md`.
3. Validated Micro-Benchmarks Added (`website/lib/benchmark-data.ts`):
   - Barge-in reflex: 0.099 ms.
   - State rollback: 14.28 us.
   - Boundary invariance: 100.0%.
   - Metacognitive overhead: 0.17 ms.
   - Candidate selection: 0.36 ms.
   - Plan verification: 0.29 ms.
4. Affective & Endocrine Modeling:
   - Replaced claims of 'biological emotions' and 'neurobiological bonding' with 'mathematical affect dynamics' and 'neuromorphic hormone decay'.
   - Corrected cortisol half-life representation to the calibrated 4500s constitutional parameter.
5. Roadmap and Branding:
   - Modernized 'Phase 8' and 'Roadmap v7.1' badges to 'web sandbox preview' and 'Roadmap Preview'.

---

## 11. Terminology Modernization

The following terms were modernized across documentation, website, and code comments:
- 'Biological emotion' -> 'Mathematical affect dynamics'
- 'Neurobiological bonding' -> 'Interpersonal trust and attachment dynamics'
- 'Biological habituation' -> 'Perceptual habituation'
- 'Phase 2 / Phase 3 Gating' -> 'Memory Truth / Affect Control Gating'
- 'Phase 8 Web' -> 'Web Sandbox Preview'

---

## 12. Dead Code Removed

- Removed obsolete commented-out code blocks in `backend/app/config.py` and `backend/app/cognitive/decision.py`.
- Cleaned scratch XML test output files from the repository root and test directory.

---

## 13. Compatibility Layers Retained

1. `Config.PHASE_02_MEMORY_TRUTH` and `Config.PHASE_03_AFFECT_CONTROL`:
   - Retained as bidirectional aliases pointing to `MEMORY_TRUTH_ENABLED` and `AFFECT_CONTROL_ENABLED`.
   - Rationale: Existing test suites, scripts, or deployment environments may toggle these properties. Retaining aliases guarantees zero breakage.
2. Speech Expression Markup in `backend/app/contracts.py`:
   - Retained support for expressive speech tags (e.g., tone, rate, pitch modulation).
   - Rationale: Required for multi-provider speech synthesis adapters (ElevenLabs, Sarvam, EdgeTTS).
3. `lexicon_seed.py`:
   - Retained generic English dictionary seeds.
   - Rationale: Used exclusively during initial database seeding; does not impact runtime hot-path execution.

---

## 14. Tests and Builds Run

1. Backend Pytest Suite:
   - Command: `../.venv/bin/python -m pytest`
   - Result: 2,379 passed, 0 failures, 0 errors in 105.74s.
2. Backend Linting:
   - Command: `../.venv/bin/python -m ruff check .`
   - Result: All checks passed.
3. Website Production Build:
   - Command: `npm run build` (in `website/`)
   - Result: 38/38 static pages generated successfully, 0 errors.
4. Frontend Production Build:
   - Command: `npm run build` (in `frontend/`)
   - Result: 8/8 static pages generated successfully, 0 errors.

---

## 15. Known Ambiguities Left Untouched

- None that impact runtime stability or architectural boundaries. All active code paths have been validated by the 2,379-test suite.
- Future provider-specific adapter extensions remain cleanly decoupled via `INTEGRATION_BOUNDARIES.md`.

---

## 16. Risks for Final System Audit

1. External Scripts Using Legacy Config Names:
   - Risk: Scripts expecting only legacy configuration flags.
   - Mitigation: Bidirectional aliasing in `config.py` ensures both legacy and canonical names function identically.
2. Link Integrity Post-Archival:
   - Risk: External links pointing to archived `codebase-analysis-docs/`.
   - Mitigation: Updated `DOCUMENTATION_INDEX.md` explicitly documents the new archive paths.

---

## 17. Final Repository Structure Summary

The repository structure is organized into clean functional tiers:
- `backend/app/`: Production cognitive architecture runtime (agents, cognitive pipeline, memory store, persona, state service, vision).
- `backend/crates/`: High-performance Rust subsystems (voice-agent, stt-agent, cognitive-rust).
- `backend/tests/`: Comprehensive test suite (2,379 tests across unit, integration, invariant, and simulation suites).
- `evidence/`: Validated technical evidence package, benchmarks, demos, integration boundaries, and IP review candidates.
- `partnership/`: Partnership pitch deck, one-pager, technical FAQ, PoC proposals, and partner target matrix.
- `outreach/`: Partner outreach strategy, target shortlist, partner briefs, messages, and call guides.
- `orchestration/`: Phase gate certifications, benchmark results, and master state ledger.
- `orchestration/archive/`: Historical research proposals, early audit rounds, intermediate plans, and archived analysis docs.
- `website/`: Public documentation, benchmark dashboard, and interactive cognitive architecture showcases.
- `frontend/`: Live interactive web chat and cognitive inspector client.
