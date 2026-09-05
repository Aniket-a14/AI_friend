# Claude Cleanup Result — Repository-Wide Modernization Pass

## 0. Scope and Branch

This round picked up after Gemini's repository-wide cleanup pass
(`REPOSITORY_CLEANUP_REPORT.md`) and covered the semantic/documentation/
public-content side only: stale comments and docstrings, README/docs
modernization, broken links, terminology consistency, and website copy
traced back to current evidence.

**Isolation note:** at the start of this round there was no dedicated Claude
cleanup worktree or branch — only a single worktree existed, checked out on
`main`, already carrying Gemini's full uncommitted diff plus an untracked
`REPOSITORY_CLEANUP_REPORT.md`. Per the user's direction, a new branch
(`claude/repo-cleanup`) was created off that state before any further edits,
so `main` itself was never touched and stays clean at its prior commit.
Everything described below (Gemini's prior diff plus this round's changes)
lives on `claude/repo-cleanup`.

## 1. Documentation Changed

- `README.md`:
  - Removed two stale references to an "overlap-add crossfade" prosody DSP
    stage. `backend/app/agents/context.md` §3 (corrected 2026-09-01) records
    that this mechanism was deleted entirely — it re-played already-streamed
    audio at a phase discontinuity — and replaced with a clean chunk-boundary
    join. Both the "What makes it different" bullet and the "Core cognitive
    models -> Prosody" bullet described behavior the code no longer has;
    reworded both to match the current implementation.
- `CLAUDE.md`:
  - `cortisol_halflife_s` was documented as 600s; the actual constitutional
    default in `backend/app/persona/profile.py:197` and
    `backend/app/state/agent_state.py:129` is 4500s. `.agents/CONTEXT.md`
    (Bucket 11, 2026-07-xx entry) records that 600s was measured 6-9x too
    fast and was raised deliberately. Updated the number and added a one-line
    pointer to the ledger entry so the "why" travels with the fact.
  - `state/memory_store.py` was documented as "~2600 lines"; it is currently
    4482 lines (`wc -l`). Updated to "~4500 lines."
  - Spot-checked other numeric/reference claims in `CLAUDE.md` against
    current code and the ledger (`LLM_STREAM_MAX_SECONDS` = 120,
    `baseline_valence` bounds ±0.6, adaptive-trait cap of 5, findings
    A1/A2/A5/B1/F4 all present in `.agents/CONTEXT.md`) — all still accurate,
    no further changes.
- `website/content/docs/concepts/speech-voice-pipeline.md`:
  - "renders a pulsing biological aura" -> "renders a pulsing aura." The
    component is a UI glow effect, not a biological process; the word
    invited a reading this project's own integrity constraints rule out
    (no unsupported biological/human-equivalence claims).

## 2. Website Content Updated

- `website/app/page.tsx`: `ComingSoonOverlay` still had
  `title="COMING SOON — ROADMAP v7.1+"` even though the badge above it had
  already been modernized to "ROADMAP PREVIEW" earlier in Gemini's pass —
  the sweep missed this second, separate occurrence. Changed to
  "COMING SOON — ROADMAP PREVIEW" for consistency and to drop an invented
  version number nothing in the repo substantiates.
- `website/app/research/page.tsx`: "neurobiological simulation equations" ->
  "affect-dynamics equations." Same integrity-constraint reasoning as above
  — the math in question is PAD/endocrine dynamics, not neurobiology.
- `website/lib/showcase-data.ts`: the `CompanionRecipe.category` union type
  still listed `"Biological Bonding"` as a literal, but the one recipe that
  used to carry that category had already been renamed to
  `"Affective Dynamics"` earlier in Gemini's pass (see the recipe at
  `id: "affective-mood-dynamics"`). That left the type out of sync with its
  own data — `tsc --noEmit` still passed only because nothing else
  referenced the stale literal, but it was a live inconsistency waiting to
  surface the next time someone added a recipe using the old name. Updated
  the union to `"Affective Dynamics"` to match the data.

## 3. Old Claims Removed or Corrected

See §1 and §2 above. Every website/public numeric claim this round touched
was traced to current evidence per the priority order given (validation
report -> benchmark results -> architecture doc -> current
implementation/config -> evidence package -> published research):

- Cortisol half-life: verified against `backend/app/persona/profile.py`
  (current implementation) and `.agents/CONTEXT.md` Bucket 11 (why it
  changed).
- `memory_store.py` line count: verified directly (`wc -l`).
- "150ms" appearing in several website docs (`architecture.md`,
  `speech-voice-pipeline.md`, `cognitive-turn-flow.tsx`, `showcase-data.ts`)
  was checked against `evidence/BENCHMARK_SUMMARY.md` and
  `backend/crates/stt-agent/src/main.rs` — this is silence-endpointing /
  speculative-intent latency, a real and distinct measurement from the
  0.099ms barge-in *reflex* latency Gemini's pass added elsewhere. Left
  unchanged; it is not stale, it is a different metric.
