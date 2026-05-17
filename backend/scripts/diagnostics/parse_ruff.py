import json

def parse_ruff():
    try:
        with open("ruff_report.json", "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            if not data:
                print("No ruff issues found.")
                return
            for item in data[:20]:
                print(f"{item['filename']}:{item['location']['row']}:{item['location']['column']} {item['message']}")
    except Exception as e:
        print("Error reading ruff report:", e)

parse_ruff()
