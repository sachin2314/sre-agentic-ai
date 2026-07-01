def observe(tool_name, tool_output):
    """
    Process the output from a tool and extract key findings.
    tool_name = which tool produced this output, e.g. "read_app_logs"
    tool_output = what the tool returned (a list of lines, or a dict)
    Returns a list of human-readable finding strings.
    """

    findings = []

    if isinstance(tool_output, dict):
        count_502 = tool_output.get("count_502", 0)
        count_200 = tool_output.get("count_200", 0)

        if count_502 > 0:
            findings.append(f"IMPACT: {count_502} requests returned 502 Bad Gateway errors.")
        if count_200 > 0:
            findings.append(f"Normal: {count_200} requests returned 200 OK before the incident.")
        return findings
    
    for line in tool_output:
        line = line.strip()
        if not line:
            continue
        line_lower = line.lower()

        #OOM Killed
        if "oom" in line_lower or "outofmemory" in line_lower or "137" in line_lower:
            findings.append(f"OOM KILL DETECTED: {line}")

        #Fatal Error
        elif "fatal" in line_lower:
            findings.append(f"FATAL ERROR: {line}")

        #Database connection problems
        elif "connection" in line_lower and ("refused" in line_lower or "timeout" in line_lower):
            findings.append(f"DB Connection failure: {line}")

        #Slow database queries
        elif "slow query" in line_lower:
            findings.append(f"SLOW QUERY: {line}")

        #Max connections hit
        elif "max connections" in line_lower or "connection slots" in line_lower:
            findings.append(f"DB EXHAUSTION: {line}")

        #Pod restart problems
        elif "quota" in line_lower or "forbidden" in line_lower:
            findings.append(f"K8S quota exceeded: {line}")

        elif "no live upstreams" in line_lower:
            findings.append(f"NO backends available: {line}")

    return findings


if __name__ == "__main__":
    print("STEP 5: The Observe Step")
    print()

    fake_app_log_output =  [
        "2026-06-26T08:00:00Z INFO  App started OK - memory: 200MB / 512MB",
        "2026-06-26T08:01:00Z INFO  Memory growing - memory: 380MB / 512MB",
        "2026-06-26T08:01:50Z ERROR OutOfMemoryError: failed to allocate memory",
        "2026-06-26T08:01:55Z FATAL Process killed by OOM killer (exit code 137)",
        "2026-06-26T08:02:01Z ERROR Cannot connect to database: connection timeout",
        "2026-06-26T08:02:07Z FATAL Max restart attempts reached. Giving up.",  
    ]

    print("RAW app log lines (6 lines):")
    for line in fake_app_log_output:
        print(f" {line}")
    print()

    findings = observe("read_app_logs", fake_app_log_output)

    print(f" Key findings extracted ({len(findings)} findings):")
    for finding in findings:
        print(f" >> {finding}")
    print()

    fake_502_result = {"count_502": 5, "count_200": 2, "total": 7}
    print("502 counter output")
    print(f" {fake_502_result}")
    print()

    findings_502 = observe("count_502_errors", fake_502_result)
    print("Findings from 502 counter:")
    for finding in findings_502:
        print(f" >> {finding}")

