# mac_migrations.md — context transfer, Windows → MacBook

**Written:** 2026-08-13, from the Windows laptop, on `main` @ `41a96c9`.
**Purpose:** carry everything a fresh Claude Code session on the MacBook cannot
read off the repository — the user's standing instructions, the persistent
memories, the state of work in flight, and the assets that a `git clone` leaves
behind. Once the receiving session has absorbed it, this file deletes itself
(§8).

This file is a *transfer medium*, not documentation. Nothing here should
outlive the migration, and nothing here belongs in the repository's own docs.

---

## 0. Instructions to the receiving Claude session

Do these in order. Do not skip §1 — it is the part that changes how you work,
and it is the part no file in the repo states.

1. **Read this whole file before acting on any of it.**
2. **Write the memories in §2** into your own memory directory — the path given
   in your system prompt under "Memory", *not* the Windows path this file was
   written from. One file per memory, exactly the contents given, plus the
   `MEMORY.md` index at the end of §2.
3. **Read `CLAUDE.md`, then `.agents/CONTEXT.md`** (the ledger — ~5,800 lines;
   the last three entries, from `## 2026-08-02`, are the live edge of the work).
   Where `README.md` and the ledger disagree, the ledger is right.
4. **Verify the environment** against §4 and §5, and tell the user what is
   missing before you touch anything. Several things they need do not arrive
   through git.
5. **Report** to the user: what you loaded, what is missing, what you believe
   the next task is (§7). Ask before starting it.
6. **Self-destruct** (§8) once they confirm the transfer took.

One caution about step 2: memories are written from the perspective of the
sessions that learned them. Dates in them are absolute and correct. But any
memory naming a file, flag or function describes the repo *as of 2026-08-13* —
verify before you act on that specific detail, not before you trust the memory.

---

## 1. How to work with this user

The repo cannot tell you any of this.

**Ask questions rather than guess.** This is a standing, repeatedly-stated
instruction, and it is the single most load-bearing item in this file. The user
holds context the repository does not, and their answers have reversed finished
reasoning more than once — not "refined", *reversed*. Ask when different answers
lead to materially different work. Do not ask about things with an obvious
default or facts you can verify from the code. Ask at the point the answer is
needed, and build everything not blocked on it in the meantime.

**They are a collaborator steering the work, not a client receiving it.** They
read the reasoning, not just the result. Report measurements that refute the
hypothesis that motivated them — several have, and each refutation was worth
more than the guess it replaced.

**The register of this project's writing is unusual and deliberate.** Commit
subjects, ledger entries and test names state *what breaks*, in prose, not
what changed in the abstract — "Measure whether a fact survives the distance to
the question", not "add recall eval". Match it. The ledger's `NOT done` sections
are as important as what was built; write them honestly.

**Verification bar is real.** Full backend suite + `ruff check .` before calling
anything done, and new tests are mutation-tested — deliberately break the code
under test and confirm the test fails. This has repeatedly caught tests that
passed for the wrong reason.

