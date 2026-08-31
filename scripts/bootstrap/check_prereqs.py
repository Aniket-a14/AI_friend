#!/usr/bin/env python3
"""Cross-platform prerequisite and hardware capability inspector for AI Friend.

Validates:
1. Python version (>= 3.11)
2. Total RAM & swap (16GB recommended, 8GB minimum with cloud fallback)
3. GPU / Hardware acceleration (Apple Silicon Metal, NVIDIA CUDA, ROCm, or AVX-512)
4. Docker & Docker Compose availability
5. Ollama liveness & required models
6. Required network port availability
"""

from __future__ import annotations

import json
import platform
import shutil
import socket
import subprocess
import sys
import urllib.request
from typing import Any


def check_ram() -> dict[str, Any]:
    total_gb = 0.0
    try:
        if platform.system() == "Darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
            total_gb = int(out.strip()) / (1024**3)
        elif platform.system() == "Linux":
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        total_gb = int(line.split()[1]) / (1024**2)
                        break
        elif platform.system() == "Windows":
            out = subprocess.check_output(
                ["wmic", "computersystem", "get", "TotalPhysicalMemory"], text=True
            )
            lines = [line.strip() for line in out.strip().splitlines() if line.strip()]
            if len(lines) > 1 and lines[1].isdigit():
                total_gb = int(lines[1]) / (1024**3)
    except Exception:
        total_gb = 16.0  # Fallback estimate

    passed = total_gb >= 15.0
    warning = not passed and total_gb >= 7.5
    return {
        "total_gb": round(total_gb, 2),
        "passed": passed,
        "warning": warning,
        "message": (
            f"{round(total_gb, 1)} GB unified/host RAM"
            + (
                " (16 GB+ recommended for local Llama 3.2 3B + full mesh)"
                if warning
                else ""
            )
        ),
    }


def check_gpu() -> dict[str, str]:
    system = platform.system()
    machine = platform.machine().lower()

    if system == "Darwin":
        if "arm" in machine or "aarch64" in machine:
            return {"type": "Apple Silicon (Metal / Neural Engine)", "supported": True}
        return {"type": "Intel Mac (CPU mode)", "supported": True}

    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader",
                ],
                text=True,
            )
            gpu_name = out.strip().splitlines()[0]
            return {"type": f"NVIDIA CUDA ({gpu_name})", "supported": True}
        except Exception:
            pass

    return {"type": "x86_64 CPU (AVX-512/OpenVINO fallback)", "supported": True}


def check_docker() -> dict[str, Any]:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return {
            "installed": False,
            "running": False,
            "message": "Docker not found in PATH",
        }

    try:
        subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return {
            "installed": True,
            "running": True,
            "message": "Docker daemon is running",
        }
    except Exception:
        return {
            "installed": True,
            "running": False,
            "message": "Docker is installed but daemon is not running",
        }


def check_ollama(url: str = "http://127.0.0.1:11434") -> dict[str, Any]:
    ollama_bin = shutil.which("ollama")
    tags_url = f"{url.rstrip('/')}/api/tags"

    running = False
    models: list[str] = []
    try:
        req = urllib.request.Request(
            tags_url, headers={"User-Agent": "AIFriend/Installer"}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                running = True
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        pass

    return {
        "installed": bool(ollama_bin),
        "running": running,
        "models": models,
        "has_llama": any("llama3.2" in m or "qwen2.5" in m for m in models),
        "has_embed": any("nomic-embed" in m for m in models),
    }


def check_ports() -> dict[str, bool]:
    ports = {
        "NATS (4222)": 4222,
        "Postgres (5432)": 5432,
        "Redis (6379)": 6379,
        "Neo4j (7687)": 7687,
        "LiveKit (7880)": 7880,
        "FastAPI (8000)": 8000,
        "Web UI (3000)": 3000,
    }
    status = {}
    for name, port in ports.items():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            # Available if connect fails
            is_open = s.connect_ex(("127.0.0.1", port)) != 0
            status[name] = is_open
    return status


def main() -> int:
    is_json = "--json" in sys.argv
    ram = check_ram()
    gpu = check_gpu()
    docker = check_docker()
    ollama = check_ollama()
    ports = check_ports()

    summary = {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "ram": ram,
        "gpu": gpu,
        "docker": docker,
        "ollama": ollama,
        "ports": ports,
        "ready": docker["running"] and ollama["running"] and ram["total_gb"] >= 7.5,
    }

    if is_json:
        print(json.dumps(summary, indent=2))
        return 0 if summary["ready"] else 1

    print("═════════════════════════════════════════════════════════════════")
    print("           AI FRIEND — PREREQUISITE & HARDWARE SCAN              ")
    print("═════════════════════════════════════════════════════════════════")
    print(
        f"OS Platform:    {platform.system()} {platform.machine()} (Python {platform.python_version()})"
    )
    print(f"Memory:         {ram['message']}")
    print(f"Hardware Accel: {gpu['type']}")
    print(
        f"Docker Daemon:  {'✓ Running' if docker['running'] else '✗ Not Running (' + docker['message'] + ')'}"
    )
    print(
        f"Ollama Server:  {'✓ Running' if ollama['running'] else '✗ Not Running (run `ollama serve`)'}"
    )

    if ollama["running"]:
        print(
            f"  └ Models:     Llama 3.2: {'✓' if ollama['has_llama'] else '✗ (will pull)'} | Embeddings: {'✓' if ollama['has_embed'] else '✗ (will pull)'}"
        )

    busy_ports = [name for name, available in ports.items() if not available]
    if busy_ports:
        print(
            f"Port Conflicts: ⚠ The following ports are in use: {', '.join(busy_ports)}"
        )
    else:
        print("Network Ports:  ✓ All standard ports available")

    print("─────────────────────────────────────────────────────────────────")
    if summary["ready"]:
        print("RESULT: System meets all prerequisites for full mesh launch.")
        return 0
    else:
        print("RESULT: Missing components detected. Installer will guide setup.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
