#!/bin/bash
# One-command start (roadmap Phase 1.6). Wraps the four manual steps
# README.md's Quick Start spells out -- network, Ollama, schema, compose --
# into one script that refuses to half-boot: each prerequisite is checked
# explicitly and fails with a clear message rather than leaving some
# containers up and others crash-looping with no obvious cause.
#
# Usage: ./start.sh [light|heavy|full] [--vision]
#   light  - cognitive-only: no real-time WebRTC voice, no Whisper STT.
#   heavy  - cognitive + local Whisper STT, no real-time voice cloning.
#   full   - the default mesh, including real-time voice cloning. (default)
#   --vision - also start vision_agent (profiles: [vision], Linux host only).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

MODE="full"
VISION=false
for arg in "$@"; do
    case "$arg" in
        light|heavy|full) MODE="$arg" ;;
        --vision) VISION=true ;;
        *)
            echo "Usage: ./start.sh [light|heavy|full] [--vision]" >&2
            exit 1
            ;;
    esac
done

echo "==> Mode: $MODE$([ "$VISION" = true ] && echo " +vision")"

# 1. Every service below reads its secrets from .env -- refuse to start
# half-configured rather than let containers crash-loop on empty passwords.
if [ ! -f .env ]; then
    echo "ERROR: .env not found at repo root. Copy .env.example to .env and fill in the secrets first." >&2
    exit 1
fi
set -a
# shellcheck disable=SC1091
source .env
set +a

# 2. Docker itself must be reachable.
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker does not appear to be running. Start Docker and try again." >&2
    exit 1
fi

# 3. The external network every service attaches to (README Step 1).
if ! docker network inspect ai_mesh_network > /dev/null 2>&1; then
    echo "==> Creating ai_mesh_network"
    docker network create ai_mesh_network
fi

# 4. Ollama is host-native by default (see docker-compose.prod.yml's
# OLLAMA_URL comment) -- every agent depends on it and none becomes healthy
# without it, so check liveness and required models before anything else.
OLLAMA_HOST_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
if ! curl -fsS -m 5 "${OLLAMA_HOST_URL%/}/api/tags" > /dev/null 2>&1; then
    echo "ERROR: Ollama is not reachable at ${OLLAMA_HOST_URL}. Install Ollama and run \`ollama serve\`, or set OLLAMA_URL in .env if it runs elsewhere." >&2
    exit 1
fi

# `ollama list` names models with a tag suffix (nomic-embed-text:latest);
# without this equivalence check, a required model given without a tag would
# never match and get needlessly re-pulled on every single run. Mirrors
# _model_exists's same "model" == "model:latest" rule in
# backend/app/runtime_bootstrap.py.
model_present() {
    local model="$1"
    if grep -qx "$model" <<< "$AVAILABLE_MODELS"; then
        return 0
    fi
    case "$model" in
        *:*) return 1 ;;
        *) grep -qx "${model}:latest" <<< "$AVAILABLE_MODELS" ;;
    esac
}

AVAILABLE_MODELS="$(ollama list 2>/dev/null | awk 'NR>1{print $1}')"
IFS=',' read -ra REQUIRED_MODELS <<< "${OLLAMA_REQUIRED_MODELS:-llama3.2:3b,nomic-embed-text}"
for model in "${REQUIRED_MODELS[@]}"; do
    if ! model_present "$model"; then
        echo "==> Pulling Ollama model: $model (this can take a while the first time)"
        ollama pull "$model"
    fi
done

# 5. Ship the bundled default voice so a fresh clone speaks before anyone
# records their own (Phase 1.1/1.5).
PYTHON_BIN="python3"
if [ -x ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
fi
"$PYTHON_BIN" backend/scripts/bootstrap/ensure_default_voice_sample.py

# 6. Bring up infra first so the schema push below has a database to push
# against -- doing this out of order is what "half-boots" a fresh clone.
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml up -d postgres neo4j redis nats livekit

echo "==> Waiting for Postgres to become healthy..."
POSTGRES_READY=false
for _ in $(seq 1 30); do
    status="$(docker inspect --format='{{.State.Health.Status}}' postgres_db 2>/dev/null || echo starting)"
    if [ "$status" = "healthy" ]; then
        POSTGRES_READY=true
        break
    fi
    sleep 2
done
if [ "$POSTGRES_READY" != true ]; then
    echo "ERROR: Postgres did not become healthy in time. Check \`docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml logs postgres\`." >&2
    exit 1
fi

# 7. Hydrate the Prisma schema (README Step 2) -- DIRECT_URL is exported
# here, before cd'ing into frontend/, because dotenv (loaded by
# prisma.config.ts) does not expand ${POSTGRES_PASSWORD}-style references
# and frontend/ has no .env of its own; an already-exported var takes
# precedence over dotenv's own (non-existent) load.
if [ -d frontend ]; then
    export DIRECT_URL="postgresql://ai_friend:${POSTGRES_PASSWORD}@127.0.0.1:5433/ai_friend_db"
    ( cd frontend && npx prisma generate && npx prisma db push )
fi

# 8. Bring up the right compose layering for the chosen mode.
COMPOSE_FILES=(-f docker-compose.infra.yml -f docker-compose.prod.yml)
case "$MODE" in
    light) COMPOSE_FILES+=(-f docker-compose.light.yml) ;;
    heavy) COMPOSE_FILES+=(-f docker-compose.heavy.yml) ;;
    full) ;;
esac

UP_ARGS=(up -d --build)
if [ "$VISION" = true ]; then
    UP_ARGS=(--profile vision "${UP_ARGS[@]}")
fi

echo "==> Starting the mesh..."
docker compose "${COMPOSE_FILES[@]}" "${UP_ARGS[@]}"

echo "==> Done. Check status with: docker compose ${COMPOSE_FILES[*]} ps"
