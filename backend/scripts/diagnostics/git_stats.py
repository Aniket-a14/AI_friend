import subprocess


def get_git_stats():
    try:
        output = subprocess.check_output(
            ["git", "log", "--since=6 months ago", "--name-only", "--format="],
            text=True,
        )
        counts = {}
        for line in output.split("\n"):
            line = line.strip()
            if line:
                counts[line] = counts.get(line, 0) + 1
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        print("Top Modified Files:")
        for file, count in sorted_counts[:20]:
            print(f"{count}: {file}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    get_git_stats()