- "39.95ms" appearing in `website/lib/changelog-data.ts` was checked against
  its surrounding changelog entry (dated, paired with "1,412 passing" tests
  — an old release's own metrics block) — correctly scoped as historical
  changelog content, not a current headline claim. Left unchanged.

## 4. Comments/Docstrings Cleaned

None beyond the doc-level fixes above. A repo-wide sweep for outdated
markers (`TODO`/`FIXME`/`HACK`/`XXX`, "bucket N", "sprint", "phase N")
outside `orchestration/archive/` turned up very little live noise (3 TODO-
adjacent hits, one of which — `backend/app/agents/base.py:429` — is a
substantive note about a `nats-py` library limitation, not a stale marker).

The large population of `# Bucket N (VOICE_REMEDIATION_PLAN.md)` /
`(voice remediation Phase 3)` comments across `brain_agent.py`,
`memory_store.py`, `agent_state.py`, `transport_agent.py`,
`subconscious_agent.py`, and the corresponding tests was deliberately
**left untouched**. These are not stale phase-wording in the sense this
task targets — each one documents *why* a specific non-obvious fix exists
(a real bug, a race, a mislabeled unit), which is exactly the category this
task's instructions say to preserve. `VOICE_REMEDIATION_PLAN.md` itself is a
local, gitignored planning doc (never tracked in this repo — confirmed via
`git log --all -- VOICE_REMEDIATION_PLAN.md`, no history), so these are
historical rationale citations, not broken doc links. Rewriting dozens of
these across this many files also risked exactly the kind of
"rewrite working code merely for style" this task says not to do.

## 5. Links Repaired

None needed. Checked all links in `README.md`, `AGENTS.md`, `CLAUDE.md`,
`DOCUMENTATION_INDEX.md`, `.agents/CONTEXT.md`, `evidence/`, `partnership/`,
`outreach/`, `orchestration/` (excluding `orchestration/archive/`, which is
intentionally historical and out of scope), and `website/content/docs/`.
Zero broken links in active/maintained documentation. (A handful of
apparent misses in `orchestration/archive/` — root-relative paths and
`file://` URIs no longer resolving from their archived location — are
expected of archived historical documents and were left alone.)

## 6. Validation / Build Results

- `cd website && npm run build` — Next.js 16.2.0, Turbopack: compiled
  successfully, 38/38 static pages generated, 0 errors. Confirms
  Gemini's report's website-build claim independently.
- `npx tsc --noEmit` (website) — exit 0, no type errors. Note:
  `next.config`'s `typescript.ignoreBuildErrors: true` means `next build`
  itself does not enforce this — `tsc` was run standalone to actually
  verify it, given this round touched a shared TypeScript union type.
- `npx vitest run` (website) — 4 test files, 8 tests, all passed.
- Backend files already modified by Gemini's pass
  (`config.py`, `cognitive/decision.py`, `contracts.py`,
  `persona/profile.py`, `state/agent_state.py`, `vision/agent.py`,
  `tests/test_planning_simulation.py`) were not re-audited in full (out of
  this round's scope and already inventoried in
  `REPOSITORY_CLEANUP_REPORT.md`), but since this round's commit carries
  them, they were sanity-checked before committing:
  - `py_compile` on all seven files: clean.
  - `ruff check` on all seven files: all checks passed.
  - Credential-leak regex (`(password|secret|api_key)\s*=\s*['"][^'"]{8,}['"]`)
    against all seven files: no hits.
  - `pytest tests/test_planning_simulation.py` run directly with
    `--junit-xml` and parsed from XML (per `CLAUDE.md`'s own documented
    pytest-summary-unreliable gotcha, not trusted from the terminal dots):
    20 tests, 0 failures, 0 errors.
  - Full 2,379-test backend suite and full `ruff check .` were **not**
    re-run this round — no backend code was changed by this pass, only
    `CLAUDE.md`/`README.md`/website content, so re-running the full suite
    would not have exercised anything this round touched.

## 7. Ambiguous Items Intentionally Retained

- `README.md`'s "`start.sh` (roadmap Phase 1.6)" wording: `start.sh` is
  fully implemented and working, so at first glance this looks like stale
  "roadmap" phrasing. Left it — this project's convention (matching the
  `Bucket N` comments in code) is to keep the originating roadmap item
  number as provenance even after a feature ships, not just while it's
  pending. Flagging in case Gemini's inventory disagrees with that reading.
- `orchestration/archive/reports/BRAIN_ARCHITECTURE_REDTEAM_REPORT.md` and
  `BRAIN_ARCHITECTURE_REPORT.md` contain root-relative and `file://` links
  that no longer resolve from the archived location. Left untouched
  (archive is explicitly out of scope and intentionally preserved
  historical material), but noting it here in case Gemini wants archived
  docs' links normalized as a separate, explicit task.

## 8. Requiring Gemini Arbitration

- None found that block this round. The one open question is the
  `start.sh` / "roadmap Phase N.M" convention noted in §7 — if Gemini's
  inventory treats that pattern as something to modernize repo-wide, it
  should be handled as its own pass rather than folded into this one, since
  it touches many files and is a stylistic/provenance decision rather than
  a correctness fix.

## 9. Final Commit SHA

See the commit immediately following this file in `claude/repo-cleanup`'s
history (this file is written before that commit is made, so it cannot
self-reference its own SHA).
