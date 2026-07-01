def read_log_file(filepath: str) -> list[str]:
    """Read a log file and return its lines, or a missing tag if not found."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.readlines()
    except FileNotFoundError:
        return [f"[MISSING] {filepath}"]

if __name__ == "__main__":
    print("========= STEP 1: Reading Log Files =========")
    print()
    lines = read_log_file("src/day6/logs/app/app.log")
    print(f"Found {len(lines)} lines in app.log")
    for line in lines:
        print(line.strip())
    
