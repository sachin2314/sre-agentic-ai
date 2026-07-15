import os

LOGS_DIR = os.path.join(os.path.dirname(__file__),"..","logs")

LOG_FILES = [
    "app.log",
    "nginx_access.log",
    "nginx_error.log",
    "database.log",
    "kubernetes_events.log"
]

def load_log_file(filename):
    full_path = os.path.join(LOGS_DIR, filename)

    if not os.path.exists(full_path):
        print(f" [WARNING] File not found: {full_path}")
        return[]
    with open(full_path, "r") as f:
        lines = f.readlines()
    lines = [line.strip() for line in lines if line.strip()]
    return lines

def load_all_logs():
    all_logs = {}

    for filename in LOG_FILES:
        print(f"Loading {filename}...")
        lines = load_log_file(filename)
        all_logs[filename] = lines
        print(f" -> {len(lines)} lines loaded")

    return all_logs


if __name__ == "__main__":
    print("=" *50)
    print("STEP 1 - Loading Log Files")
    print("=" * 50)

    logs = load_all_logs()

    print("\n -- Summary --")
    for filename, lines in logs.items():
        print(f" {filename:30s}  {len(lines):4d} lines")

    print("\n --- First line of app.log")
    if logs.get("app.log"):
        print(logs["app.log"][0])





