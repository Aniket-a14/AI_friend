# BRINGING IT TO LIFE

**How to run the brain, voice and eyes of your humanoid on this laptop — and give
it a personality and a voice that are actually its own.**

Written 2026-08-24, against `main` at the merge of PR #203.

This is the operational companion to [FUTURE_WORK.md](FUTURE_WORK.md). That file
says what is left to build. This one says how to run what exists.

> **A note on tone, deliberately.** `README.md` is the polished front door and it
> overstates completeness relative to the engineering ledger. This document does
> not. Where something does not work yet, it says so and names what would fix it,
> because the fastest way to lose an evening here is to follow a confident
> instruction for a path nobody has walked.

---

## 0. What you are actually starting

Nine or so processes that talk to each other over a message bus, not one program.

| Layer | What it is | Where it runs |
| :--- | :--- | :--- |
| **The brain** | `brain_agent` (the cognitive turn), `system_agent` (ticks, decay), `subconscious_agent` (background reflection, graph persistence), `surfacing_agent` | Python, containers |
| **Memory** | Postgres (episodes), Qdrant (vectors), Neo4j (the entity graph), Redis (cache) | Containers |
| **The voice** | `voice_agent` (Rust) → GPT-SoVITS synthesis | Rust container + `local_voice` |
| **The ears** | `stt_agent` (Rust) — Whisper, plus SenseVoice for tone | Rust container |
| **The eyes** | `vision_agent` — moondream VLM | Container, **opt-in** |
| **The mouth/ears wire** | `transport_agent` + LiveKit (WebRTC) | Containers |
| **Thinking** | Ollama | **Host-native, not a container** |

They coordinate over **NATS JetStream**. Nothing here is a function call between
components — if two halves disagree about a message shape, both keep running and
one of them silently stops working. That failure mode is the single most common
one in this system and §9 is mostly about recognising it.

---

## 1. The machine you are on, honestly

This laptop is an **Apple M5 with 16 GB of unified memory**. That number governs
almost every decision below, so it is worth being blunt about what it means.

**Unified memory is shared.** The model, the vector store, the graph database, the
Docker VM and the synthesiser all draw from the same 16 GB. There is no separate
VRAM to spill into. Running "everything at once" is not a configuration choice
here; it is the thing that makes the machine swap.

What that implies in practice:

- **Ollama runs on the host, not in Docker.** This is the default and it is
  deliberate — a containerized Ollama exists behind the `docker-ollama` profile
  but is not started by a plain `up`. Host-native Ollama gets direct access to the
  Metal backend; containerized does not.
- **A 3B model is the working ceiling** (`llama3.2:3b` is the configured
  `LLM_FAST_MODEL`). This is temporary and acknowledged as such — the roadmap
  expects a rented GPU for training and a server for the humanoid.
- **GPT-SoVITS falls back to CPU/FP32 on this machine.** Its image is
  CUDA-oriented; on Apple silicon it detects no GPU and runs on CPU in FP32, which
  is memory-heavy and slow. This is why the voice container is the first thing to
  stop when the machine gets tight.
- **Do not run the vision profile and the voice stack simultaneously** while you
  are still learning the system. Each is fine; together on 16 GB they contend.

**Pick a mode rather than starting everything:**

| Mode | What runs | Use it for |
| :--- | :--- | :--- |
| **Light** | Cognition, memory, text agents. No WebRTC, no STT, no synthesis. | Personality work, memory work, evals. **Start here.** |
| **Heavy** | Light + local Whisper STT. | Talking *to* it. |
| **Full** | Everything: real-time WebRTC voice in and out, voice cloning. | Actually living with it. |
| **`--profile vision`** | Adds the eyes, on top of any of the above. | Opt-in, separately. |

---

## 2. One-time prerequisites

```bash
# 1. Ollama, host-native. Install from ollama.com, then:
ollama serve                      # leave running
ollama pull llama3.2:3b           # the cognitive model
ollama pull nomic-embed-text      # embeddings for memory retrieval
ollama pull moondream             # only if you want the eyes

# 2. Python environment. The venv lives at the REPO ROOT; pytest runs from backend/.
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt

# 3. The shared Docker network the mesh attaches to.
docker network create ai_mesh_network

# 4. Your environment file.
cp .env.example .env
```