**Public repo, real person.** `Aniket-a14/AI_friend` is public and has a fork.
The persona work is modelled on a real friend who did not consent to being in a
public repository. Anonymise *before* writing — commits, PR bodies, comments,
test fixtures, the ledger. Live-model transcripts are the trap: they contain
real names by construction. This was violated once (2026-08-02, PRs #97/#99),
reached public `main`, and cleaning it took `git filter-repo` plus a force-push
— and *even then* the objects stayed reachable by SHA, because a merged PR's
`refs/pull/<n>/head` pins them forever. Only GitHub Support can purge that.

---

## 2. The memories — write these files

Eight memory files plus the index. Contents are given verbatim. The
`originSessionId` and `modified` fields are provenance from the Windows
sessions; keep them as-is — they record when the fact was learned, which is
what makes a superseded memory legible later.

### `ask-questions-rather-than-guess.md`

```markdown
---
name: ask-questions-rather-than-guess
description: Standing instruction — always ask clarifying questions before committing to a design, rather than picking an interpretation and building it
metadata:
  node_type: memory
  type: feedback
  originSessionId: 02717c4b-4f64-442f-904e-d233d63f2bbb
  modified: 2026-08-02T12:33:49.354Z
---

Stated 2026-08-02: *"ask me questions if you need and keep in memory to always
ask questions."* Earlier in the same session they had already said *"now ask me
as many questions as you want"* before the research phase, so this is a repeated
preference, not a one-off.

**Why:** this user holds context the repo does not — that production personas
are authored by writers, that the laptop is about to be replaced, that the
research paper has no deadline. Every one of those reversed a design decision I
had already reasoned my way to. Guessing wastes a build; asking costs one turn.
They are also an active collaborator who wants to steer, not a client handing
off a spec.

**How to apply:** use AskUserQuestion when different answers lead to materially
different work — which retrieval stack to measure against, whether a comparison
should be budget-matched, what a metric is allowed to assume. Do NOT ask about
things with an obvious default or facts verifiable from the code; make those
calls, state them, and move on. Ask at the point the answer is needed, and do
everything not blocked on it first. When mid-build and a question arises, keep
building the unaffected parts rather than stopping dead.

Related: [[production-personas-are-authored]] is the clearest case of an answer
that invalidated work already reasoned through.
```

### `cvs4-qlora-is-roadmap-only.md`

```markdown
---
name: cvs4-qlora-is-roadmap-only
description: "CVS-4 / QLoRA \"REM sleep\" consolidation is a design doc discussed across sessions but never implemented; parts of the same roadmap ARE built, and one section now contradicts shipped code"
metadata:
  node_type: memory
  type: project
  originSessionId: 02717c4b-4f64-442f-904e-d233d63f2bbb
  modified: 2026-07-19T13:01:23.266Z
---

`docs/cvs4_architecture_roadmap.md` describes a QLoRA "REM sleep" consolidation
layer that fine-tunes a LoRA adapter on accumulated memory during idle periods.
As of 2026-07-19 it is **discussed but not implemented** — no `rem_sleep`,
`qlora`, or adapter-training code in `app/`/`crates/`/`scripts/`, no `peft`/
`trl`/`bitsandbytes` dependencies, and `.agents/CONTEXT.md` has **no entry for
it at all**. The user has referred back to it as a prior discussion; it happened
in a session whose context is not carried forward.

**Why:** the ledger is the project's record of real decisions, so its silence
here is the signal — searching the ledger for "QLoRA" returns nothing and the
absence is easy to misread as memory loss rather than as "never decided".

**How to apply:** treat the roadmap as design input, not as agreed work. Do not
reconstruct plans "we made" from it. Note it is *not* uniformly aspirational:

- **Built already** — the §3B dual-threshold forgetting curve
  (`threshold = -3.5 if importance_score < 0.5 else -4.5`, milestones ≥0.7 never
  pruned), `distractor` exclusion from Neo4j, and the `dopamine_phasic` /
  `release_dopamine` endocrine spikes.
- **Aspirational** — the QLoRA adapter itself, the parametric prefix header
  replacing the NL system prompt, single-pass generation with a trailing
  `<cognitive_appraisal>` block, `vision_appraisal.py`, and the
  `llama3.2:3b-persona` GGUF.
- **Now wrong** — §3D and §F.6 specify Python-side prosody formulas
  (speaking_rate / intensity / pause_bias) and say to wire them into
  `speech.py`. PR #86 deleted exactly those fields from `ChatOutput`; prosody has
  a single source in Rust's `vad_to_prosody`. Following §F.6 as written would
  reintroduce the duplicate implementation that had already drifted from Rust.

Also relevant: the roadmap sits in the same docs family as the `[TBP]` benchmark
placeholders, so its performance claims are targets, not measurements.
```

### `no-live-llm-runs.md`

```markdown
---
name: no-live-llm-runs
description: Live model runs are now permitted if they fit the machine — reversed on 2026-08-02 from the earlier blanket "never generate against a real LLM"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 02717c4b-4f64-442f-904e-d233d63f2bbb
  modified: 2026-08-02T12:14:28.506Z
---

**Superseded 2026-08-02.** The user granted live runs: *"yes you can run live
run, but make sure it fits the system."* The earlier rule — set 2026-07-19 with
"DONT RUN on actual llm" — no longer holds as a blanket prohibition.

**Why:** the original objection was cost in the user's time and load on a
CPU-only laptop, not a principled objection to live evaluation. Once
measurement became the bottleneck — an eval harness whose numbers moved between
identical runs cannot gate anything — live runs were the only way to answer the
question, and the user agreed. The `[TBP]` placeholders and finding B1 exist
precisely because nothing here had been measured against a real model.

**How to apply:** run live when a claim genuinely requires it, and size the run
to the box first — `qwen2.5:3b` at roughly four minutes per 16-probe suite is
fine; a 14B, or a sweep of dozens of generations, is not on the current laptop.
Say what a long run will cost before starting it. Report the measurement even
when it refutes the hypothesis that motivated it — three of mine were refuted
this way and each refutation was worth more than the guess. Never edit source
that a running measurement imports; restart the measurement instead.

The constraint is machine-shaped, not policy-shaped, so it loosens with
[[hardware-and-deployment-roadmap]] once the MacBook Air M5 arrives. Verifying
*code paths* still belongs in tests with scripted clients — a live model is for
measuring behaviour, never for checking that a function is wired up.
```

> **Receiving session, note:** the "sized to the box" clause is the half of this
> memory that the migration changes. See §6.

### `personal-branch-policy.md`

```markdown
---
name: personal-branch-policy
description: Pankudi_ai splits personal/private work from the shared codebase across separate branches; personal/ is gitignored and personal/pankudi is never merged.
metadata:
  node_type: memory
  type: project
  originSessionId: 02717c4b-4f64-442f-904e-d233d63f2bbb
  modified: 2026-08-02T06:27:38.573Z
---

The user is building a personal humanoid brain modelled on a real friend, from
their WhatsApp history. Two hard rules, stated 2026-08-02 and still in force:

- `personal/` is **gitignored totally**. It holds the chat export, the derived
  corpus, `persona.toml`, `biography.md` — all identifying material. Nothing in
  it is ever committed.
- Branch `personal/pankudi` holds personal-only code (`friend_brain/`) and is
  **never merged to main**. Any change to the actual codebase goes to `main` or
  a new branch off `main`, never to the personal branch.

**Why:** the material describes a real, named person who did not consent to
being in a public repo, and the shared codebase has to stay usable by anyone.

**How to apply:** before editing, decide which side of the line the change is
on. A generic capability (grounding gates, config paths, parser fixes) branches
off `main` even when it was discovered while doing personal work. Ask rather
than guess when a change could plausibly be either.

See [[no-live-llm-runs]] — the same caution applies to generating against this
persona.
```

### `no-personal-names-in-shared-artifacts.md`

```markdown
---
name: no-personal-names-in-shared-artifacts
description: "Never put real personal names or identifying details into commits, PR bodies, code comments, test fixtures, or the ledger — the repo is public."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 02717c4b-4f64-442f-904e-d233d63f2bbb
  modified: 2026-08-02T08:17:45.378Z
---

Real names and identifying details must never appear in anything that leaves the
machine: commit messages, PR titles/bodies, code comments, **test fixtures**, or
`.agents/CONTEXT.md`. Use invented names (Daniel, Elena, Ada) and generic places.

**Why:** `Aniket-a14/AI_friend` is a **public** repo with a fork. On 2026-08-02 I
put the friend's family names into a test fixture in PR #97 and a live-model
transcript into PR #99's body and the ledger. It reached public `main`. Cleaning
it required `git filter-repo` plus a force-push of a public branch — and even
then the old commit stayed reachable by direct SHA, because a merged PR's
`refs/pull/<n>/head` pins its objects forever. Only GitHub Support can purge
that. The person described did not consent to being in a public repository.

**How to apply:** anonymise *before* writing, not after — treat a real name in a
diff the same as a leaked credential. Live-model transcripts are the easy trap:
they contain both names by construction, so rewrite speakers to `User:`/`Agent:`
before quoting them anywhere. Personal material belongs only in the gitignored
`personal/` folder — see [[personal-branch-policy]].
```

### `production-personas-are-authored.md`

```markdown
---
name: production-personas-are-authored
description: "In production, personas are written by an author/writer per character — there is no reference corpus, so main-branch design and evals must never assume one."
metadata:
  node_type: memory
  type: project
  originSessionId: 02717c4b-4f64-442f-904e-d233d63f2bbb
  modified: 2026-08-02T09:24:02.843Z
---

The WhatsApp-corpus workflow is **personal-branch only**. In the intended
production use of `main`, multiple people each create a dedicated character
with a writer or author, and that authored document *is* the persona. There is
no chat log to mine and no ground-truth text by that character.

**Why:** it changes what belongs in `main` and what any evaluation can measure.
Corpus-derived techniques (idiolect extraction, QLoRA on real messages,
distribution-distance scoring against someone's real texts) are personal tools,
not architecture. An eval that scores human-likeness by comparing output to a
reference corpus cannot run at all for an invented character.

**How to apply:** style metrics must be corpus-free or persona-relative —
scored against the persona document's own declared style, or against generic
conversational baselines. Anything that needs "her real messages" stays in
`personal/`. This is the same rule as [[no-personal-names-in-shared-artifacts]]
and the "no hardcoded acceptance rules in prod" principle, applied to
evaluation rather than to code.
```

### `humanlikeness-target-is-gpt56-luna.md`

```markdown
---
name: humanlikeness-target-is-gpt56-luna
description: "The text-quality target is GPT-5.6 Luna — which is the family's CHEAPEST tier, so human-likeness is a post-training property, not a scale property."
metadata:
  node_type: memory
  type: project
  originSessionId: 02717c4b-4f64-442f-904e-d233d63f2bbb
  modified: 2026-08-02T09:24:09.406Z
---

The reference point for "text that reads as human" is **GPT-5.6 Luna**.

GPT-5.6 (released 2026-07-09) has three tiers. Ranked most to least capable:
**Sol** (flagship, $5/$30 per 1M tokens), **Terra** ($2.50/$15), **Luna**
($1/$6 — "fastest and most budget-friendly"). Several SEO articles state this
backwards; Wikipedia, CNBC and OpenAI's own preview page agree Sol is flagship.

**Why:** if the *cheapest* tier in the family already reads as human, then
conversational human-likeness is not bought with scale — it is a post-training
property shared across the family. That is the single most encouraging fact
for a local-first architecture, and it reframes the research question away
from "how big a model do we need" toward "what post-training produces this."

**How to apply:** stop treating text quality as blocked on model size. Luna at
$1/$6 also makes the "cloud later" half of the plan nearly free at this
project's token volumes. See [[production-personas-are-authored]] for why the
style target must still be defined without a reference corpus.
```

### `hardware-and-deployment-roadmap.md`

```markdown
---
name: hardware-and-deployment-roadmap
description: Dev hardware moves to a MacBook Air M5 within days; training on rented GPU; a server is planned for the humanoid deployment.
metadata:
  node_type: memory
  type: project
  originSessionId: 02717c4b-4f64-442f-904e-d233d63f2bbb
  modified: 2026-08-02T09:24:16.337Z
---

As of 2026-08-02: development moves off the Windows laptop (i7-1195G7, 15.7 GB
RAM, MX450 with 2 GB VRAM — effectively CPU-only inference) to a **MacBook Air
M5** within days. Fine-tuning will use a **rented GPU**. When the system drives
a humanoid, it will run against a **server**, not the laptop.

**Why:** the "we can't use bigger models, this laptop won't handle it"
constraint that shaped earlier decisions is temporary and nearly expired. On
Apple unified memory a 7B–14B q4 becomes viable locally, and remote inference
is architecturally acceptable at the humanoid stage.

**How to apply:** treat local-first as a *deployment mode* the architecture
supports, not a ceiling it must be designed down to. Keep the language layer
swappable. Do not re-derive plans from the old 3B ceiling — but do confirm the
M5's actual RAM configuration before assuming a model size fits.
```

> **Receiving session:** this memory is the one the migration *completes*. Once
> the Mac is running and its RAM is confirmed, update it in place — it should
> read as history ("moved on <date>, config is X"), not as a pending plan.

### `MEMORY.md` (the index)

```markdown
# Memory Index

- [Ask questions rather than guess](ask-questions-rather-than-guess.md) — standing instruction; they hold context the repo doesn't, and their answers have reversed finished reasoning more than once.

- [CVS-4 / QLoRA is roadmap-only](cvs4-qlora-is-roadmap-only.md) — discussed across sessions, never built; parts of the same doc *are* implemented, and §F.6 now contradicts shipped prosody code.
- [Live LLM runs are allowed now](no-live-llm-runs.md) — reversed 2026-08-02: run live when a claim needs it, sized to the machine; code paths still get scripted clients.
- [Personal branch policy](personal-branch-policy.md) — `personal/` is gitignored totally and `personal/pankudi` never merges; codebase changes branch off `main` even when found during personal work.
- [No personal names in shared artifacts](no-personal-names-in-shared-artifacts.md) — public repo; anonymise before writing commits, PR bodies, comments, test fixtures and the ledger.
- [Production personas are authored](production-personas-are-authored.md) — writers invent each character, so `main` and its evals can never assume a reference corpus exists.
- [Human-likeness target is GPT-5.6 Luna](humanlikeness-target-is-gpt56-luna.md) — Luna is the family's *cheapest* tier, so the quality being chased is post-training, not scale.
- [Hardware and deployment roadmap](hardware-and-deployment-roadmap.md) — MacBook Air M5 in days, rented GPU for training, server for the humanoid; the 3B ceiling is temporary.
```

---

## 3. Where the work stands, 2026-08-13

`main` @ `41a96c9`, working tree clean. **850 tests passing**, 0 failed / errored
/ skipped, `ruff check .` clean. Six local branches exist (`evals/…`, `feat/…`,
`fix/…`) but they are stale copies of already-merged PRs — a fresh clone will
not have them, and should not recreate them.

The arc of the last few weeks, most recent first:

| PR | What it did |
|----|-------------|
| #104 | Recall probes that can distinguish two retrievers (see below) |
| #103 | Measured the memory layer against a fifty-line BM25 control |
| #102 | Multi-turn recall harness — does a fact survive distance to the question |
| #101 | Record what she was asked and could not answer; let her ask back |
| #100 | Self-claim trigger became grammatical instead of a noun list |
| #96–#99 | Biography seeding, sibling-heading fix, prompt self-contradiction fix |
| #89 | The behavioural eval harness itself |
| #76–#88 | Persona unification, identity authority, audit follow-ups, ruff adoption |

**The live edge is the eval harness measuring the memory layer.** The most
recent result — read the full ledger entry at `.agents/CONTEXT.md` §`2026-08-02
-- The tie was the benchmark's fault`:

- On the discriminating pack (8 probes × 6 strategies, `qwen2.5:3b`, real
  Postgres/Qdrant/Neo4j, `--num-ctx 8192`): `retrieved_memory_store_6` **5/8**,
  `full_history` 3/8, `retrieved_bm25_6` 2/8, `recent_window_6` 0/8. The memory
  layer wins three head-to-heads and loses none.
- The best single finding: at distance 96, six retrieved turns (240 chars) beat
  the full 194-turn history (7,123 chars). ~30× less context, better answer.
- **The whole run is provisional.** `refresh_on_recall=False` also selects the
  candidate-pool tier in `_compute_mrl_gating`, so the memory strategies
  searched 20 candidates where production searches 120. `full_candidate_pool=True`
  is the fix. The re-run **has not happened** — infra containers were down when
  it was attempted. This is the top of the queue (§7).
- Separately established, and *not* acted on: `_base_activation`'s `ln(recall_count)`
  term makes **frequency outrank relevance structurally**. Neutralising it moved
  answers from #17→#2, #17→#1, #36→#4. No production constant was changed,
  deliberately — tuning a retrieval constant against the eval pack in the same
  commit is finding B1 exactly. The principled fix needs per-presentation
  timestamps the schema does not store.

**Standing integrity constraints** (also in `CLAUDE.md`, restated because they
are the easiest thing for a fresh session to violate): documented benchmark
numbers are `[TBP]` placeholders; `MOCK_LLM_TEXT=true` returns strings fitted to
one demo corpus; no headline latency or Recall@K figure has been measured against
real infrastructure. State targets as targets.

---

## 4. What does **not** arrive with `git clone`

This is the part most likely to bite. All of the following are gitignored and
must be copied from the Windows machine by hand — AirDrop, USB, or `scp`:

| Path | Size | Why it matters |
|------|------|----------------|
| `personal/` | ~4 MB | WhatsApp export, cleaned + curated corpus, `persona.toml`, `biography.md`, `style_profile.{json,md}`, `curation_report.md`, `runtime/`. **Irreplaceable** — derived through several curation passes. |
| `.env` | 2.6 KB | Real service config. `.env.example` is tracked; the filled one is not. |
| `models/` | ~113 MB | `GPT_weights`, `SoVITS_weights`, `base` — voice model weights. |
| `*.db` at repo root | ~60 KB | `app.db`, `identity_core.db`, `state_cache.db` — local SQLite state. Disposable if you are willing to re-seed; copy them if you want continuity. |
| `backend/evals/out/` | small | `discriminating_qwen3b.json` — the baseline the next comparison runs against. Copy it or the §7 re-run has nothing to compare to. |
| `.venv/` | large | Do **not** copy. Windows binaries. Recreate on the Mac. |

The `personal/pankudi` branch is local-only and holds `friend_brain/`
(`parse_whatsapp.py`, `curate_corpus.py`, `extract_style.py`, its own
`ruff.toml`). It is **never pushed and never merged**. If the Mac is a fresh
clone, that branch does not come with it — push it to a **private** remote, or
bundle it (`git bundle create pankudi.bundle personal/pankudi`) and copy the
bundle across. Do not push it to `origin`.

---

## 5. Mac setup

Toolchain on the Windows machine, as a target to match or beat:

- Python **3.13.1** — venv at the **repo root** (`.venv`), pytest runs from `backend/`
- Node **v25.2.1**, Rust **1.95.0**, Docker **29.6.1**
- Ollama models pulled: `qwen2.5:3b`, `llama3.2:3b-instruct-q4_K_M`,
  `llama3.2:3b-text-q4_K_M`, `nomic-embed-text:latest`, plus two coder/reasoning
  models. Re-pull rather than copy; `nomic-embed-text` is required for embeddings.

Path differences that will break copy-pasted commands from `CLAUDE.md`:

```bash
# CLAUDE.md documents (Windows):
../.venv/Scripts/python.exe -m pytest
# On macOS:
../.venv/bin/python -m pytest
```

Two judgement calls for the receiving session — **ask the user, do not decide
alone**, because `CLAUDE.md` is committed and shared with contributors:

1. Whether to rewrite `CLAUDE.md`'s command block to macOS paths, or make it
   dual-platform.
2. The **"Getting a reliable test count on Windows"** section documents this
   terminal truncating pytest's summary — the `N passed` line and the entire
   `=== FAILURES ===` block get swallowed, so a run can look clean when it is
   not. That may simply not happen on macOS. Verify before trusting the dots
   again, and do not delete the guidance unilaterally — the `--junit-xml`
   habit is cheap and correct on any platform.

Also verify: `maturin build` for the PyO3 `cognitive-rust` extension on
`aarch64-apple-darwin`, and whether the Docker infra compose files
(`docker-compose.infra.yml` — Postgres/Qdrant/Neo4j/NATS) pull arm64 images
cleanly. The eval work in §7 needs all four services up.

---

## 6. What the Mac changes about the project's assumptions

Not just an environment move — it retires a constraint that shaped real
decisions.

- **The 3B ceiling lifts.** On unified memory a 7B–14B q4 becomes viable. But
  **confirm the actual RAM configuration** before assuming a size fits, and say
  what a long run will cost before starting it.
- **Every existing eval baseline is `qwen2.5:3b` on CPU.** A model change
  invalidates comparison, not just makes it faster. `compare` carries sampling
  options and a system-prompt digest precisely so it can refuse to diff two runs
  that were not configured alike. If the user wants a bigger model, the honest
  sequence is: re-baseline first, then compare — never compare a Mac run against
  the Windows JSON and call the delta a regression.
- **`runner.reset_model_state` was tuned against CPU-backed Ollama.** It unloads,
  reloads, and burns one throwaway generation before the first scored probe,
  because without it two byte-identical runs differed on 3 of 16 probes. Whether
  Metal-backed Ollama has the same starting-state nondeterminism is **unknown**
  — re-verify the three-consecutive-identical-runs property on the Mac before
  trusting any gate.
- **The "sized to the box" half of the live-run permission loosens**, but the
  rest of that memory holds: measuring behaviour is what a live model is for;
  checking that a function is wired up still belongs in tests with scripted
  clients.

---

## 7. The queue

In the order the ledger leaves them. Confirm with the user before starting —
this list is inference from the ledger, not an agreed plan.

1. **Re-run the discriminating recall pack with `full_candidate_pool=True`.**
   The headline result is provisional until this lands, and it is explicitly
   flagged as such in the ledger. Needs the infra containers up (they were down
   last attempt). Everything else waits behind this.
2. **Cross-session recall** — designed, not built. A fact learned in an earlier
   conversation and absent from this transcript is the most discriminating probe
   available, because both context baselines fail on it by construction. Blocked
   on a harness change: the strategy seam maps retrieved turns back to transcript
   positions, so a hit not in the transcript is silently dropped. Needs a
   retriever index separate from the rendered context.
3. **Write-side behaviour is entirely unmeasured** — importance scoring, decay,
   pruning, promotion are all bypassed by indexing a transcript in one burst and
   querying it immediately.
4. **The `ln(freq)` activation problem**, if and when the schema can carry
   per-presentation timestamps. `ln(freq) - d*ln(recency)` is the standard
   approximation to ACT-R's `B_i = ln(Σ t_k^-d)`, valid when presentations are
   spread across a lifetime and wrong for the bursty ones a conversation
   produces. Do **not** patch it by tuning `ACTR_SPREAD_WEIGHT` against the eval
   pack.
5. **CVS-4 / QLoRA** remains roadmap-only. The eval harness exists to be the
   gate that consolidation loop would need. Fine-tuning is planned on a rented
   GPU, not locally.

---

## 8. Self-destruct

Run these **after** the receiving session has written the memories in §2 and the
user has confirmed the transfer took. Three levels — use the lowest one that
matches how this file actually travelled.

### Preferred: never commit it at all

If this file moved by AirDrop / USB / `scp`, there is no history to purge:

```bash
# On the Mac, and again on the Windows machine:
rm -f mac_migrations.md
```

That is the whole self-destruct. Levels 2 and 3 exist only for the case where it
was committed.

### Level 2 — committed locally, never pushed

```bash
cd <repo>
git rm --cached mac_migrations.md 2>/dev/null; rm -f mac_migrations.md

# Drop it from every local commit that touched it:
git filter-repo --path mac_migrations.md --invert-paths --force

# filter-repo strips remotes by design — put it back:
git remote add origin https://github.com/Aniket-a14/AI_friend.git

git reflog expire --expire=now --all && git gc --prune=now --aggressive
git log --all --oneline -- mac_migrations.md   # must print nothing
```

### Level 3 — committed **and** pushed

Everything in Level 2, then a force-push of the rewritten branch:

```bash
git push --force-with-lease origin main
```

Read this before running it:

- **`main` is a public branch with a fork.** Force-pushing rewrites history for
  the fork owner and anyone else who has cloned. Tell them.
- **The purge is not complete.** GitHub keeps unreachable objects addressable by
  direct SHA, and if this file ever appeared in a **pull request**, that PR's
  `refs/pull/<n>/head` pins its objects permanently — force-pushing does nothing
  to it, and only GitHub Support can remove it. This project has already learned
  this the hard way (2026-08-02, PRs #97/#99).
- **Therefore: do not open a PR containing this file.** If it must travel by
  git, push it as a direct commit on a throwaway branch, never as a PR.
- Verify after, from a fresh clone, not from the rewritten one:
  ```bash
  git clone --mirror https://github.com/Aniket-a14/AI_friend.git verify.git
  cd verify.git && git log --all --oneline -- mac_migrations.md   # expect nothing
  ```

### The residue nobody thinks about

Deleting the file does not delete every copy of its contents:

- **Session transcripts.** Both machines' Claude Code sessions logged this file
  under `~/.claude/projects/<project-slug>/`. Clear them if the contents matter
  to you.
- **Editor and OS artefacts** — VS Code local history, Time Machine, OneDrive /
  iCloud sync, the Recycle Bin / Trash.
- Anywhere you pasted it in transit (chat apps, gists, email drafts).

Nothing in this file is a credential, and no real personal name appears in it by
construction. The material worth removing is the user's private working
preferences and unpublished project state — sensitive in the sense of *not
yours to publish*, not in the sense of exploitable.

---

*End of transfer. Once §2 is written and §8 has run, this file should not exist
anywhere — and the receiving session should be able to reconstruct everything
above from the memories, `CLAUDE.md`, and the ledger alone. That is the test of
whether the transfer worked.*
