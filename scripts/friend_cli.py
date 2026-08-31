#!/usr/bin/env python3
"""AI Friend Unified CLI Tool ('friend').

Provides a single command interface for managing, interacting with, and
configuring AI Friend on macOS, Windows, and Linux.

Commands:
    friend start [--mode full|light|heavy] [--vision] [--model MODEL]
    friend stop
    friend status
    friend model [list|set MODEL|pull MODEL]
    friend talk
    friend persona
    friend voice
    friend backup export [--output PATH]
    friend backup import --file PATH [--force]
    friend logs [SERVICE]
    friend update
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import urllib.request
from pathlib import Path

__version__ = "7.0.0"


def get_repo_root() -> Path:
    current = Path(__file__).resolve().parent.parent
    if (current / "start.sh").exists() or (
        current / "docker-compose.infra.yml"
    ).exists():
        return current
    env_root = os.environ.get("AI_FRIEND_HOME")
    if env_root:
        return Path(env_root)
    return Path.home() / "AI_friend"


REPO_ROOT = get_repo_root()


def get_python_bin() -> str:
    venv_python = (
        REPO_ROOT
        / ".venv"
        / ("Scripts" if platform.system() == "Windows" else "bin")
        / ("python.exe" if platform.system() == "Windows" else "python")
    )
    if venv_python.exists() and os.access(venv_python, os.X_OK):
        return str(venv_python)
    return sys.executable


def run_cmd(cmd: list[str], cwd: Path | None = None) -> int:
    return subprocess.call(cmd, cwd=str(cwd or REPO_ROOT))


def set_env_key(key: str, value: str) -> None:
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        example = REPO_ROOT / ".env.example"
        if example.exists():
            env_file.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            env_file.touch()

    lines = env_file.read_text(encoding="utf-8").splitlines()
    updated = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"{key}={value}")
    env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def cmd_start(args: argparse.Namespace) -> int:
    if args.model:
        set_env_key("LLM_CHAT_MODEL", args.model)
        print(f"==> Configured LLM model: {args.model}")

    system = platform.system()
    if system == "Windows":
        script = REPO_ROOT / "start.ps1"
        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-Mode",
            args.mode,
        ]
        if args.vision:
            cmd.append("-Vision")
        return run_cmd(cmd)

    script = REPO_ROOT / "start.sh"
    cmd = [str(script), args.mode]
    if args.vision:
        cmd.append("--vision")
    return run_cmd(cmd)


def cmd_stop(args: argparse.Namespace) -> int:
    print("==> Stopping AI Friend mesh containers...")
    cmd = [
        "docker",
        "compose",
        "-f",
        "docker-compose.infra.yml",
        "-f",
        "docker-compose.prod.yml",
        "down",
    ]
    return run_cmd(cmd)


def cmd_status(args: argparse.Namespace) -> int:
    prereq_script = REPO_ROOT / "scripts" / "bootstrap" / "check_prereqs.py"
    py_bin = get_python_bin()
    run_cmd([py_bin, str(prereq_script)])
    print("\n==> Active Docker Container Services:")
    return run_cmd(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.infra.yml",
            "-f",
            "docker-compose.prod.yml",
            "ps",
        ]
    )


def cmd_model(args: argparse.Namespace) -> int:
    ollama_url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    if args.model_action == "list" or not args.model_action:
        print("==> Popular Models Tested with AI Friend:")
        popular = [
            (
                "llama3.2:3b",
                "Default Recommended: Fast, empathetic, 3B parameters (~2.0 GB VRAM)",
            ),
            (
                "qwen2.5:3b",
                "High multilingual fluidity & conversational nuance (~2.0 GB VRAM)",
            ),
            (
                "qwen2.5:7b",
                "Deep conversational depth & complex problem solving (~4.7 GB VRAM)",
            ),
            (
                "deepseek-r1:7b",
                "High reasoning & chain-of-thought analysis (~4.7 GB VRAM)",
            ),
            (
                "deepseek-r1:1.5b",
                "Fast chain-of-thought for lower RAM devices (~1.2 GB VRAM)",
            ),
            (
                "llama3.2:1b",
                "Ultra-lightweight: for 8GB RAM laptops & low-power devices (~1.1 GB VRAM)",
            ),
            (
                "mistral:7b",
                "Balanced literary eloquence & structured roleplay (~4.1 GB VRAM)",
            ),
            (
                "claude-3-5-sonnet",
                "Cloud API Fallback (Set LLM_PROVIDER=anthropic in .env)",
            ),
        ]
        for name, desc in popular:
            print(f"  • \033[1m{name:<18}\033[0m {desc}")

        # Check local Ollama installed models
        try:
            req = urllib.request.Request(f"{ollama_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                installed = [m.get("name", "") for m in data.get("models", [])]
                if installed:
                    print("\n==> Models currently installed in your local Ollama:")
                    for m in installed:
                        print(f"    ✓ {m}")
        except Exception:
            pass
        return 0

    if args.model_action == "set":
        if not args.name:
            print(
                "Error: Specify model name (e.g. friend model set qwen2.5:14b or friend model set claude-3-5-sonnet)"
            )
            return 1

        name = args.name.strip()
        # Auto-configure provider
        if any(c in name.lower() for c in ("claude", "anthropic")):
            set_env_key("LLM_PROVIDER", "anthropic")
            set_env_key("LLM_CHAT_MODEL", name)
            print(
                f"✓ Configured Cloud Provider: \033[1mAnthropic\033[0m with model \033[1m{name}\033[0m"
            )
            print("  (Make sure ANTHROPIC_API_KEY is set in your .env file)")
        elif any(c in name.lower() for c in ("gpt-", "openai", "o1-", "o3-")):
            set_env_key("LLM_PROVIDER", "openai")
            set_env_key("LLM_CHAT_MODEL", name)
            print(
                f"✓ Configured Cloud Provider: \033[1mOpenAI\033[0m with model \033[1m{name}\033[0m"
            )
            print("  (Make sure OPENAI_API_KEY is set in your .env file)")
        else:
            set_env_key("LLM_PROVIDER", "ollama")
            set_env_key("LLM_CHAT_MODEL", name)
            print(
                f"✓ Configured Local Engine: \033[1mOllama\033[0m with model \033[1m{name}\033[0m"
            )
            print(
                f"  (Run `friend model pull {name}` to pull weights locally if not already installed)"
            )
        return 0

    if args.model_action == "pull":
        if not args.name:
            print(
                "Error: Specify model name to pull (e.g. friend model pull deepseek-r1:7b)"
            )
            return 1
        print(f"==> Pulling model '{args.name}' via Ollama...")
        return run_cmd(["ollama", "pull", args.name])

    return 0


def cmd_talk(args: argparse.Namespace) -> int:
    py_bin = get_python_bin()
    return run_cmd([py_bin, "-m", "scripts.talk"], cwd=REPO_ROOT / "backend")


def cmd_persona(args: argparse.Namespace) -> int:
    py_bin = get_python_bin()
    return run_cmd([py_bin, "-m", "scripts.create_friend"], cwd=REPO_ROOT / "backend")


def cmd_voice(args: argparse.Namespace) -> int:
    py_bin = get_python_bin()
    voice_script = REPO_ROOT / "backend" / "scripts" / "audio" / "record_voice.py"
    return run_cmd([py_bin, str(voice_script), "--duration", str(args.duration)])


def cmd_backup_export(args: argparse.Namespace) -> int:
    py_bin = get_python_bin()
    export_script = REPO_ROOT / "backend" / "scripts" / "export_friend.py"
    cmd = [py_bin, str(export_script)]
    if args.output:
        cmd.extend(["--out", args.output])
    if args.skip_neo4j:
        cmd.append("--skip-neo4j")
    return run_cmd(cmd)


def cmd_backup_import(args: argparse.Namespace) -> int:
    py_bin = get_python_bin()
    import_script = REPO_ROOT / "backend" / "scripts" / "import_friend.py"
    cmd = [py_bin, str(import_script), "--archive", args.file]
    if args.force:
        cmd.append("--force")
    return run_cmd(cmd)


def cmd_logs(args: argparse.Namespace) -> int:
    cmd = [
        "docker",
        "compose",
        "-f",
        "docker-compose.infra.yml",
        "-f",
        "docker-compose.prod.yml",
        "logs",
        "-f",
    ]
    if args.service:
        cmd.append(args.service)
    return run_cmd(cmd)


def cmd_update(args: argparse.Namespace) -> int:
    print("==> Updating AI Friend from GitHub...")
    run_cmd(["git", "pull", "--ff-only"])
    print("==> Rebuilding containers...")
    return run_cmd(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.infra.yml",
            "-f",
            "docker-compose.prod.yml",
            "build",
        ]
    )


def cmd_vision(args: argparse.Namespace) -> int:
    action = args.vision_action or "status"
    if action == "on":
        set_env_key("ENABLE_VISION", "true")
        set_env_key("VLM_MODEL", "moondream")
        print(
            "✓ Enabled Visual Appraisal (Moondream VLM). Restarting mesh with vision profile..."
        )
        return cmd_start(argparse.Namespace(mode="full", vision=True, model=None))
    elif action == "off":
        set_env_key("ENABLE_VISION", "false")
        print("✓ Disabled Visual Appraisal. Vision agent will not start.")
        return 0
    else:
        env_file = REPO_ROOT / ".env"
        enabled = False
        if env_file.exists():
            enabled = "ENABLE_VISION=true" in env_file.read_text(encoding="utf-8")
        status_label = (
            "\033[1;32mEnabled (Moondream VLM)\033[0m"
            if enabled
            else "\033[1;30mDisabled\033[0m"
        )
        print(f"==> Visual Appraisal Status: {status_label}")
        print("  • Toggle with: `friend vision on` or `friend vision off`")
        return 0


def cmd_init(args: argparse.Namespace) -> int:
    from scripts.bootstrap.env_wizard import run_init_wizard

    return run_init_wizard()


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="friend",
        description="AI Friend — Model-Agnostic Management & Interaction CLI Tool",
    )
    parser.add_argument("--version", action="version", version=f"friend {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init
    p_init = subparsers.add_parser(
        "init", help="Run interactive environment & model setup wizard"
    )
    p_init.set_defaults(func=cmd_init)

    # vision
    p_vision = subparsers.add_parser(
        "vision", help="Inspect or toggle camera/screen visual appraisal"
    )
    p_vision.add_argument(
        "vision_action",
        nargs="?",
        choices=["on", "off", "status"],
        default="status",
        help="Vision action",
    )
    p_vision.set_defaults(func=cmd_vision)

    # start
    p_start = subparsers.add_parser("start", help="Start the 9-agent cognitive mesh")
    p_start.add_argument(
        "mode",
        nargs="?",
        default="full",
        choices=["full", "light", "heavy"],
        help="Launch profile mode",
    )
    p_start.add_argument(
        "--vision", action="store_true", help="Enable Moondream VLM vision agent"
    )
    p_start.add_argument(
        "--model",
        help="Select LLM model (e.g. llama3.2:3b, qwen2.5:7b, deepseek-r1:7b)",
    )
    p_start.set_defaults(func=cmd_start)

    # model
    p_model = subparsers.add_parser(
        "model", help="Select, pull, and inspect any local or cloud LLM model"
    )
    p_model.add_argument(
        "model_action",
        nargs="?",
        choices=["list", "set", "pull"],
        default="list",
        help="Action to perform",
    )
    p_model.add_argument(
        "name",
        nargs="?",
        help="Model name (e.g. qwen2.5:7b, deepseek-r1:7b, llama3.2:1b)",
    )
    p_model.set_defaults(func=cmd_model)

    # stop
    p_stop = subparsers.add_parser("stop", help="Stop all running mesh services")
    p_stop.set_defaults(func=cmd_stop)

    # status
    p_status = subparsers.add_parser(
        "status", help="Display system status, hardware scan, and container health"
    )
    p_status.set_defaults(func=cmd_status)

    # talk
    p_talk = subparsers.add_parser(
        "talk", help="Start interactive conversation REPL in terminal"
    )
    p_talk.set_defaults(func=cmd_talk)

    # persona
    p_persona = subparsers.add_parser(
        "persona", help="Run the natural language persona authoring wizard"
    )
    p_persona.set_defaults(func=cmd_persona)

    # voice
    p_voice = subparsers.add_parser(
        "voice", help="Enroll an 8-second custom voice sample"
    )
    p_voice.add_argument(
        "--duration", type=int, default=8, help="Recording length in seconds"
    )
    p_voice.set_defaults(func=cmd_voice)

    # backup
    p_backup = subparsers.add_parser(
        "backup", help="Export or restore 4-store friend archives"
    )
    b_subs = p_backup.add_subparsers(dest="backup_action")

    b_exp = b_subs.add_parser("export", help="Export friend state to .tar.gz")
    b_exp.add_argument("--output", help="Output archive filepath")
    b_exp.add_argument("--skip-neo4j", action="store_true", help="Skip Neo4j subgraphs")
    b_exp.set_defaults(func=cmd_backup_export)

    b_imp = b_subs.add_parser("import", help="Restore friend state from .tar.gz")
    b_imp.add_argument("--file", required=True, help="Input archive file")
    b_imp.add_argument(
        "--force", action="store_true", help="Confirm destructive table overwrite"
    )
    b_imp.set_defaults(func=cmd_backup_import)

    # logs
    p_logs = subparsers.add_parser("logs", help="Tail live container logs")
    p_logs.add_argument(
        "service", nargs="?", help="Specific service name (e.g. brain_agent, postgres)"
    )
    p_logs.set_defaults(func=cmd_logs)

    # update
    p_update = subparsers.add_parser(
        "update", help="Pull latest release updates from Git and rebuild"
    )
    p_update.set_defaults(func=cmd_update)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    if hasattr(args, "func"):
        return args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
