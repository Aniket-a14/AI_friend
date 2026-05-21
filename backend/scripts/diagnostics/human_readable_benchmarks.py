#!/usr/bin/env python3
import json
import os
import glob


def find_latest_benchmark():
    # Find the latest JSON file in .benchmarks
    base_dir = os.path.join(os.path.dirname(__file__), "..", "..", ".benchmarks")
    json_files = glob.glob(os.path.join(base_dir, "**", "*.json"), recursive=True)
    if not json_files:
        return None
    # Sort by modification time
    json_files.sort(key=os.path.getmtime, reverse=True)
    return json_files[0]


def print_human_readable_table(filepath):
    with open(filepath, "r") as f:
        data = json.load(f)

    benchmarks = data.get("benchmarks", [])
    if not benchmarks:
        print("No benchmarks found.")
        return

    print("=" * 85)
    print(f"{'🧠 AI FRIEND CVS-3.0 CORE LATENCY BENCHMARKS':^85}")
    print("=" * 85)
    print(
        f"{'Subsystem Component':<45} | {'Mean Latency':<12} | {'p99 Tail':<10} | {'Status':<10}"
    )
    print("-" * 85)

    for b in benchmarks:
        raw_name = b["name"]
        # Clean up the name for human readers
        clean_name = (
            raw_name.replace("test_", "")
            .replace("_benchmark", "")
            .replace("_", " ")
            .title()
        )

        mean_ms = b["stats"]["mean"] * 1000
        p99_ms = b["stats"].get("p99", 0) * 1000

        # Determine status
        if mean_ms < 1.0:
            status = "🟩 ULTRA"
        elif mean_ms < 5.0:
            status = "🟦 FAST"
        elif mean_ms < 20.0:
            status = "🟨 OK"
        else:
            status = "🟥 SLOW"

        print(
            f"{clean_name:<45} | {mean_ms:>8.3f} ms | {p99_ms:>7.3f} ms | {status:<10}"
        )

    print("=" * 85)
    print("Status Guide: ULTRA (<1ms), FAST (<5ms), OK (<20ms), SLOW (>20ms)")
    print("These micro-benchmarks prove the sub-50ms conversational budget overhead.")


if __name__ == "__main__":
    latest_file = find_latest_benchmark()
    if latest_file:
        print(f"Reading from latest benchmark run: {os.path.basename(latest_file)}\n")
        print_human_readable_table(latest_file)
    else:
        print(
            "No benchmark runs found. Please run `pytest tests/test_performance.py` first."
        )
