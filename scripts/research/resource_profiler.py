import subprocess
import time
import json
import os
from datetime import datetime

# Resource Consumption Profiler
# Measures CPU and Memory footprint of the agentic mesh during active inference.


def get_docker_stats():
    """Capture a snapshot of docker container stats."""
    try:
        # Get stats for all project containers
        cmd = ["docker", "stats", "--no-stream", "--format", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        stats = []
        for line in result.stdout.splitlines():
            if line.strip():
                stats.append(json.loads(line))
        return stats
    except Exception as e:
        print(f"Error capturing docker stats: {e}")
        return []


def run_profiler(duration_sec=60):
    print("\n🔋 --- Resource Profiler ---")
    print(f"Sampling interval: 5s | Duration: {duration_sec}s")

    all_snapshots = []
    start_time = time.time()

    # Dynamic resolution of local scripts/results folder
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    RESULTS_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "results"))
    os.makedirs(RESULTS_DIR, exist_ok=True)

    output_file = os.path.join(
        RESULTS_DIR, f"resource_profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    try:
        while time.time() - start_time < duration_sec:
            print(
                f"📸 Capturing resource snapshot... ({(time.time() - start_time):.0f}s elapsed)",
                end="\r",
            )
            snapshot = {
                "timestamp": datetime.now().isoformat(),
                "elapsed": time.time() - start_time,
                "stats": get_docker_stats(),
            }
            all_snapshots.append(snapshot)
            time.sleep(5)

    except KeyboardInterrupt:
        pass

    print(f"\n✅ Profiling complete. Saving to {output_file}")

    # Calculate Averages for the paper
    print("\n📊 --- RESOURCE USAGE SUMMARY (AVERAGES) ---")
    print(f"{'Container':<25} | {'CPU %':<10} | {'MEM USAGE':<10}")
    print("-" * 50)

    # Simple aggregation (for quick feedback)
    aggregates = {}
    for snap in all_snapshots:
        for s in snap["stats"]:
            name = s["Name"]
            if name not in aggregates:
                aggregates[name] = {"cpu": [], "mem": []}
            # Clean up percentage strings
            cpu_val = float(s["CPUPerc"].replace("%", ""))
            aggregates[name]["cpu"].append(cpu_val)
            aggregates[name]["mem"].append(s["MemUsage"])

    for name, data in aggregates.items():
        avg_cpu = sum(data["cpu"]) / len(data["cpu"])
        last_mem = data["mem"][-1]  # Show peak/last memory
        print(f"{name:<25} | {avg_cpu:>9.2f}% | {last_mem:>10}")

    with open(output_file, "w") as f:
        json.dump(all_snapshots, f, indent=2)


if __name__ == "__main__":
    run_profiler()
