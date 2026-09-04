"""Local Phase 01 micro-benchmarks (BM-LOC-01, BM-LOC-02, BM-LOC-03)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
from dataclasses import asdict
from typing import Any

# Ensure backend root is on sys.path
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.cognitive import percept
from app.state.workspace import WorkspaceCommand
from app.state.workspace_store import SQLiteWorkspaceStore


async def run_bm_loc_01() -> dict[str, Any]:
    """BM-LOC-01: Workspace CAS Commit Overhead.
    
    5 iterations of 1,000 sequential commits on SQLite (WAL mode, temp disk).
    """
    print("\n--- Running BM-LOC-01: Workspace CAS Commit Overhead ---")
    latencies_ns: list[int] = []
    num_iterations = 5
    commits_per_iter = 1000

    for iteration in range(num_iterations):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name
        
        store = SQLiteWorkspaceStore(db_path)
        try:
            session_id = f"bench-session-{iteration}"
            snap = await store.get_snapshot(session_id)
            epoch = snap.epoch
            rev = snap.revision

            for i in range(commits_per_iter):
                cmd = WorkspaceCommand(
                    session_id=session_id,
                    expected_epoch=epoch,
                    expected_revision=rev,
                    focus_update=f"focus-topic-{i}",
                    add_goals=[f"goal-{i % 5}"],
                    affect_update={"pleasure": 0.1, "arousal": 0.05, "dominance": 0.0},
                    pending_action={"act": "SPEAK", "target": f"user-{i}"},
                )
                t0 = time.perf_counter_ns()
                snap = await store.commit_transition(cmd)
                t1 = time.perf_counter_ns()
                latencies_ns.append(t1 - t0)
                rev = snap.revision
                epoch = snap.epoch
        finally:
            await store.close()
            if os.path.exists(db_path):
                os.unlink(db_path)
            wal_file = f"{db_path}-wal"
            if os.path.exists(wal_file):
                os.unlink(wal_file)
            shm_file = f"{db_path}-shm"
            if os.path.exists(shm_file):
                os.unlink(shm_file)

    latencies_ms = [ns / 1_000_000.0 for ns in latencies_ns]
    latencies_ms.sort()
    n = len(latencies_ms)
    p50 = latencies_ms[int(n * 0.50)]
    p95 = latencies_ms[int(n * 0.95)]
    p99 = latencies_ms[int(n * 0.99)]
    mean = sum(latencies_ms) / n

    result = {
        "benchmark_id": "BM-LOC-01",
        "total_commits": n,
        "iterations": num_iterations,
        "commits_per_iteration": commits_per_iter,
        "mean_ms": round(mean, 4),
        "p50_ms": round(p50, 4),
        "p95_ms": round(p95, 4),
        "p99_ms": round(p99, 4),
        "min_ms": round(latencies_ms[0], 4),
        "max_ms": round(latencies_ms[-1], 4),
        "target_p50_ms": "<= 3.0",
        "target_p95_ms": "<= 5.0",
        "verdict": "PASS" if p50 <= 3.0 and p95 <= 5.0 else "FAIL",
    }
    print(json.dumps(result, indent=2))
    return result


async def run_bm_loc_02() -> dict[str, Any]:
    """BM-LOC-02: Snapshot Serialization & Memory Budget.
    
    100 sessions loaded with 10 active goals, full PAD affect, and pending actions.
    """
    print("\n--- Running BM-LOC-02: Snapshot Serialization & Memory Budget ---")
    store = SQLiteWorkspaceStore(":memory:")
    serialized_sizes: list[int] = []
    num_sessions = 100

    try:
        for i in range(num_sessions):
            session_id = f"session-mem-{i}"
            snap = await store.get_snapshot(session_id)
            cmd = WorkspaceCommand(
                session_id=session_id,
                expected_epoch=snap.epoch,
                expected_revision=snap.revision,
                focus_update="conversational turn about cognitive architecture and memory retrieval",
                add_goals=[f"active_goal_{g}_verify_subconscious_continuity" for g in range(10)],
                affect_update={"pleasure": 0.42, "arousal": -0.15, "dominance": 0.33},
                pending_action={
                    "act": "SPEAK",
                    "intent": "CLARIFY",
                    "goal": "ENGAGE",
                    "target_character_count": 140,
                    "model_options": {"temperature": 0.7, "top_p": 0.9},
                },
                percept_id=f"percept:text:chat-{i}",
            )
            updated_snap = await store.commit_transition(cmd)
            
            # Serialize snapshot to JSON
            raw_dict = asdict(updated_snap)
            encoded = json.dumps(raw_dict).encode("utf-8")
            serialized_sizes.append(len(encoded))
    finally:
        await store.close()

    mean_bytes = sum(serialized_sizes) / len(serialized_sizes)
    max_bytes = max(serialized_sizes)
    min_bytes = min(serialized_sizes)

    result = {
        "benchmark_id": "BM-LOC-02",
        "sessions_measured": num_sessions,
        "mean_bytes": round(mean_bytes, 2),
        "min_bytes": min_bytes,
        "max_bytes": max_bytes,
        "target_mean_bytes": "<= 2048",
        "verdict": "PASS" if mean_bytes <= 2048 else "FAIL",
    }
    print(json.dumps(result, indent=2))
    return result


def run_bm_loc_03() -> dict[str, Any]:
    """BM-LOC-03: Percept Normalization Micro-benchmark.
    
    10,000 synthetic events across all 6 modalities.
    """
    print("\n--- Running BM-LOC-03: Percept Normalization Micro-benchmark ---")
    num_events = 10000
    latencies_us: list[float] = []

    # Pre-build synthetic payloads
    chat_payload = {"text": "Hello, how are you feeling today?", "metadata": {"source": "user", "channel": "voice", "confidence": 0.95}}
    vision_payload = {"description": "User is sitting at a wooden desk with a coffee mug.", "source": "camera", "user_distance": 1.2, "is_novel": True}
    reflex_payload = {"name": "startle", "arousal_delta": 0.08, "timestamp": time.time(), "evidence": "blink"}
    audio_stop_payload = {"interrupt": True, "reason": "user_speech_detected", "intent_type": "VOICE_INTERRUPTION"}
    system_tick_payload = {"timestamp": time.time(), "source": "system_agent"}
    progress_payload = {"utterance_id": "turn-42", "character_offset": 84, "completed": False}

    modalities = [
        ("chat", chat_payload, percept.from_chat_input),
        ("vision", vision_payload, percept.from_vision_description),
        ("reflex", reflex_payload, percept.from_facial_reflex),
        ("stop", audio_stop_payload, percept.from_audio_stop),
        ("tick", system_tick_payload, percept.from_system_tick),
        ("progress", progress_payload, percept.from_playback_progress),
    ]

    for i in range(num_events):
        mod_name, payload, fn = modalities[i % len(modalities)]
        t0 = time.perf_counter_ns()
        env = fn(payload)
        t1 = time.perf_counter_ns()
        latencies_us.append((t1 - t0) / 1_000.0)

    latencies_us.sort()
    n = len(latencies_us)
    p50 = latencies_us[int(n * 0.50)]
    p95 = latencies_us[int(n * 0.95)]
    p99 = latencies_us[int(n * 0.99)]
    mean = sum(latencies_us) / n

    result = {
        "benchmark_id": "BM-LOC-03",
        "total_events": num_events,
        "mean_us": round(mean, 2),
        "p50_us": round(p50, 2),
        "p95_us": round(p95, 2),
        "p99_us": round(p99, 2),
        "min_us": round(latencies_us[0], 2),
        "max_us": round(latencies_us[-1], 2),
        "target_p95_us": "<= 100.0",
        "verdict": "PASS" if p95 <= 100.0 else "FAIL",
    }
    print(json.dumps(result, indent=2))
    return result


async def main():
    results = {}
    results["BM-LOC-01"] = await run_bm_loc_01()
    results["BM-LOC-02"] = await run_bm_loc_02()
    results["BM-LOC-03"] = run_bm_loc_03()
    
    out_path = os.path.join(BACKEND_ROOT, "..", "orchestration", "PHASE_01", "local_benchmark_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote local benchmark results to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
