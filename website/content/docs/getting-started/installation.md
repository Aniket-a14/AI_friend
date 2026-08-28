# Installation

You need [Docker](https://docs.docker.com/get-docker/) and
[Ollama](https://ollama.com) (`ollama serve` running, host-native — not
containerized by default) on a machine with at least ~16GB RAM. A GPU is
optional: a 3B-class Ollama model runs on CPU, and real-time voice cloning
(GPT-SoVITS) is meaningfully faster with one but not required to boot.

```bash
git clone https://github.com/Aniket-a14/AI_friend.git
cd AI_friend
cp .env.example .env   # fill in the secrets it asks for
./start.sh              # or: make start
```

`start.sh` does the whole boot sequence itself and refuses to half-start: it
creates the shared Docker network, confirms Ollama is reachable and pulls
the required models, ships a bundled default voice so the agent can speak
before you've recorded your own, brings up Postgres/Neo4j/Redis/NATS/
LiveKit, waits for Postgres to actually be healthy before pushing the
database schema, then starts the right container set for your chosen mode.

## Launch modes

```bash
./start.sh light             # cognitive-only: no real-time voice/STT
./start.sh heavy             # cognitive + local Whisper STT, no voice cloning
./start.sh full               # the default: everything, including voice cloning
./start.sh full --vision      # + the vision agent (Linux host only)
```

`light` and `heavy` exist for machines that can't comfortably run real-time
voice cloning alongside everything else — the cognitive core and memory
work the same either way, you just lose live speech in and out.

## Hardware

There is no packaged install yet — you run this from source via Docker
Compose. Development has run on a 16GB unified-memory MacBook with a
~3B-parameter Ollama model on CPU. A GPU (local or rented) speeds up
real-time voice cloning and STT, and is effectively required for GPT-SoVITS
*fine-tuning* on your own voice recordings — see the
[voice training guide](/docs/guides/voice-training) for that path rather
than doing it on a laptop.

An optional cloud LLM fallback exists for hardware that can't run a local
model comfortably (`LLM_PROVIDER=anthropic` in `.env`, opt-in, sends
conversation to a third party by design — see `.env.example`).

## Health check

```bash
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml ps
```

Next: [Quickstart](/docs/getting-started/quickstart) to actually create
your friend.