**Then edit `.env` before you start anything.** A straight unedited copy is
designed to fail loudly: `.env.example` ships `ENVIRONMENT=production`, which arms
a guard that refuses to boot on placeholder secrets. That guard exists because a
silent boot on default credentials is worse than a crash. At minimum set:

- `POSTGRES_PASSWORD`, `NEO4J_PASSWORD` — real values, not the placeholders.
- `LIVEKIT_KEYS` — format `"apikey: secret"`, and **the secret must be at least 32
  characters** or LiveKit refuses to start. Note that this environment variable
  *fully replaces* any keys in `livekit.yaml` rather than merging with them —
  verified empirically against a real server, not assumed.
- `NATS_*_PASSWORD` — only if you want the scoped mesh credentials. They are
  opt-in on both sides; an unconfigured mesh connects exactly as it did before
  `nats-accounts.conf` existed. Fine to leave unset on a single machine.

---

## 3. First boot

### Step 1 — infrastructure

```bash
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml \
  up -d postgres neo4j redis nats livekit
```

Container names are not the service names, which matters when you go looking:
`postgres` → `postgres_db`, `neo4j` → `brain_graph`, `redis` → `brain_cache`,
`nats` → `nats_mesh`, `livekit` → `local_sfu`, `qdrant` → `brain_vectors`,
`gpt-sovits` → `local_voice`.

Wait for health before continuing:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### Step 2 — hydrate the schema

Postgres is mapped to host port **5433**, not 5432, to avoid colliding with a
local install.

```bash
export DIRECT_URL="postgresql://ai_friend:YOUR_DB_PASSWORD@127.0.0.1:5433/ai_friend_db"
cd frontend && npx prisma generate && npx prisma db push && cd ..
```

### Step 3 — write the personality *before* the first agent boot

**This is the step with a one-way door in it.** See §4. Do it now, not later.

### Step 4 — start the agents

```bash
# Light — recommended for a first run
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml \
  -f docker-compose.light.yml up -d --build

# Heavy — adds local STT
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml \
  -f docker-compose.heavy.yml up -d --build

# Full — everything
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml up -d --build
```

If Apple-silicon builds time out compiling PyTorch, build the cached layers
sequentially first:

```bash
docker build -t ai-friend/base:v1 -f backend/Dockerfile.base ./backend
docker build -t ai-friend/full:v1 --build-arg BASE_IMAGE=ai-friend/base:v1 \
  -f backend/Dockerfile.full ./backend
```

---

## 4. Giving it a personality

Two files, and they do genuinely different jobs. Getting this distinction right is
most of what makes the result feel like a person rather than a chatbot with a
system prompt.

### `config/persona.toml` — temperament

Who they *are*: name, tone, the few sentences that colour every reply, and the
numeric temperament that drives affect.

**It is read exactly once, on the very first boot, and then never again.** Editing
it later changes nothing; the log will tell you it was skipped.

That is not a limitation, it is the design. The reasoning, from the source itself:
a file that keeps re-asserting who someone is means *they can never grow away from
the document, and the document is always the least current description of them.*
After first boot, everything lives in the durable store and evolves through
reflection.

Fields sort into three tiers, enforced by the schema rather than by convention:

| Tier | Meaning | Editable? |
| :--- | :--- | :--- |
| **CONSTITUTIONAL** | Temperament — who they fundamentally are. Reflection does not rewrite these. | Seeded once |
| **ADAPTIVE** | Where the *relationship* starts. Trust, attachment. These move on their own. | Seeded once, then owned by the agent |
| **IMMUTABLE** | Safety invariants. **Not in the file and cannot be put in it** — naming one is rejected with a warning. | Never |

Bounds are deliberately tighter than the maths permits, each guarding a specific
failure mode. `mood_decay_rate` must be `> 0` because zero is a permanent mood
lock. `baseline_valence` is capped at ±0.6 because *a friend pinned at maximum
happiness can never be sad with you.* **The rule behind all of them: a personality
may be shaped, but it must remain moveable.** A character who cannot be affected by
what happens to them is a puppet.

Two temperament fields worth understanding, because they are the ones people get
wrong: `dopamine_halflife_s` (default 90 s) and `cortisol_halflife_s` (default
600 s) are **CONSTITUTIONAL, not deployment settings.** How long a reward glows and
a fright lingers *is* temperament. A friend whose cortisol half-life is an hour is
a different person from one whose is a minute.

### `config/biography.md` — history

