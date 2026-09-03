# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Read this first

`.agents/CONTEXT.md` is the project's engineering ledger and the best source of ground truth — it records what was actually built, what was measured, and what was deliberately left undone. **Read it before making architecture or behavior changes, and append an entry after every meaningful one.** Existing entries show the expected style: what changed, why, how it was verified, and an explicit "NOT done" section.

The polished `README.md` overstates completeness relative to the ledger. Where they disagree, the ledger is right.

## Commands

The virtualenv lives at the **repo root** (`.venv`), but pytest must run from
`backend/`. Development moved to macOS in 2026-08, so macOS is the primary
column below; Windows still works unmodified underneath it — the interpreter
path is the only thing that differs by host, and nothing in the codebase
branches on OS, so picking the right block for your platform is the whole
adjustment, no config edit required:

```bash
cd backend

# macOS / Linux
../.venv/bin/python -m pytest                      # full suite
../.venv/bin/python -m pytest tests/test_foo.py     # one file
../.venv/bin/python -m pytest tests/test_foo.py::test_name   # one test
../.venv/bin/python -m pytest -k "somatic and not vision"    # by expression
../.venv/bin/python -m ruff check .                 # lint (CI gate)

# Windows
../.venv/Scripts/python.exe -m pytest
../.venv/Scripts/python.exe -m pytest tests/test_foo.py
../.venv/Scripts/python.exe -m pytest tests/test_foo.py::test_name
../.venv/Scripts/python.exe -m pytest -k "somatic and not vision"
../.venv/Scripts/python.exe -m ruff check .
```

Rust workspace (`backend/crates/`) and the native extension:

```bash
cd backend
cargo check --workspace
cargo test --workspace
maturin build --manifest-path crates/cognitive-rust/Cargo.toml --out target/wheels
```

Frontend (`frontend/`): `npm run dev` | `npm run build` | `npm run lint`.

Infra for integration work:

```bash
docker compose -f docker-compose.infra.yml up -d
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml up
docker compose -f docker-compose.prod.yml --profile vision up   # vision is opt-in
```

### Getting a reliable test count

