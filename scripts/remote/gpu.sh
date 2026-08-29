#!/usr/bin/env bash
# AI Friend - Remote GPU Controller
# Executes commands directly on the home GPU server over Tailscale SSH.

set -e

HOST="${GPU_HOST:-home-gpu}"

if [ $# -eq 0 ]; then
    echo "=================================================="
    echo "🎮 AI Friend Remote GPU Controller ($HOST)"
    echo "=================================================="
    echo "Usage: $0 <command>"
    echo ""
    echo "Examples:"
    echo "  $0 nvidia-smi              # View GPU VRAM and temperature"
    echo "  $0 ollama ps               # View currently loaded LLMs"
    echo "  $0 ollama pull hermes3:8b  # Pull a new model"
    echo "  $0 docker compose ps       # Check backend microservices"
    echo "  $0 logs brain_agent        # Tail logs of brain agent"
    echo "=================================================="
    exit 0
fi

# Special helper shortcuts
if [ "$1" == "logs" ]; then
    shift
    SERVICE="${1:-brain_agent}"
    echo "📡 Tailing logs for $SERVICE on $HOST..."
    exec ssh -t "$HOST" "cd AI_friend && docker compose logs -f $SERVICE"
fi

if [ "$1" == "status" ]; then
    echo "📊 --- GPU Hardware & Service Status ($HOST) ---"
    ssh "$HOST" "echo '=== GPU VRAM & Compute ===' && nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu --format=csv && echo '' && echo '=== Ollama Models ===' && ollama ps && echo '' && echo '=== Active Containers ===' && docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
    exit 0
fi

# General command forwarding
exec ssh "$HOST" "$@"