Everything that is only *sometimes* relevant. This file is **not** pasted into the
prompt — each blank-line-separated paragraph becomes one episodic memory, tagged
with the heading it sits under. Only passages relevant to what is being said come
back. That is what lets it be long.

How to write it well:

- **Prose, not bullet-point facts.** "She goes quiet when she is angry rather than
  loud, and it takes a day" recalls far better than `trait: reserved`, because
  retrieval matches on meaning.
- **One idea per paragraph** — it becomes one memory and surfaces cleanly alone.
- **You can extend it later.** Only new passages are seeded; existing ones are left
  alone, so adding to it never duplicates.

### Starting over

```bash
cd backend && ../.venv/bin/python -m scripts.reset_persona
```

Clears the stored persona and every file-seeded memory so the next boot re-reads
both files as if it were the first. **Memories from real conversations are kept.**
It requires typing a confirmation phrase in full rather than a `y/n` — the
destructive half is irreversible, and a reflexive "y" is the most likely way to
lose a persona someone spent an evening writing.

Inspect what is actually loaded at any point:

```bash
cd backend && ../.venv/bin/python -m scripts.show_persona
```

---

## 5. Giving it a voice

GPT-SoVITS clones **zero-shot from a reference clip**. There are two levels, and
you almost certainly want the first.

### Level 1 — a cloned voice from one clip (minutes)

Whatever audio sits at the reference path *is what your humanoid sounds like*.

```bash
cd backend && ../.venv/bin/python scripts/audio/record_voice.py
# It asks for a duration (default 120 s) and a filename.
# For a REFERENCE clip, answer ~8, not 120. The 120 s default is sized for a
# fine-tuning dataset (Level 3), not for zero-shot cloning.
```

It saves into `backend/voice_samples/`, which is the only directory the
synthesiser can see — `docker-compose.infra.yml` bind-mounts it to
`/workspace/GPT-SoVITS/output`, and that is what `output/...` resolves against.

Then point `.env` at the clip:

```bash
REF_AUDIO_PATH=output/sample_en_gold.wav
REF_TEXT=the exact transcript of that clip, word for word
```

The path is `output/...` because `backend/voice_samples/` is mounted into the
container at `/workspace/GPT-SoVITS/output`. **`REF_TEXT` must match the audio
exactly** — the model conditions on the pairing, and a wrong transcript degrades
every utterance.

For the reference clip itself: **5–10 seconds, clean, neutral tone, no background
noise, no music, one speaker.** Longer is not better. Neutral matters because
everything else is modulated *relative* to it.

