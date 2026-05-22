import matplotlib

matplotlib.use("Agg")  # Headless mode
import pandas as pd
import matplotlib.pyplot as plt
import os

# Absolute directory of this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "results"))
os.makedirs(RESULTS_DIR, exist_ok=True)


def generate_research_plots(csv_file=None):
    """
    Research Visualizer.
    Generates publication-quality 3-panel trajectory charts tracking:
    1. Core Affect & Relational Dynamics (Valence/Pleasure, Arousal, Dominance, Trust)
    2. Theory of Mind Alignment (Inferred Valence, Inferred Arousal)
    3. Endocrine & Hormonal Dynamics (Cortisol, Dopamine, Fatigue)
    """
    if csv_file is None:
        csv_file = os.path.join(RESULTS_DIR, "research_pad_trajectory.csv")
        if not os.path.exists(csv_file):
            csv_file = os.path.join(SCRIPT_DIR, "research_pad_trajectory.csv")

    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found. Run the collector first.")
        return

    print(f"📈 Generating plots from {csv_file}...")
    df = pd.read_csv(csv_file)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Normalize time for the X-axis (seconds from start)
    start_time = df["timestamp"].iloc[0]
    df["seconds"] = (df["timestamp"] - start_time).dt.total_seconds()

    # Premium style configuration
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = [
        "DejaVu Sans",
        "Arial",
        "Helvetica",
        "sans-serif",
    ]

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 14), sharex=True)
    fig.suptitle(
        "Cognitive Affective Trajectory Benchmarking\n(Tier-5 Sovereign Mesh & Theory of Mind)",
        fontsize=16,
        fontweight="bold",
        color="#2C3E50",
        y=0.96,
    )

    # 1. Panel 1: Core Affect & Relational Dynamics
    # Mapping 'pleasure' to mood/valence
    ax1.plot(
        df["seconds"],
        df["pleasure"],
        label="Pleasure/Valence (P)",
        color="#E05A47",
        linewidth=2.5,
    )
    ax1.plot(
        df["seconds"],
        df["arousal"],
        label="Arousal (Ar)",
        color="#F1C40F",
        linewidth=2.5,
    )
    ax1.plot(
        df["seconds"],
        df["dominance"],
        label="Dominance (D)",
        color="#3498DB",
        linewidth=2.5,
    )
    ax1.plot(
        df["seconds"],
        df["trust"],
        label="Trust (T)",
        color="#9B59B6",
        linewidth=2.0,
        linestyle="--",
    )

    ax1.set_title(
        "Core Affect (PAD) & Relational Dynamics",
        fontsize=12,
        fontweight="semibold",
        color="#34495E",
    )
    ax1.set_ylabel("State Space [-1.0, 1.0]", fontsize=10)
    ax1.set_ylim(-1.1, 1.1)
    ax1.grid(True, which="both", linestyle=":", alpha=0.6, color="#BDC3C7")
    ax1.legend(
        loc="upper right",
        frameon=True,
        facecolor="#F8F9F9",
        edgecolor="#BDC3C7",
        fontsize=9,
    )

    # 2. Panel 2: Theory of Mind (ToM) Alignment
    # Inferred Valence and Arousal are mapped against pleasure/arousal to show alignment
    ax2.plot(
        df["seconds"],
        df["pleasure"],
        label="Actual Valence (P)",
        color="#E05A47",
        linewidth=1.5,
        alpha=0.5,
    )
    ax2.plot(
        df["seconds"],
        df["arousal"],
        label="Actual Arousal (Ar)",
        color="#F1C40F",
        linewidth=1.5,
        alpha=0.5,
    )
    ax2.plot(
        df["seconds"],
        df["inferred_valence"],
        label="ToM Inferred Valence",
        color="#1ABC9C",
        linewidth=2.5,
    )
    ax2.plot(
        df["seconds"],
        df["inferred_arousal"],
        label="ToM Inferred Arousal",
        color="#E67E22",
        linewidth=2.5,
    )

    ax2.set_title(
        "Theory of Mind (ToM) User Alignment Tracking",
        fontsize=12,
        fontweight="semibold",
        color="#34495E",
    )
    ax2.set_ylabel("State Space [-1.0, 1.0]", fontsize=10)
    ax2.set_ylim(-1.1, 1.1)
    ax2.grid(True, which="both", linestyle=":", alpha=0.6, color="#BDC3C7")
    ax2.legend(
        loc="upper right",
        frameon=True,
        facecolor="#F8F9F9",
        edgecolor="#BDC3C7",
        fontsize=9,
    )

    # 3. Panel 3: Endocrine & Hormonal Dynamics
    ax3.plot(
        df["seconds"],
        df["cortisol"],
        label="Cortisol (Stress)",
        color="#E74C3C",
        linewidth=2.5,
    )
    ax3.plot(
        df["seconds"],
        df["dopamine"],
        label="Dopamine (Reward)",
        color="#2ECC71",
        linewidth=2.5,
    )
    ax3.plot(
        df["seconds"],
        df["fatigue"],
        label="Fatigue (Metabolic)",
        color="#7F8C8D",
        linewidth=2.0,
        linestyle="-.",
    )

    ax3.set_title(
        "Endocrine Hormonal & Metabolic Dynamics",
        fontsize=12,
        fontweight="semibold",
        color="#34495E",
    )
    ax3.set_xlabel(
        "Time (elapsed seconds)", fontsize=11, fontweight="semibold", color="#2C3E50"
    )
    ax3.set_ylabel("Concentration [0.0, 1.0]", fontsize=10)
    ax3.set_ylim(-0.05, 1.05)
    ax3.grid(True, which="both", linestyle=":", alpha=0.6, color="#BDC3C7")
    ax3.legend(
        loc="upper right",
        frameon=True,
        facecolor="#F8F9F9",
        edgecolor="#BDC3C7",
        fontsize=9,
    )

    # Spacing and layout
    plt.tight_layout(rect=[0, 0.02, 1, 0.95])

    output_plot = os.path.join(RESULTS_DIR, "research_trajectory_plot.png")
    plt.savefig(output_plot, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"✅ Plot saved to {output_plot}")


if __name__ == "__main__":
    generate_research_plots()
