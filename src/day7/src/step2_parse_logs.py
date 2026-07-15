import re
import os
from collections import Counter
from step1_load_logs import load_all_logs

APP_PATTERN = re.compile(
    r"(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
    r"\s+(?P<level>\w+)"
    r"\s+\[(?P<source>\w+)\]"
    r"\s+(?P<message>.+)"
)

NGINX_ACCESS_PATTERN = re.compile(
    r"(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
    r"\s+(?P<ip>\S+)"          # IP address
    r"\s+(?P<method>\S+)"      # GET / POST / etc.
    r"\s+(?P<path>\S+)"        # /api/orders
    r"\s+\S+"                  # HTTP/1.1  — we skip this, no group needed
    r"\s+(?P<status>\d+)"      # 500
    r"\s+(?P<bytes>\d+)"       # 89
    r"\s+(?P<response_time>\S+)"  # 5.001
)

DB_PATTERN = re.compile(
    r"(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
    r"\s+\[(?P<level>\w+)\]"   # [ERROR]  → level=ERROR
    r"\s+(?P<message>.+)"
)

NGINX_ERROR_PATTERN = re.compile(
    r"(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
    r"\s+\[(?P<level>\w+)\]"
    r"\s+(?P<message>.+)"
)

K8S_PATTERN = re.compile(
    r"(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
    r"\s+(?P<level>\w+)"         # Warning / Normal
    r"\s+(?P<event_type>\w+)"    # Unhealthy / Scheduled / Killing / etc.
    r"\s+(?P<object>\S+)"        # Pod/api-server-... or Deployment/...
    r"\s+(?P<message>.+)"        # everything after the object
)

def extract_key_value_fields(message):
    pattern = re.compile(r"(\w+)=([^\s]+)")
    matches = pattern.findall(message)
    return dict(matches)

def parse_app_log(lines):
    parsed = []

    for line in lines:
        match = APP_PATTERN.match(line)
        if not match:
            continue

        entry = {
            "timestamp": match.group("timestamp"),
            "level": match.group("level"),
            "source": "app",
            "message": match.group("message"),
            "fields": extract_key_value_fields(match.group("message"))
        }

        parsed.append(entry)
    return parsed


def parse_nginx_access_log(lines):

    parsed =[]

    for line in lines:
        match = NGINX_ACCESS_PATTERN.match(line)

        if not match:
            continue

        message = f"{match.group('method')}  {match.group('path')} {match.group('status')}"

        entry = {
            "timestamp": match.group("timestamp"),
            "level": "INFO",
            "source": "nginx_access",
            "message": message,
            "fields": {
                "ip": match.group("ip"), 
                "method": match.group("method"),
                "path": match.group("path"),
                "status": match.group("status"),
                "bytes": match.group("bytes"),
                "response_time": match.group("response_time")
            }
        }

        parsed.append(entry)

    return parsed

def parse_nginx_error_log(lines):
    parsed= []

    for line in lines:
        match = NGINX_ERROR_PATTERN.match(line)

        if not match:
            continue

        entry = {
            "timestamp": match.group("timestamp"),
            "level": match.group("level").upper(),
            "source": "nginx_error",
            "message": match.group("message"),
            "fields": {}
        }

        parsed.append(entry)

    return parsed

def parse_database_log(lines):
    parsed= []

    for line in lines:
        match = DB_PATTERN.match(line)

        if not match:
            continue
        
        entry = {
            "timestamp": match.group("timestamp"),
            "level": match.group("level"),
            "source": "database",
            "message": match.group("message"),
            "fields": extract_key_value_fields(match.group("message"))
        }

        parsed.append(entry)

    return parsed



def parse_k8s_log(lines):
    parsed = []

    for line in lines:
        match = K8S_PATTERN.match(line)

        if not match:
            continue

        raw_level = match.group("level")
        if raw_level == "Warning":
            level = "WARN"
        else:
            level = "INFO"

        entry = {
            "timestamp": match.group("timestamp"),
            "level": level,
            "source": "kubernetes",
            "message": match.group("message"),
            "fields": {
                "event_type": match.group("event_type"),
                "object": match.group("object")
            }
        }
        parsed.append(entry)

    return parsed

def parse_all_logs(raw_logs):

    all_entries = []
    
    all_entries.extend(parse_app_log(raw_logs.get("app.log", [])))
    all_entries.extend(parse_nginx_access_log(raw_logs.get("nginx_access.log", [])))
    all_entries.extend(parse_nginx_error_log(raw_logs.get("nginx_error.log", [])))
    all_entries.extend(parse_database_log(raw_logs.get("database.log", [])))
    all_entries.extend(parse_k8s_log(raw_logs.get("kubernetes_events.log", [])))

    all_entries.sort(key=lambda e: e["timestamp"])
    return all_entries

if __name__ == "__main__":
    print("=" * 50)
    print("Step 2 - Parsing Log Files")
    print("=" * 50)

    raw_logs = load_all_logs()
    entries = parse_all_logs(raw_logs)

    level_counts = Counter(e["level"] for e in entries)

    print("\n Entries by log level: ")

    for level, count in sorted(level_counts.items()):
        print(f" {level:10s}: {count}")

    print("\n -- Sample Error / FATAL entries ---")
    errors = [e for e in entries if e["level"] in ("ERROR", "FATAL")]
    for e in errors[:5]:
        print(f"  [{e['timestamp']}] [{e['source']:12s}]  {e['message'][:70]}")










