# FUTURE_WORK.md — everything still open, and why

**Standing as of 2026-08-24**, after the engineering roadmap (Stages 0–6, PR #202)
and its leftovers pass (PR #203) both merged to `main`.

This file replaces thirteen audit documents and a 1,784-line brief as the place to
look for *what is left to do*. Those documents are still on disk under `audit/`
(untracked, local only) and remain the evidentiary record — every finding ID cited
below resolves there. What they are not is a work queue: they were written on
2026-08-22, before any of it was implemented, and most of what they describe is now
done.

**The engineering ledger, `.agents/CONTEXT.md`, is still ground truth.** This file
is a forward-looking index into it. Where the two disagree, the ledger is right.

---

## How to read this

Every item carries the same five fields, because the thing that makes a roadmap
rot is recording *what* without recording *why*:

- **What** — the defect or gap, in one paragraph, with `file:line` where it exists.
- **Why it matters** — what a user or the system actually loses. If this field is
  weak, the item probably should not be done.
- **How** — the approach that was chosen, concretely enough to start from.
- **Alternatives rejected** — and the reason. This is the field that stops an item
  from being relitigated every six months.
- **Status** — one of:

| Status | Meaning |
| :--- | :--- |
| **OPEN** | Should be done. Nothing blocks it but time. |
| **BLOCKED** | Decided and specified, but waiting on something outside the code. |
| **TRIGGERED** | Do nothing now. Becomes mandatory the day a named condition holds. |
| **DECLINED** | Deliberately not doing. Recorded so it is not re-opened by accident. |
| **UNANSWERED** | A question, not a task. Someone has to decide. |

---

# Part 1 — Open engineering work

Two items, both from the same finding cluster (P4-10: "signals computed but never
consumed"), both blocked on the same thing: **real audio**.

Everything else P4-10 named is done. `turn_taking_probability` was verified over
the reachable state space and wired into proactive-speech gating; the dead-code
test was identified and fixed. These two are what is left, and they are left
because verifying them needs a microphone and a running synthesiser, not because
they are hard.

## 1.1 — `pause_bias`: arousal-driven pause length

**Status: BLOCKED** (needs `local_voice` / GPT-SoVITS running for real synthesis).
Finding **M3-D1**, roadmap **P4-10**, plan Item 4a.

### What

`vad_to_prosody` derives `pause_bias` as `1.0 - arousal`
(`backend/crates/contracts/src/lib.rs:345-346`). `clamp_prosody` re-clamps it
(`backend/crates/voice-agent/src/main.rs:91`). `OlaCrossfadeFilter` includes it in
the equality test that decides whether a crossfade fires. And **nothing applies it
to any pause duration** — the modulation path hardcodes the multiplier to `1.0`
(`:129`). Pause lengths come solely from the literal `<pause=Nms>` tags the LLM
emits, identically whether the agent is calm or frightened.

### Why it matters

Humans compress pauses when aroused and stretch them when calm or tired. Pause
length is the one temporal dimension of delivery still frozen. After P3-13
(Stage 6 Part 6), every *other* prosody dimension already drifts across an
utterance via `ProsodyTrajectory::prosody_now()`. This is a gap in a system that
is otherwise finished: arousal-driven pacing is wired end to end except the end
that makes it hearable.

### How

Keep `split_temporal_parts` (`voice-agent/src/main.rs:1251`) **pure** — it keeps
parsing tags to `TemporalPart::Silence(ms)` / `Hesitation(350)`, so its existing
test at `:1582` stays valid. Scale at the **consumption** site, where prosody is
known, sampling `prosody_now()` at the moment the pause is emitted so pause length
drifts with the trajectory exactly as rate, pitch and volume already do.

Multiplier `0.6 + 0.8 × pause_bias`, giving a `[0.6, 1.4]` range. Re-apply the
existing 5000 ms clamp **after** scaling, not before — scaling a pre-clamped value
can exceed the cap.

**Verify before wiring.** Synthesize one fixed utterance containing several
`<pause=Nms>` tags through the real TTS path at a high-arousal and a low-arousal
state, and measure the rendered PCM. Three criteria, all required:

1. Total rendered silence differs between the two states by a margin matching the
   multiplier (≈2.3× between extremes) — **measured on the PCM**, not asserted
   from the code.
2. Total utterance duration shifts accordingly, proving the change survives into
   the audio rather than being absorbed by the synthesis loop.
3. No artefact at the seams. This is the real risk: `pause_bias` is already part of
   the crossfade equality test, so changing what it does changes *when a crossfade
   fires*.

If 1 or 2 fails, the value is being overwritten downstream — find where before
wiring. If 3 fails, the multiplier range is wrong, not the idea; narrow it and
re-measure.

### Alternatives rejected

- **Scaling inside `split_temporal_parts`.** Rejected: it would break that
  function's purity and invalidate its existing test, and — decisively — a pure
  parser cannot sample `prosody_now()`, so pause length would be constant across
  an utterance instead of drifting with the trajectory. The drift is the point.
- **Shipping it unverified because the code is obviously right.** Rejected on
  principle: this repo has a standing rule that a signal is wired only after it is
  shown to help. Pause scaling is audible on *every* utterance, which makes it the
  worst candidate for an unverified change.

### What unblocks it

`local_voice` running (see [1.3](#13--the-missing-reference-clip) — its healthcheck
is also broken) plus enough headroom to run CPU-mode GPT-SoVITS. On a 16 GB
machine that realistically means not running the vision profile at the same time.

---

## 1.2 — `tempo_wpm`: fix the measurement, verify it, then entrain

**Status: BLOCKED** (needs a real recording session).
Finding **M3-A17**, roadmap **P4-10**, plan Item 4c.

### What

`estimate_tempo_wpm` (`backend/crates/stt-agent/src/main.rs:917`) computes a
zero-crossing rate and maps it to `120 + min(zcr·200, 60)`. **ZCR measures spectral
brightness — fricative content — not speaking rate**, and the output is
structurally confined to `[120, 180]` wpm no matter how fast anyone talks. It is
published on `user.voice.properties` under a name that asserts otherwise. Its only
consumer today is a log line (`backend/app/agents/brain_agent.py:608`).

### Why it matters

Speech-rate entrainment — humans unconsciously converging toward an interlocutor's
tempo — is a genuine humanoid feature and would be the largest human-likeness win
of the three P4-10 signals.

**But entraining to this number would make the agent less human, not more.** It
would converge on a value that does not track the user at all and does not vary
outside a 60-wpm band. Acting on a wrong signal is worse than acting on none. That
is why "wire it up" is the wrong instruction for this one, and why it splits into
three ordered pieces.

### How

**(i) Fix the measurement — correctness, do this regardless.** The problem is
*where* it is computed: `estimate_tempo_wpm` runs per inbound audio chunk
(`main.rs:746`), in the VAD loop, **where no transcript exists yet**. Real speaking
rate needs words and duration, and the crate has both at the final-transcript
point. Compute `words / duration_minutes` there, carry it in session state, and
have the per-chunk `UserVoiceProperties` publish the last completed utterance's
measured rate. Before the first completed utterance there is no rate — make the
contract field `Option<f64>` in **both** `crates/contracts/src/lib.rs` and
`backend/app/contracts.py`, and publish `None` rather than a fabricated default.
Delete `estimate_tempo_wpm`.

**(ii) Verify the corrected number before wiring anything to it.** Record three
passes of the same scripted paragraph — slow, natural, fast — via
`backend/scripts/audio/record_voice.py`, and compare measured WPM against
hand-counted ground truth (`words ÷ stopwatch duration`). Criteria:

1. **Rank order holds:** slow < natural < fast, every time. An estimator that
   cannot order three deliberately different tempos is unusable however good its
   absolute error.
2. **Absolute error within ~15%** of hand-counted truth on the natural pass.
3. **Range exceeds the old band.** The ZCR proxy was trapped in `[120, 180]`; if
   the corrected number does not move outside that on the slow and fast passes,
   nothing has actually been fixed.

If it fails, the likely cause is duration accounting — whether the measured window
includes leading/trailing silence the endpointer kept. Fix the window, re-measure.
Do not proceed to (iii) on a number that failed here.

**(iii) Wire it — partial entrainment.** Feed the verified rate into the agent's
own prosody `rate` so delivery converges **partway** toward the user's tempo:
`agent_rate = base_rate × (1 + k × (user_rate / reference_rate − 1))` with
`k ≈ 0.3`, clamped to the existing prosody rate bounds. Verify the wiring on PCM,
not just the signal: a fast-speaking user measurably shortens the agent's rendered
utterance and a slow one lengthens it, and the clamp holds at both extremes.

### Alternatives rejected

- **Full convergence (`k = 1.0`).** Rejected: matching a speaker's tempo exactly
  reads as mimicry rather than rapport. Partial convergence is what the phenomenon
  actually looks like in humans.
- **Keeping `estimate_tempo_wpm` and calibrating it.** Rejected: ZCR is not a noisy
  proxy for speaking rate, it is a measurement of a different physical quantity.
  No calibration constant fixes a category error.
- **Publishing a default (e.g. 150 wpm) before the first utterance.** Rejected: a
  fabricated default is indistinguishable downstream from a measured one. `Option`
  makes "we do not know yet" representable, which is the honest state.

### Risks specific to this item

- **It changes a published contract field to `Option`.** The Rust mirror and
  `contracts.py` must change **together** — a one-sided change is exactly the
  silent-drop failure mode that produced the `char_offset` / `character_offset`
  bug found in Stage 6 Part 9. Re-run
  `backend/scripts/bootstrap/setup_nats_streams.py` after the contract change.
- **It compounds with [1.1](#11--pause_bias-arousal-driven-pause-length).**
  Entrainment moves prosody `rate` while pause scaling moves silence; both change
  perceived tempo. **Verify them independently before enabling both**, or a
  regression in one will be attributed to the other.

---

## 1.3 — The missing reference clip

**Status: OPEN** (needs an audio asset, not code). Found 2026-08-24 while fixing an
unrelated crash-loop; no finding ID — it predates the audit's coverage.

### What

`backend/scripts/bootstrap/sovits_bootstrap.sh:88` and `sovits_healthcheck.sh` both
POST against a fixed reference clip, `output/sample_en_gold.wav`, mounted from the
host's `backend/voice_samples/` (`docker-compose.infra.yml:175`). **The file does
not exist**, `backend/voice_samples/` is empty, and nothing in the repository
provisions it — not a bootstrap script, not a provisioning script, not the docs.
Every call returns 400 Bad Request.

`.env.example:157-158` describes this exact clip and its transcript as "the
always-present neutral clip GPT-SoVITS conditions delivery on", implying it is
expected to exist. It never did.

### Why it matters

It is the difference between the voice stack starting and the voice stack
appearing to start. The container boots, loads weights, serves on 9871 — and its
healthcheck fails forever, so `local_voice` never reports healthy and anything
gated on that health never proceeds. It also **blocks [1.1](#11--pause_bias-arousal-driven-pause-length)**,
which needs real synthesis to verify.

More importantly: this clip *is* the voice. GPT-SoVITS clones zero-shot from a
reference clip, so whatever audio lands at this path is what the agent sounds
like. See
[BRINGING_IT_TO_LIFE.md § Giving it a voice](BRINGING_IT_TO_LIFE.md#5-giving-it-a-voice).

### How

Record (or license) a clean 5–10 s neutral-tone clip, place it at
`backend/voice_samples/sample_en_gold.wav`, and set `REF_TEXT` in `.env` to its
**exact** transcript. Then decide whether the repo should ship a reference clip at
all, or whether `voice_samples/` should stay empty-by-design with the bootstrap
scripts made to skip the probe gracefully when no clip is present.

### Alternatives rejected

- **Generating a synthetic clip to satisfy the healthcheck.** Rejected: a
  synthesised reference makes the cloned voice a copy of a copy, and a healthcheck
  that passes against a fake asset is worse than one that fails honestly.
- **Deleting the healthcheck probe.** Rejected as the *first* move — the probe is
  the only thing that distinguishes "server up" from "server can actually
  synthesise". If the decision is that no clip ships, the probe should be made
  conditional, not removed.

### Related bug, fixed 2026-08-24

The two helper scripts on this exact path pointed at directories the synthesiser
cannot see. `record_voice.py` saved to `backend/scripts/audio/voice_samples/` and
`process_voice_samples.py` listed `backend/scripts/voice_samples/`, while the only
directory that matters — the one `docker-compose.infra.yml:175` bind-mounts to
`/workspace/GPT-SoVITS/output`, and therefore the one `REF_AUDIO_PATH=output/...`
resolves against — is `backend/voice_samples/`. Three different paths.

`process_voice_samples.py` printed *"No voice samples found in
`backend/voice_samples/`"* while looking somewhere else entirely, which is this
repo's own defining failure pattern in miniature: **the message and the code
disagreed, and both halves ran without complaint.** Anyone recording a reference
clip by following the scripts would have produced a file the container never sees
and had no way to tell why. Both now resolve to `backend/voice_samples/`.

---

# Part 2 — Deferred by trigger

Nothing to do now. Each becomes mandatory the day its condition holds, and each is
recorded here because the condition is easy to meet without noticing.

## 2.1 — TLS across the mesh

**Trigger: the day the mesh crosses a machine boundary.**

`nats-accounts.conf` ships per-agent users with per-subject permissions, verified
against a real `nats-server` 2.14.5 (finding **M4-S1**, roadmap **P2-1**). The
**accounts half is done; the TLS half was deliberately deferred**, because
single-host with all ports bound to `127.0.0.1` (P0-2) means the mesh is not
reachable off-box and TLS would buy nothing.

That reasoning expires the moment the humanoid-plus-server split in
[Part 6](#part-6--the-long-arc) happens, which is a stated goal. **Do not ship that
split without TLS on the mesh.**

**Known limitation, already recorded in the file itself:** a denied *subscribe*
never raises on the caller. It surfaces only through `error_cb` — a logged error
and a quietly deaf subscription. A grant that is wrong in the too-narrow direction
does not crash; it silently stops working.

## 2.2 — The loopback trust exemption

**Trigger: the day a TLS-terminating reverse proxy is introduced.**

`is_loopback_client` trusts the loopback host with no key — a deliberate decision
for zero-config single-machine setups, and correct today (finding **M4-S4**, which
M7 withdrew as a false positive on the confirmed no-proxy topology).

**Behind a proxy, every request arrives from loopback, so every caller becomes
trusted.** If a proxy is ever introduced, `is_loopback_client` must be made
proxy-aware **in the same change**, or this becomes a live HIGH the same day.

## 2.3 — Reducing the per-turn LLM call count

**Trigger: moving to a larger model.**

Roadmap **P2-4**. Attempted at Stage 4 and dropped, with two independent findings:

- Measurement 1.5 settled the prefix-caching question definitively — the two
  in-turn calls share **0** characters of prefix, so prefix caching was never a
  lever here.
- The stage-merge itself was built, mutation-tested, and dropped: a 3B model does
  not reliably continue past a JSON classification block into prose.

The second reason is a property of the model, not the design. Worth revisiting on
a larger model — which the hardware roadmap expects.

**Do not parallelise instead.** `HARDWARE.md` §5 measured aggregate throughput
rising only 16% with two models loaded, so overlapping converts latency into
memory contention. On 16 GB this is strictly worse.

---

# Part 3 — Declined, deliberately

Recorded so they are not re-opened by accident. Each was argued once, in the
ledger, and re-opening a decision the ledger already made is not completing the
roadmap — it is contradicting it.

| Item | Decision | Reasoning |
| :--- | :--- | :--- |
| **P4-3** — three dead PyO3 exports; `_split_thought` superseded; `evolved_learnings` loader with no saver | **KEEP** | "A loader without a saver is a worse asymmetry than an unused pair." Deleting the loader removes the only evidence of intended shape. |
| **P4-11** — import cycle broken with deferred imports; `app.config` process-global with fan-in 24 | **KEEP** | Both are load-bearing workarounds with no better local fix. Prefer `@computed_field` over adding logic to `ConfigMeta.__getattr__` (finding **F4**). |
| **Migrating off NATS, off Ollama, or to full-duplex speech-to-speech** | **DECLINED** | All three analysed at M6 against the brief's seven-field template and declined. Reasoning in `audit/REAL_WORLD_COMPARISON.md` §13. |
| **Bi-temporal memory edges** | **DECLINED** | A second time axis before reinforcement works (P2-13) builds on a broken base. |
| **An Isaac-style real-time control layer** | **DECLINED** | There are no actuators. What transfers is the *discipline* — no blocking call on a bus-serving loop, a stated latency budget for audio, perception off the cognition loop — carried as review criteria, not a build item. |
| **Horizontal scaling / multi-tenancy** | **DECLINED, do not resurrect** | Issues #151 and #164 were rejected as contradicting the single-family deployment; the maintainer's own answer confirmed it. |
| **Corpus-specific constants in production retrieval** | **DECLINED** | Finding **B1**. `MOCK_LLM_TEXT=true` returns strings fitted to one demo corpus; that fitting must never migrate into real retrieval paths. |

---

# Part 4 — Unanswered questions

These are decisions, not tasks. None blocks work today; each would sharpen it.

**All previously-BLOCKING questions are closed.** `audit/QUESTIONS.md` §2 still
lists three as blocking (Q-M4-1(b), Q-M2-2, Q-M1-2) — **that section is stale**;
§6 of the same file records all three as answered on 2026-08-22, and Q-M3-2 and
Q-M4-2 were closed during the leftovers pass. Read §6, not §2.

What remains is the "IMPORTANT" tier — worth answering, none urgent:

| ID | Question | What it would settle |
| :--- | :--- | :--- |
| **Q-M1-1** | The Rust agents subscribe over core NATS and publish over JetStream. Is restart-time loss on the subscribe side accepted? | Whether M1-A7 is a defect or a documented trade-off. P1-2's sensor tier already resolved it in the right *direction*; the intent is still unstated. |
| **Q-M1-3** | Is `system.tick` meant to be durable, or a transient heartbeat? | Sizes part of M1-A2. A heartbeat persisted forever suggests nobody chose. |
| **Q-M2-1** | Is `IdentityCoreStore` / `cache.sync` intended to be wired, or abandoned? | Its CHANGELOG advertises it as shipped. Wire-or-delete. |
| **Q-M2-3** | Should repeated facts reinforce graph edges? | The comment says "optionally"; the decay model implies yes. |
| **Q-M2-4** | Is tick-driven consolidation expected to finish within one 60 s tick? | Measured at 7.48 s idle / 10.08 s under VLM contention vs a 30 s AckWait — so the answer is currently "yes, comfortably", but the intent is unrecorded. |
| **Q-M3-3** | Of the subjects wired at one end only, is any a deliberate extension point? | The allowlist for the P1-8 CI check. Seven are currently allowlisted with individual justifications. |
| **Q-M3-4** | Is `user_distance` a calibrated metre measurement or a relative proximity signal? | Finding M3-A10. Four absolute-metre thresholds consume it; nothing calibrates it. |
| **Q-M3-5** | Should `agent.voice.modulation` drive prosody *across* an utterance or set one value per turn? | Largely settled by P3-13 shipping trajectories, but the contract still permits both readings. |
| **Q-M4-3** | Is the mesh trusted-by-construction on a private segment, or was auth never added? | Now partly moot — accounts shipped — but decides whether the opt-in default is right. |
| **Q-M5-1** | Is `pytest-benchmark` a regression gate or illustrative timing? | `test_vision_frame_encode_benchmark` asserts `len(x) > 100` under either reading, so today it is neither. |
| **Q-M5-2** | Must `stt-agent` run natively on macOS, or only in its container? | Changes what "runs on laptop hardware" means. |
| **Q-M6-1′** | Should visual episodic memory store traces when the source is **screen**? | The privacy boundary for *live capture* is closed; the boundary for *persisted screen content* is a different question and has not been asked. Currently: screen traces carry a hard 24 h TTL (`VISUAL_SCREEN_TRACE_TTL_H`). |

Three further questions (Q-M0-5, Q-M0-6, Q-M1-4) are classed OPTIONAL and are
effectively answered by what shipped.

---

# Part 5 — The unfinished audit surface

The audit closed as a *process* at nine of nine milestones. It did not close as
*coverage*, and the distinction is the single most important thing to carry
forward.

## 5.1 — Coverage is 17.8%

**58 of 325 applicable files were read end to end** (76 of 325 = 23.4% counting
partial reads). **249 applicable files were never opened.** Skipped files are
excluded from the denominator and individually justified in
`audit/REPOSITORY_INVENTORY.md` §3 — none were silently dropped.

**This is a second audit, not a leftover**, and it should be scoped as one. The
existing audit's own defining finding is the reason it matters: *the parts one
engineer could reason about alone are done well; the parts requiring two components
to agree fail silently, because the failing half still compiles, still passes its
own tests, and still logs as though it were working.* That pattern was confirmed
repeatedly **in places the audit never reached** — `char_offset` vs
`character_offset` across the Python/Rust boundary, `audio.playback.progress`
published by nothing, `cache.sync` subscribed by an agent no one constructed, a
`.dockerignore` silently excluding a module imported at startup, a `requests`
import that was never a declared dependency. Every one was found by making two
halves actually run against each other.

**The method that works, therefore: run the halves against each other.** Not more
reading.

## 5.2 — The nine pressure scenarios

`AUDIT.md` §17 asks for resource-pressure analysis of the **complete system running
simultaneously** across nine states: idle; voice-only; voice + cognition;
vision-only; vision + cognition; voice + vision + cognition; full multimodal; full
+ background cognition; and sustained long-running operation — determining RAM,
VRAM, CPU, GPU, disk and storage growth for each.

**None of the nine has been run.** What exists instead:

- A boot-and-connect path exercised on real infrastructure.
- Two sustained-behaviour measurements: consolidation wall-clock (7.48 s idle,
  10.08 s under real VLM contention, vs a 30 s AckWait) and `AI_AUDIO` growth
  (68,571 B/s measured, roughly **half** the ~130 KB/s that was estimated — so the
  audio tier has more headroom than assumed).
- Six Stage-3 measurement harnesses under `backend/tools/measure/` (`m11`–`m16`,
  plus `m4b`), all with a `MEASURED` / `ESTIMATED` / `UNKNOWN` provenance label.

**This is a separate measurement campaign.** It is also the one that decides
whether the humanoid is feasible on the hardware it is meant to live on, so it
should probably come before the second audit.

## 5.3 — Benchmark figures are still placeholders

Documented benchmark results are **`[TBP]`** placeholders. `MOCK_LLM_TEXT=true`
returns hardcoded strings fitted to a specific demo corpus. **No headline latency
or Recall@K figure has been measured against real infrastructure.** State targets
as targets until measured — this is a standing integrity constraint, not a to-do.

One number now exists that did not before: the eval recall gate was run against the
Stage 6 retrieval rewrite on 2026-08-24 and found **no regression** (27/48 probes
on both a pre-Stage-6 baseline and current `main`, identical probe-for-probe,
`mean score delta +0.000`). Read it precisely: it shows the rewrite did **not make
recall worse**. It does *not* show the memory layer beats its own BM25 control at
long distance — on the two hardest probe families both fail identically. That is a
finding about the eval pack's discriminating power, and it is worth fixing before
the pack is used to justify anything.

---

# Part 6 — The long arc

Not roadmap items. The direction the above is in service of.

## 6.1 — Consolidation and the fine-tuned adapter (CVS-4)

`docs/cvs4_architecture_roadmap.md` describes a consolidation loop in which the
agent's own conversation history trains a LoRA/QLoRA adapter that is then adopted
as its voice. **This has been discussed across sessions and never built.** Parts of
the same document *are* implemented, which makes the document itself a trap — read
it as a roadmap, not a description, and note that its §F.6 now contradicts the
prosody code that actually shipped.

The gate it needs already exists: `backend/evals/` answers "did this model +
persona change behaviour between two runs?" at the LLM boundary, with
deterministic scoring, provenance-carrying reports, and a `run-conversation` suite
for multi-turn recall. **No fine-tuned adapter should be adopted without passing
it.** A regression is pass→fail on a probe, not a score threshold.

Note the reproducibility lesson embedded in that harness: deterministic scoring is
not enough on its own — the *response* has to be reproducible too, and on a 3B
model it was not until the runner started unloading the model, reloading it and
burning one throwaway generation before the first scored probe.

## 6.2 — The hardware split

The current machine (Apple M5, 16 GB unified memory) is a development host, not
the target. The stated direction is a rented GPU for training and a server for the
humanoid, with the 3B model ceiling explicitly temporary.

Two things follow that are already written down above and are easy to miss:

1. **The mesh crosses a machine boundary in that topology** → [2.1](#21--tls-across-the-mesh) becomes mandatory.
2. **The model gets bigger** → [2.3](#23--reducing-the-per-turn-llm-call-count) becomes worth revisiting.

## 6.3 — What "human-likeness" is being measured against

The quality target is a cheap-tier frontier model's conversational quality, which
means **the thing being chased is post-training, not scale.** That is what makes
6.1 the central item of the long arc rather than a nice-to-have, and it is why the
eval harness probes the LLM boundary specifically — that is the seam an adapter
changes.

---

## Appendix — where the evidence lives

| Source | What it is | Tracked? |
| :--- | :--- | :--- |
| `.agents/CONTEXT.md` | **Engineering ledger. Ground truth.** What was built, measured, and deliberately left undone. | Yes |
| `audit/ISSUES.md` | All 101 findings with `file:line` evidence, as written 2026-08-22. Point-in-time; status lives in `ROADMAP.md`. | No — local only |
| `audit/ROADMAP.md` | P0–P4 disposition per finding, with dated implementation-status markers. | No — local only |
| `audit/QUESTIONS.md` | The question register. **Read §6, not §2** — §2 is stale. | No — local only |
| `audit/SECURITY.md`, `HARDWARE.md`, `PERFORMANCE.md`, `ARCHITECTURE.md`, and 6 more | Milestone reports. Evidentiary, superseded as a work queue by this file. | No — local only |
| `AUDIT.md` (repo root) | The original 1,784-line audit brief. | No — local only |
| `backend/tools/measure/out/` | Measurement artefacts with provenance labels. **Check here before claiming something was never measured.** | Yes |
| `backend/evals/` | The behavioural eval harness and its probe packs. | Yes |

**`audit/` and `AUDIT.md` are deliberately untracked and must stay that way.**
Stage every commit by explicit path; never `git add -A`. A prior sweep published
the security audit and required a force-push to undo.