Pytest's terminal summary is unreliable here — the final `N passed in ...s`
line (and, when something fails, the whole `=== FAILURES ===` section) is
frequently swallowed, so a run can look clean when it is not. Originally
documented as a Windows-terminal quirk; **verified 2026-08-21 to reproduce
identically on macOS**, including with output redirected straight to a file
(not just an interactive terminal), which rules out terminal truncation as the
cause — `pytest-benchmark`'s session-finish hook (the `Saved benchmark data
in: ...` line) prints where the summary should be, and the summary itself
never appears, on either host. Do not trust the dots. Use:

```bash
../.venv/Scripts/python.exe -m pytest -q --junit-xml=<scratch>/res.xml
# then parse tests/failures/errors from the XML
```

To see a traceback that pytest is eating, import the failing test directly in a small script, wrap it in `try/except BaseException` with `traceback.print_exc()`, redirect to a file, and read the file.

## Architecture

### The mesh

Agents are separate processes coordinated over **NATS JetStream**, not function calls. `backend/app/agents/` holds `brain_agent` (the cognitive turn), `system_agent` (ticks, decay), `subconscious_agent` (background reflection, Neo4j persistence), `surfacing_agent`, and `transport_agent` (LiveKit WebRTC). Voice and STT are **Rust** binaries (`backend/crates/voice-agent`, `stt-agent`); their Python predecessors have been retired and removed.

`backend/app/contracts.py` defines the Pydantic models that cross agent boundaries. Changing a contract means also running `backend/scripts/bootstrap/setup_nats_streams.py`.

**Ack model matters here.** `BaseAgent.subscribe` acks only after the callback returns, and a cognitive turn can run to `LLM_STREAM_MAX_SECONDS` (120s), well past JetStream's default AckWait — see finding A1 in the ledger before touching long-running consumers.

### The cognitive turn

`cognitive/pipeline.py` → `cognitive/core.py` → `cognitive/action.py`. Appraisal produces a plan; `ActionService.execute` streams the response, strips `<thought>` chain-of-thought incrementally across chunk boundaries, sanitizes control markup, validates against identity boundaries, and can trigger a self-correction retry pass.

The `<thought>` parser is a genuine incremental parser with partial-token hold-back — a naive `split()` leaks the entire reasoning block when the LLM emits `<`, `thought`, `>` as separate tokens, which is the common case, not an edge case.

### State is single-owner

`state/agent_state.py` holds `AgentState` (a `slots=True` dataclass: PAD affect, Marsh trust, attachment, fatigue) and `StateService`, which owns **all** mutation behind `self._state_lock`. A fire-and-forget System-2 appraisal task writes concurrently with the synchronous path, so bypassing the lock reintroduces finding A2. Route new affect changes through a `StateService` method rather than touching `current_state` fields directly.

**Endocrine layer.** `cortisol`, `dopamine`, and `fatigue` are injected into the plan payload by `cognitive/core.py` and mapped to LLM sampling parameters in `action.py::_compute_endocrine_options` — cortisol narrows temperature, dopamine widens top_p, fatigue shortens `num_predict`.

Both hormones are tonic + phasic, and the symmetry is the point. `dopamine_tonic` (valence × arousal) and `cortisol_tonic` (inverse valence plus a fatigue term) are pure functions of current affect and so have no memory. Each carries a decaying burst on top — `dopamine_phasic` / `cortisol_phasic`, fired by `release_dopamine()` / `release_cortisol()` and stored as a peak plus a release timestamp, so the level is derived from elapsed time rather than needing a tick to decay it.

Two consequences worth knowing before touching this. The tonic terms are perfectly anti-correlated by construction (both functions of valence, one rising exactly as the other falls), so **only the phasic channels let the agent be stressed and rewarded at once** — bypassing them collapses that back. And burst peaks are computed *relative to the tonic floor*, so releases must go through the `StateService` wrappers, which hold `_state_lock`: an unlocked release interleaving with a valence write measures its peak against a floor that no longer exists. Half-lives (`dopamine_halflife_s` 90s, `cortisol_halflife_s` 600s) are CONSTITUTIONAL persona fields, not deployment settings — how long a reward glows and a fright lingers is temperament. Bursts are deliberately **not persisted**: minutes-scale decay means a restart would restore a value that no longer means anything.

### Memory

`state/memory_store.py` is the largest and riskiest file (~2600 lines). `search_memories` fuses an L1 cache, Qdrant vectors, Neo4j graph boost, Postgres/SQLite candidates, PageRank, and cue expansion. Retrieval uses a **learned mental lexicon** (`lexicon_store.py`), built from the agent's own conversation — not a hardcoded thesaurus. The innate seed in `lexicon_seed.py` is generic English used once at DB seeding, never on the hot path.

**Dual backend.** Nearly every query has a Postgres and a SQLite branch. `MemoryStore.is_sqlite` is a read-only property (there is no setter — see A5); to force SQLite in a test, give the pool a real `sqlite3` connection instead of assigning to the property.

### Persona and identity

Two sources, not yet unified:

- `cognitive/identity.py` (`IdentityManager`) loads `personality.json` / `history.json` — the **narrative** persona (name, values, tone, boundaries, adaptive traits). It already distinguishes an immutable core from adaptive traits that evolve through reflection, capped at 5.
- The **numeric** persona lives in `persona/profile.py` (`PersonaProfile`), injected into `StateService.__init__`. `Config` now only supplies defaults.

`PersonaProfile` sorts every field into one of three tiers, declared in the schema so the boundary is enforceable rather than conventional: **IMMUTABLE** (safety invariants — deliberately *not* model fields; they live in `IMMUTABLE_CORE` and a persona file naming them is rejected with a warning), **CONSTITUTIONAL** (temperament, fixed at creation), **ADAPTIVE** (seeded by the user, then owned by the agent). Bounds are tighter than the maths permits, each guarding a specific failure mode — `mood_decay_rate > 0` because zero is a permanent mood lock, `baseline_valence` capped at ±0.6 because a friend pinned at maximum can never be sad *with* you. The rule is that a personality may be shaped but must remain moveable.

Loading is deliberately asymmetric: `load()` (authored file) validates strictly and falls back *whole*, since half-applying a persona hands its author a friend they did not describe; `from_config()` clamps with a warning, since a running deployment should not fail to boot because bounds arrived.

`config.py` is a process-global Pydantic-settings singleton reached through a metaclass (`Config.FOO` delegates to `config_instance`). Prefer `@computed_field` properties over adding logic to `ConfigMeta.__getattr__` (F4).

## Conventions

**Branch and PR per change.** Feature branch off `main`, PR to `main`. When merging, **retarget any stacked PR before deleting a base branch** — deleting a base auto-closes PRs targeting it, and a closed PR cannot be reopened or retargeted once its base is gone.

**Verification bar.** Full backend suite plus `ruff check .` before considering work done. New tests are expected to be **mutation-tested**: deliberately break the code they cover and confirm they fail. This repeatedly catches tests that pass for the wrong reason — a mutation that changes nothing observable usually means the assertion targets state the test could never distinguish.

**Test names state the failure, not the number** (`test_mood_decay_cannot_be_zero`, not `test_bounds`). Tests carry docstrings explaining what breaks in the real system if the assertion fails.

## CI gotchas

- **Credential Leak Prevention** greps for `(password|secret|api_key)\s*=\s*['"][^'"]{8,}['"]` across the whole repo with **no test-directory exclusion**. A test variable named `secret = "..."` fails the build; rename the variable rather than loosening the check.
- **Persona Guard** runs on changes to `cognitive/**`, `vision/**`, `brain_agent.py`, `persona/**`, the identity seeds (`personality.json` / `history.json` / `config/persona.toml`), and the frontend identity seed. It boots a real NATS container.
- **Workflows are path-filtered**, so PR check counts legitimately differ. A PR based on a non-`main` branch runs almost nothing and CodeRabbit skips it entirely — a green check on such a PR means "nothing ran," not "nothing wrong." CodeRabbit also reports the check as *passed* when it hit its review-rate limit; read the actual comment.

## Behavioral eval harness

`backend/evals/` answers "did this model + persona change behavior between two
runs?" — the gate Fine-Tuned Adapter's consolidation loop needs before any fine-tuned adapter
can be adopted. It probes the **LLM boundary only** (real persona prompt, real
`OllamaClient`, sampling pinned, mood frozen), because that is the seam a LoRA
adapter changes.

```bash
cd backend
python -m evals run --model <tag> --out evals/out/baseline.json
python -m evals compare evals/out/baseline.json evals/out/candidate.json --fail-on-regression
python -m evals run-conversation --model <tag> --num-ctx 8192 --out evals/out/recall.json
```

`run-conversation` is the multi-turn suite: a fact planted early, asked about
after N scripted filler turns, under two context strategies. It probes the same
LLM boundary but answers a different question — *does a fact survive distance*.
Two failure modes are surfaced rather than scored, because both make the number
meaningless rather than merely low: `plant out` (the strategy never showed the
model the fact) and `fits NO` (the context exceeded `num_ctx`, and Ollama
truncates from the front, which is where the plant sits — `OllamaClient`
defaults it to 2048, so the harness pins it).

Three rules hold it together: **nothing in `app/` may import from `evals/`** (the
dependency points one way); **scoring is deterministic**, never an LLM judge, so
a given response always yields the same verdict; and **reports carry provenance**,
with both subcommands refusing mock-sourced data as evidence unless `--allow-mock`
is passed. A regression is pass→fail on a probe, not a score threshold.

Deterministic scoring does **not** make the gate reproducible on its own — the
*response* has to be reproducible too, and on `qwen2.5:3b` it was not: two runs
with byte-identical prompts and pinned sampling differed on 3 of 16 probes and
flipped two verdicts. The fix was to stop leaving the runtime's starting state
implicit — both suites now **unload the model, reload it and burn one throwaway
generation** before the first scored probe (`runner.reset_model_state`), after
which three consecutive runs were identical on every probe. Reports also carry
the sampling options and a digest of the system prompt, so `compare` can say
when two runs were not configured alike instead of diffing them as though they
were.

## Integrity constraints

`MOCK_LLM_TEXT=true` returns hardcoded strings fitted to a specific demo corpus — anything measured under it is not evidence. Some documented benchmark results remain genuine **placeholders** (`[TBP]`) and must stay labeled that way until a real run backs them.

**Corrected 2026-09-01**: this section used to state flatly that no headline latency or Recall@K figure had been measured against real infrastructure. That is no longer accurate for every number in the repo — the historical Hermes 3 8B benchmark run (61.9 ms TTFT, 46.6 tok/s, real Colab GPU, `MOCK_LLM_TEXT` not forced true) and its Recall@K figures (81.8/87.5/87.5/93.2% at K=1/3/5/10) were independently recomputed from the raw per-sample arrays in `scripts/results/hermes3_benchmark_results.json` and sibling files, and matched the summary exactly (`.agents/CONTEXT.md`, 2026-07-18 entry) — those are real. What remains true, and is the actual point of this constraint: those numbers came from that run's own one-off benchmark corpus, not a reference corpus that generalizes across deployments — **production personas on `main` are authored per-deployment by design, so there is no shared corpus to compute a fresh Recall@K or realism figure against for an arbitrary running instance.** Treat any historical benchmark number as evidence about that specific run, never as a property of "the system" in general. Do not present a number without its provenance line, and do not add corpus-specific constants to production retrieval paths (finding B1). State targets as targets until measured, and measured-but-corpus-specific results as exactly that.