> ### ⚠️ Known gap, and the first thing you will hit
>
> `backend/voice_samples/` is **empty**, and nothing in the repository provisions
> `sample_en_gold.wav` — but the bootstrap and healthcheck scripts both probe it.
> Result: `local_voice` boots, loads weights, serves on 9871, and its healthcheck
> returns **400 Bad Request** forever.
>
> **Recording your own clip and setting `REF_TEXT` is what fixes this**, and it is
> the same action as choosing the voice. Tracked as
> [FUTURE_WORK.md §1.3](FUTURE_WORK.md#13--the-missing-reference-clip).

### Level 2 — four emotional reference clips (an evening)

The agent selects a reference per turn from its own affect state. Record four more
clips in the same voice — calm, warm, concerned, excited — and set both members of
each pair:

```bash
REF_AUDIO_PATH_CALM=output/calm.wav
REF_TEXT_CALM=transcript of the calm clip
# ...WARM, CONCERNED, EXCITED likewise
```

**Both members of a pair must be set together**, or the whole pair is ignored — a
lone audio path with no transcript is worse than falling back to neutral. Any
unset pair silently falls back, so setting none behaves exactly like the
single-clip setup. This is the single highest-return thing you can do for
perceived humanness right now, because it makes affect *audible* rather than just
modelled.

### Level 3 — a fine-tuned voice (a day, plus a GPU)

Train dedicated weights and point at them:

```bash
CUSTOM_GPT_PATH=GPT_weights/ai_friend_voice.ckpt
CUSTOM_SOVITS_PATH=SoVITS_weights/ai_friend_voice.pth
```

See [GPT_SOVITS_INSTALL.md](GPT_SOVITS_INSTALL.md). Realistically this belongs on
the rented GPU, not here. Use `scripts/audio/process_voice_samples.py` to organise
a multi-file training set.

### What is *not* wired yet

`pause_bias` — arousal-driven pause length — is computed and then thrown away.
Every other prosody dimension drifts across an utterance; pause length is frozen.
See [FUTURE_WORK.md §1.1](FUTURE_WORK.md#11--pause_bias-arousal-driven-pause-length).
`tempo_wpm` is worse: it is measured wrongly, and §1.2 explains why wiring it as-is
would make the agent *less* human.

**There is deliberately no fallback voice.** If synthesis fails, it stays silent
rather than speaking in a different voice — a friend whose voice changes mid-
conversation is not a friend. The circuit-breaker settings govern same-engine
recovery only.

---

## 6. Giving it eyes

Vision is **opt-in**, gated behind a profile, and not part of a default `up`:

```bash
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml \
  --profile vision up -d vision_agent
```

It uses `moondream` through host Ollama for visual appraisal and spatial
reasoning. On Linux, screen capture and camera passthrough need the X11 volume and
`/dev/video0` device lines uncommented in `docker-compose.prod.yml`; on macOS,
camera passthrough into Docker is not straightforward and this is one of the
places the system is genuinely less capable on this host.

**Privacy boundaries already in force**, worth knowing before you point a camera
at your life:

- Screen captures carry a hard TTL — `VISUAL_SCREEN_TRACE_TTL_H`, default **24
  hours**.
- Camera traces follow the normal memory lifecycle (ACT-R decay).
- Dead-letter logging records a payload's length and SHA-256, **not** its content —
  changed specifically because it had been putting user speech into log files.

The open question nobody has answered: whether persisted *screen* content should
be stored at all, as distinct from live capture. See
[FUTURE_WORK.md](FUTURE_WORK.md#part-4--unanswered-questions), Q-M6-1′.

---

## 7. Verifying it is actually alive

Container health is not aliveness. Everything in this system is built so that a
broken half keeps running and logging normally, so check the seams.

```bash
# 1. Everything up?
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml ps

# 2. Do the message subjects actually connect at both ends?
cd backend && ../.venv/bin/python scripts/check_subject_wiring.py
```

That second one is the important one. It is the CI gate for the defining failure
mode of this architecture. Seven subjects are currently allowlisted with
individual written justifications — that is expected. What you care about is
anything *new*.

```bash
# 3. Does it still behave the way it did yesterday?
cd backend
../.venv/bin/python -m evals run --model llama3.2:3b --out evals/out/today.json
../.venv/bin/python -m evals compare evals/out/baseline.json evals/out/today.json \
    --fail-on-regression
```

**Pass `--model` explicitly.** The client's hardcoded default is `llama3.2:1b`,
which is probably not pulled — and a run against a missing model returns "Error
generating response." for *every* probe, scoring 0/48 while looking like a
completed run. Matching totals on both sides of a comparison is not by itself
evidence of anything.

```bash
# 4. Does a fact survive distance? (needs Postgres, Qdrant, Neo4j up)
../.venv/bin/python -m evals run-conversation --model llama3.2:3b \
    --retrieval bm25 --retrieval memory --num-ctx 8192 --out evals/out/recall.json
```

Two failure modes are surfaced rather than scored, because either makes the number
meaningless rather than merely low: **`plant out`** (the strategy never showed the
model the fact) and **`fits NO`** (context exceeded `num_ctx`, and truncation
happens from the front, which is exactly where the planted fact sits).

⚠️ **`--retrieval memory` writes every transcript turn into the live stores** and
removes them at the end. Point it at a throwaway database unless you mean to write
into your agent's actual memory.

And the repo's own bar, before you consider any change done:

```bash
cd backend
../.venv/bin/python -m pytest -q --junit-xml=/tmp/res.xml   # parse the XML
../.venv/bin/python -m ruff check .
cargo check --workspace && cargo test --package stt-agent --package voice-agent --package contracts
```

**Parse the XML.** Pytest's terminal summary is unreliable in this repo — the final
`N passed` line and even whole `=== FAILURES ===` sections get swallowed, verified
on both macOS and Windows and not a terminal-truncation artefact. Do not trust the
dots.

---

## 8. Day to day

```bash
# Watch it think
docker logs -f brain_agent

# Stop the voice stack when the machine gets tight (this is normal on 16 GB)
docker stop local_voice

# After changing anything in backend/app/contracts.py
cd backend && ../.venv/bin/python scripts/bootstrap/setup_nats_streams.py
```

That last one is not optional. `contracts.py` defines the models that cross agent
boundaries; changing one without re-running the stream setup produces exactly the
silent-mismatch failure this architecture is prone to.

---

## 9. When it breaks

The failure modes that actually happen, in rough order of frequency.

**A container crash-loops with `exec ... permission denied`.**
`docker-compose.infra.yml` bind-mounts several bootstrap scripts directly over
their in-container paths. A bind mount **completely replaces** the image's baked-in
copy, so the Dockerfile's own `RUN chmod +x` never applies at runtime — the *host*
file's permission bits are what the container executes. Fix with `chmod +x` on the
host file. (This exact bug ran unnoticed as a standing crash-loop under
`restart: always` until 2026-08-24.)

**`local_voice` is healthy-ish but every synthesis returns 400.** The missing
reference clip. See §5.

**LiveKit refuses to start.** Either the secret is under 32 characters, or
`LIVEKIT_KEYS` is set to an empty string — which is not a silent fallback to the
config file, it is a hard refusal. Unset the variable entirely if you want
`livekit.yaml`'s keys to apply.

**An agent connects but hears nothing.** If you configured scoped NATS
credentials, note that **a denied subscribe never raises on the caller.** It
surfaces only through `error_cb` — a logged error and a quietly deaf subscription.
A too-narrow grant does not crash; it silently stops working. Check
`nats-accounts.conf` against what that agent actually subscribes to.

**A cognitive turn gets redelivered / acked twice.** `BaseAgent.subscribe` acks
only after the callback returns, and a turn can run to `LLM_STREAM_MAX_SECONDS`
(120 s) — well past JetStream's default AckWait. Read finding **A1** in
`.agents/CONTEXT.md` before touching long-running consumers.

**Affect changes are lost or interleave strangely.** `StateService` owns *all*
mutation behind `self._state_lock`, and a fire-and-forget System-2 appraisal task
writes concurrently with the synchronous path. Route new affect changes through a
`StateService` method; never touch `current_state` fields directly. Hormone bursts
in particular must go through the wrappers — burst peaks are computed relative to
the tonic floor, so an unlocked release interleaving with a valence write measures
its peak against a floor that no longer exists.

**Ollama "model not found" during evals.** Pass `--model` explicitly. See §7.

---

## 10. What "a person living in this system" honestly needs next

The parts that make this feel like a person rather than a pipeline, ranked by
return on effort *from where the system actually is today*:

1. **Record the reference clip.** (§5, Level 1.) It is the single blocking gap
   between "the voice stack runs" and "the voice stack works", and it is also how
   you choose what your humanoid sounds like. Minutes of work.
2. **Record the four emotional clips.** (§5, Level 2.) This is what makes affect
   *audible*. The system already models emotion end to end and already selects a
   clip per turn from its own state — it just currently has one clip to choose
   from. An evening.
3. **Write the biography properly.** (§4.) The retrieval layer is the most
   developed part of this codebase — a learned mental lexicon built from the
   agent's own conversation, ACT-R activation, graph boost, cue expansion. It has
   very little to retrieve *from* until you write something worth retrieving.
4. **Wire `pause_bias`, then fix and wire `tempo_wpm`.**
   ([FUTURE_WORK.md §1.1–1.2](FUTURE_WORK.md#part-1--open-engineering-work).) The
   last two frozen dimensions of delivery. Both need real audio to verify, which
   is why they are the first things to do *after* you have a microphone set up for
   step 1 anyway.
5. **Run the nine pressure scenarios.**
   ([FUTURE_WORK.md §5.2](FUTURE_WORK.md#52--the-nine-pressure-scenarios).) Nobody
   has measured this system under simultaneous multimodal load. On 16 GB that is
   the measurement that decides what is actually livable on this machine versus
   what needs the server.
6. **The consolidation loop / fine-tuned adapter.**
   ([FUTURE_WORK.md §6.1](FUTURE_WORK.md#61--consolidation-and-the-fine-tuned-adapter-cvs-4).)
   The long arc. The quality being chased is a post-training problem, not a scale
   problem — which is exactly why this, and not a bigger model, is the item that
   matters most in the end.

**A closing caution that is load-bearing.** Documented benchmark figures in this
repo are placeholders (`[TBP]`), and `MOCK_LLM_TEXT=true` returns hardcoded strings
fitted to one demo corpus. No headline latency or Recall@K number has been measured
against real infrastructure. When you are deciding whether this system is ready to
live with, measure it yourself — and state targets as targets until you have.
