import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.day6.src.step1_read_logs import read_log_file
from src.day6.src.step2_search_logs import find_errors_in_log

def tool_read_app_logs():
    """ Tool 1: Read the application log file"""
    lines = read_log_file("src/day6/logs/app/app.log")
    return lines

def tool_read_nginx_logs():
    """ Tool 2: Read the Nginx error log file"""
    lines = read_log_file("src/day6/logs/nginx/error.log")
    return lines

def tool_read_db_logs():
    """ Tool 3: Read the database log file"""
    lines = read_log_file("src/day6/logs/database/postgres.log")
    return lines

def tool_read_k8s_logs():
    """ Tool 4: Find errors in Kubernetes events log"""
    errors = find_errors_in_log("src/day6/logs/kubernetes/events.log")
    return errors

def tool_find_oom_events():
    """ Tool 5: Search All logs for OOM events"""
    all_oom_lines = []
    log_files = [
        "src/day6/logs/app/app.log",
        "src/day6/logs/nginx/error.log",
        "src/day6/logs/database/postgres.log",
        "src/day6/logs/kubernetes/events.log"
    ]

    for filepath in log_files:
        lines = read_log_file(filepath)
        for line in lines:
            if "OOM" in line.lower() or "OutOfMemory" in line.lower() or "137" in line.lower():
                all_oom_lines.append(line.strip())
    return all_oom_lines

def tool_count_502_errors():
    """ Tool 6: Count how many 502 HTTP errors happened in nginx access logs"""
    lines = read_log_file("src/day6/logs/nginx/access.log")
    count_502 = 0 
    count_200 = 0 
    for line in lines:
        if "502" in line:
            count_502 += 1
        elif "200" in line:
            count_200 += 1

    result = {
        "502_errors": count_502,
        "200_success": count_200,
        "total": count_502 + count_200,
    }
    return result

TOOLS = {
    "read_app_logs": tool_read_app_logs,
    "read_nginx_error_logs": tool_read_nginx_logs,
    "read_db_logs": tool_read_db_logs,
    "read_k8s_logs": tool_read_k8s_logs,
    "find_oom_events": tool_find_oom_events,
    "count_502_errors": tool_count_502_errors
}

def run_tool(tool_name):
    """Run a tool by its name."""
    if tool_name not in TOOLS:
        return f"ERROR: Non tool called '{tool_name}'"
    tool_function = TOOLS[tool_name]
    result = tool_function()
    return result


if __name__ == "__main__":
    print("========= STEP 3: Tools =========")
    print()

    print("Available tools:")

    for name in TOOLS:
        print(f" - {name}")
    print()

    print("Running tool: count_502_errors")
    result = run_tool("count_502_errors")
    print(f"Result: {result}")
    print()

    print("Running tool: find_oom_events")
    oom_lines = run_tool("find_oom_events")
    print(f"Found {len(oom_lines)} OOM events across all logs.")

    for line in oom_lines:
        print(f" {line}")
