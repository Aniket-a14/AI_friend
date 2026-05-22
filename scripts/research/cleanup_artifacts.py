import os
import shutil

# Dynamic resolution of local scripts/results and research directories
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "results"))

# Create directory dynamically if not exists
os.makedirs(RESULTS_DIR, exist_ok=True)

# Patterns/Names of benchmark artifacts to delete
BENCHMARK_FILES_TO_REMOVE = [
    # JSON results
    "benchmark_results.json",
    "cognitive_metrics_results.json",
    "extended_benchmarks.json",
    "human_realism_results.json",
    "raw_research_data.json",
    
    # Images/Plots
    "hard_benchmark_progression.png",
    "cognitive_confusion_matrix.png",
    "cognitive_rag_recall.png",
    "cognitive_tom_errors.png",
    "extended_benchmarks_comparisons.png",
    "extended_benchmarks_radar.png",
    "human_realism_comparisons.png",
    "human_realism_physiological.png",
    "research_trajectory_plot.png",
    "affective_trajectory_sample.png",
    
    # Audit Reports and temporary documents
    "benchmark_fidelity_audit.md",
    "benchmark_fidelity_audit.md.metadata.json",
    "walkthrough.md",
    "walkthrough.md.metadata.json",
    "CVS-3.0_Mind_Benchmarking_Report.pdf",
]

def clean_directory(directory_path, label):
    print(f"\n🧹 Cleaning {label}: {directory_path}")
    if not os.path.exists(directory_path):
        print(f"⚠️ Directory does not exist: {directory_path}")
        return

    deleted_count = 0
    # Walk directory and delete matching files
    for root, dirs, files in os.walk(directory_path):
        # Do not descend into .agents or .system_generated to protect system stability
        if ".agents" in root or ".system_generated" in root:
            continue
            
        for file in files:
            # Match files in the predefined list or matching resolved file backups
            should_delete = False
            if file in BENCHMARK_FILES_TO_REMOVE:
                should_delete = True
            elif file.startswith("walkthrough.md.resolved") or file.startswith("benchmark_fidelity_audit.md.resolved"):
                should_delete = True
            elif file.startswith("task.md.resolved"):
                # Clean up task.md resolved backups as well to keep workspace pristine
                should_delete = True
            
            if should_delete:
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    print(f"  🗑️ Deleted: {os.path.relpath(file_path, directory_path)}")
                    deleted_count += 1
                except Exception as e:
                    print(f"  ⚠️ Error deleting {file}: {e}")
                    
    print(f"✅ Cleaned {deleted_count} files from {label}.")

if __name__ == "__main__":
    print("✨ --- Starting Benchmark Artifacts Cleanup ---")
    
    # 1. Clean workspace results folder (scripts/results)
    clean_directory(RESULTS_DIR, "Workspace Results Directory")
    
    # 2. Clean workspace research folder (scripts/research) to remove any leftover artifacts
    clean_directory(SCRIPT_DIR, "Workspace Research Directory")
    
    print("\n✨ --- Benchmark Artifacts Cleanup Complete ---\n")

