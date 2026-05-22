import os
import matplotlib.pyplot as plt
import numpy as np


def plot_sample_pad_trajectory():
    """
    Generates a sample Pleasure-Arousal-Dominance (PAD) trajectory chart
    for research paper visualization.
    """
    # Sample data: 60 minutes of conversation
    time_points = np.linspace(0, 60, 100)

    # Pleasure: Starts high, dips during a 'disagreement', then recovers
    pleasure = (
        0.5
        + 0.3 * np.sin(time_points / 10)
        - 0.4 * np.exp(-((time_points - 30) ** 2) / 20)
    )

    # Arousal: Spikes during the 'disagreement'
    arousal = (
        0.2
        + 0.6 * np.exp(-((time_points - 30) ** 2) / 30)
        + 0.1 * np.random.normal(0, 0.1, 100)
    )

    # Dominance: Generally stable but slightly lower during stress
    dominance = 0.6 - 0.2 * np.exp(-((time_points - 30) ** 2) / 50)

    plt.figure(figsize=(12, 6))
    plt.plot(
        time_points, pleasure, label="Pleasure (Valence)", color="#10B981", linewidth=2
    )
    plt.plot(
        time_points, arousal, label="Arousal (Intensity)", color="orange", linewidth=2
    )
    plt.plot(
        time_points,
        dominance,
        label="Dominance (Control)",
        color="royalblue",
        linewidth=2,
    )

    plt.title(
        "Affective Trajectory: Tier-5 Sovereign Mesh", fontsize=14, fontweight="bold"
    )
    plt.xlabel("Time (Minutes)", fontsize=12)
    plt.ylabel("Coordinate Value (-1.0 to 1.0)", fontsize=12)
    plt.axhline(0, color="black", linestyle="--", alpha=0.3)
    plt.grid(True, which="both", linestyle="--", alpha=0.5)
    plt.legend(loc="upper right")
    plt.ylim(-1.1, 1.1)

    # Add annotations for paper clarity
    plt.annotate(
        "User Disagreement",
        xy=(30, 0.5),
        xytext=(35, 0.8),
        arrowprops=dict(facecolor="black", shrink=0.05),
    )

    plt.tight_layout()

    # Dynamic resolution of local scripts/results folder
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    RESULTS_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "results"))
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # Save the visualization
    output_path = os.path.join(RESULTS_DIR, "affective_trajectory_sample.png")
    plt.savefig(output_path, dpi=300)
    print(f"Visualization saved to: {output_path}")


if __name__ == "__main__":
    try:
        plot_sample_pad_trajectory()
    except ImportError:
        print("Error: matplotlib and numpy are required for visualization.")
        print("Run: pip install matplotlib numpy")
