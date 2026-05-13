import pandas as pd
import matplotlib.pyplot as plt
import os

def generate_research_plots(csv_file="research_pad_trajectory.csv"):
    """
    Research Visualizer.
    Generates publication-quality PAD trajectory charts from collector logs.
    """
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found. Run the collector first.")
        return

    print(f"📈 Generating plots from {csv_file}...")
    df = pd.read_csv(csv_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Normalize time for the X-axis (seconds from start)
    start_time = df['timestamp'].iloc[0]
    df['seconds'] = (df['timestamp'] - start_time).dt.total_seconds()

    plt.figure(figsize=(12, 6))
    
    # Plot PAD Dimensions
    plt.plot(df['seconds'], df['valence'], label='Valence (V)', color='green', linewidth=2)
    plt.plot(df['seconds'], df['arousal'], label='Arousal (Ar)', color='orange', linewidth=2)
    plt.plot(df['seconds'], df['dominance'], label='Dominance (D)', color='blue', linewidth=2)
    
    # Plot Trust for reference
    plt.plot(df['seconds'], df['trust'], label='Trust (T)', color='purple', linestyle='--', alpha=0.7)

    plt.title('Affective Trajectory Benchmarking (Tier-5 Sovereign Mesh)', fontsize=14)
    plt.xlabel('Time (seconds)', fontsize=12)
    plt.ylabel('Coordinate Value [-1, 1]', fontsize=12)
    plt.ylim(-1.1, 1.1)
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.legend(loc='upper right')
    
    output_plot = "research_trajectory_plot.png"
    plt.savefig(output_plot, dpi=300)
    print(f"✅ Plot saved to {output_plot}")
    plt.show()

if __name__ == "__main__":
    generate_research_plots()
