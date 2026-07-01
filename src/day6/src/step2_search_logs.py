import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.day6.src.step1_read_logs import read_log_file

def find_errors_in_log(filepath: str) -> list[str]:
    """
    Read a log file and find lines that contain error keywords.
    Returns a list of only the bad lines.
    """
    
    error_keywords = ["ERROR", "FATAL", "WARN","OOM", "failed", "timeout", "refused",]

    found_lines = []
    all_lines = read_log_file(filepath)

    for line in all_lines:
        for keyword in error_keywords:
            if keyword.lower() in line.lower():
                found_lines.append(line.strip())
                break  # Stop checking other keywords if one is found
    return found_lines

def summarise_log(filepath, log_name):
    """
    Print a simple summary of errors found in a log file.
    """
    print(f"---checking: {log_name} ---")
    errors = find_errors_in_log(filepath)
    print(f"Total error/warning lines found: {len(errors)}")

    for error_line in errors:
        print(f" >> {error_line}")
    print()
    return errors


if __name__ == "__main__":
    print("========= STEP 2: Searching for Errors in Log Files =========")
    print()




    log_files = {
        "app.log": "src/day6/logs/app/app.log",
        "access.log": "src/day6/logs/nginx/access.log",
        "error.log": "src/day6/logs/nginx/error.log",
        "events.log": "src/day6/logs/kubernetes/events.log",
        "database.log": "src/day6/logs/database/postgres.log"
    }

    for log_name, log_path in log_files.items():
        summarise_log(log_path, log_name)