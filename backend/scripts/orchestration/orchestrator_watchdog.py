#!/usr/bin/env python3
"""AI Friend Multi-Agent Orchestrator Watchdog.

Monitors:
- /Users/aniketsaha/Projects/AI_friend/personal/HANDOFF.md
- /Users/aniketsaha/Projects/AI_friend-claude-phase1 (claude/phase2)
- /Users/aniketsaha/Projects/AI_friend-codex-phase2c2e (codex/phase2c2e)

Detects commit events, runs validation, posts alerts, and triggers notifications.
"""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

BASE_REPO = Path("/Users/aniketsaha/Projects/AI_friend")
HANDOFF_PATH = BASE_REPO / "personal" / "HANDOFF.md"
CLAUDE_WT = Path("/Users/aniketsaha/Projects/AI_friend-claude")
CODEX_WT = Path("/Users/aniketsaha/Projects/AI_friend-codex")
STATUS_JSON = Path("/tmp/orchestrator_status.json")
LOG_PATH = Path("/tmp/orchestrator_watchdog.log")
PYTHON_BIN = BASE_REPO / ".venv" / "bin" / "python"


def notify(title: str, message: str) -> None:
    try:
        # Sanitize message for AppleScript
        safe_msg = message.replace('"', '\\"').replace("'", "\\'")
        safe_title = title.replace('"', '\\"').replace("'", "\\'")
        cmd = f'display notification "{safe_msg}" with title "{safe_title}"'
        subprocess.run(["osascript", "-e", cmd], check=False, capture_output=True)
    except Exception:
        pass


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def get_git_info(worktree: Path) -> tuple[str, str, bool]:
    if not worktree.exists():
        return "", "", False
    try:
        head = subprocess.check_output(
            ["git", "-C", str(worktree), "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        msg = subprocess.check_output(
            ["git", "-C", str(worktree), "log", "-1", "--pretty=%s"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        status = subprocess.check_output(
            ["git", "-C", str(worktree), "status", "--porcelain"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        is_dirty = bool(status)
        return head, msg, is_dirty
    except Exception:
        return "", "", False


def run_worktree_checks(worktree: Path, name: str) -> bool:
    log(f"Running automated quality check for {name} ({worktree})...")
    backend_dir = worktree / "backend"
    all_ok = True

    # 1. Ruff check
    try:
        res = subprocess.run(
            [str(PYTHON_BIN), "-m", "ruff", "check", "."],
            cwd=str(backend_dir),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if res.returncode == 0:
            log(f"  [RUFF] {name}: Clean")
        else:
            log(f"  [RUFF FAIL] {name}:\n{res.stdout.strip()[:300]}")
            all_ok = False
    except Exception as e:
        log(f"  [RUFF ERROR] {e}")
        all_ok = False

    # 2. Targeted pytest
    try:
        res = subprocess.run(
            [str(PYTHON_BIN), "-m", "pytest", "-q"],
            cwd=str(backend_dir),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        summary = res.stdout.strip().splitlines()[-1] if res.stdout.strip() else ""
        if res.returncode == 0:
            log(f"  [PYTEST] {name}: {summary}")
        else:
            log(f"  [PYTEST FAIL] {name}: code {res.returncode} | {summary}")
            all_ok = False
    except Exception as e:
        log(f"  [PYTEST ERROR] {e}")
        all_ok = False

    return all_ok


def main():
    log("AI Friend Orchestrator Watchdog starting...")
    notify("Orchestrator Active", "Monitoring Claude & Codex worktrees and HANDOFF.md")

    last_handoff_mtime = 0.0
    if HANDOFF_PATH.exists():
        last_handoff_mtime = os.path.getmtime(HANDOFF_PATH)

    claude_last_head, _, _ = get_git_info(CLAUDE_WT)
    codex_last_head, _, _ = get_git_info(CODEX_WT)

    log(f"Initial state: Claude @ {claude_last_head}, Codex @ {codex_last_head}")

    while True:
        try:
            # 1. Check HANDOFF.md
            if HANDOFF_PATH.exists():
                mtime = os.path.getmtime(HANDOFF_PATH)
                if mtime > last_handoff_mtime:
                    last_handoff_mtime = mtime
                    # Extract top non-header entry
                    try:
                        content = HANDOFF_PATH.read_text(encoding="utf-8")
                        lines = content.splitlines()
                        for i, line in enumerate(lines):
                            if line.startswith("### "):
                                log(f"HANDOFF update: {line}")
                                notify("HANDOFF.md Updated", line.replace("### ", ""))
                                break
                    except Exception as e:
                        log(f"Error reading HANDOFF: {e}")

            # 2. Check Claude worktree
            c_head, c_msg, c_dirty = get_git_info(CLAUDE_WT)
            if c_head and c_head != claude_last_head:
                log(f"Claude committed new HEAD: {c_head} - {c_msg}")
                notify("Claude Committed", f"[{c_head}] {c_msg[:50]} — Codex review triggered")
                run_worktree_checks(CLAUDE_WT, "Claude")
                claude_last_head = c_head

            # 3. Check Codex worktree
            x_head, x_msg, x_dirty = get_git_info(CODEX_WT)
            if x_head and x_head != codex_last_head:
                log(f"Codex committed new HEAD: {x_head} - {x_msg}")
                notify("Codex Committed", f"[{x_head}] {x_msg[:50]} — Claude review triggered")
                run_worktree_checks(CODEX_WT, "Codex")
                codex_last_head = x_head

            # 4. Check if both completed Phase 4
            both_ready = c_head != "41b2019" and x_head != "41b2019" and not c_dirty and not x_dirty

            # 5. Write status snapshot
            status = {
                "timestamp": datetime.now().isoformat(),
                "claude": {"head": c_head, "msg": c_msg, "dirty": c_dirty},
                "codex": {"head": x_head, "msg": x_msg, "dirty": x_dirty},
                "both_ready_for_merge": both_ready,
            }
            STATUS_JSON.write_text(json.dumps(status, indent=2), encoding="utf-8")

        except Exception as e:
            log(f"Watchdog loop exception: {e}")

        time.sleep(3)


if __name__ == "__main__":
    main()

