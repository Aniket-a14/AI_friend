import os

def get_stats():
    file_stats = []
    for root, _, files in os.walk("app"):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        lines = len(f.readlines())
                        file_stats.append((lines, path))
                except Exception:
                    pass
    file_stats.sort(reverse=True)
    print("Top Largest Files:")
    for lines, path in file_stats[:20]:
        print(f"{lines}: {path}")

if __name__ == "__main__":
    get_stats()
