"""
=============================================================================
FILE: src/tools/pod_log_reader.py
COURSE: AI Agentic SRE - Day 8: Deep Dive — Agent Architectures
TOPIC:  Tool 1 of 2 — Read EKS pod logs from local files
=============================================================================

PURPOSE:
  This is TOOL 1 used by the ReAct agent.
  Reads fake EKS pod log files from the logs/ directory and parses
  them into structured LogEntry objects.

  In a REAL production system this would call:
    boto3.client('logs').get_log_events(logGroupName=..., logStreamName=...)
  But for this course we read local .log files to skip AWS setup time.

HOW THIS FITS INTO THE REACT LOOP:
  Thought: "I need to read the pod logs for web-service-7d8b9c"
  Action:  read_pod_logs
  Action Input: {"pod_name": "web-service-7d8b9c", "namespace": "production"}
  Observation: [JSON list of LogEntry objects]
  → Agent now has raw log data to reason about

ALGORITHM TO IMPLEMENT:
  1. Accept pod_name and namespace as input
  2. Scan logs/ directory for files matching the pod name pattern
  3. Read the matching file line by line
  4. Skip comment lines (starting with #) and blank lines
  5. Parse each line with a regex to extract:
       - timestamp (ISO8601)
       - log level (INFO/WARNING/ERROR/FATAL)
       - service name and pod ID from [service/podid] bracket
       - message (everything after the bracket)
  6. Extract numeric fields from message if present:
       - memory_mi from "memory_used=XXXMi"
       - cpu_pct from "cpu=XX%"
       - latency_ms from "latency=XXXms"
       - exit_code from "exit_code=XXX"
  7. Build LogEntry Pydantic object for each valid line
  8. Return JSON-serialised list of LogEntry objects
  9. Also return a summary statistics dict (error_count, peak_memory etc.)

REGEX PATTERN FOR LOG LINE:
  ^(\S+)\s+(\w+)\s+\[([^/]+)/([^\]]+)\]\s+(.+)$
  Groups: (timestamp, level, service, pod_id, message)

REQUIREMENTS (pip install):
  pydantic>=2.0.0
  langchain-core>=0.2.0

=============================================================================
"""

import re
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from langchain_core.tools import tool

from src.models.schemas import LogEntry, LogLevel
from src.utils.app_logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------
LOGS_DIR = Path("logs")

# Regex to parse one log line
# Example line:
# 2024-01-15T09:15:01.234Z ERROR  [web-service/7d8b9c] DB pool EXHAUSTED ...
LOG_LINE_PATTERN = re.compile(
    r"^(\S+)"           # Group 1: timestamp  e.g. 2024-01-15T09:15:01.234Z
    r"\s+(\w+)"         # Group 2: level       e.g. ERROR
    r"\s+\[([^/]+)"     # Group 3: service     e.g. web-service
    r"/([^\]]+)\]"      # Group 4: pod_id      e.g. 7d8b9c
    r"\s+(.+)$"         # Group 5: message     (rest of line)
)

# Regex patterns to extract numeric values from message fields
MEMORY_PATTERN   = re.compile(r"memory[_\s]used[=:](\d+(?:\.\d+)?)Mi")
CPU_PATTERN      = re.compile(r"cpu[=:](\d+(?:\.\d+)?)%")
LATENCY_PATTERN  = re.compile(r"latency[=:](\d+(?:\.\d+)?)ms")
EXIT_CODE_PATTERN = re.compile(r"exit_code[=:](\d+)")


def _parse_timestamp(ts_str: str) -> Optional[datetime]:
    """
    Parse ISO8601 timestamp from log line.

    ALGORITHM:
      Try multiple timestamp formats because real logs are inconsistent.
      Return None if unparseable (we skip those lines).
    """
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",   # 2024-01-15T09:15:01.234Z
        "%Y-%m-%dT%H:%M:%SZ",       # 2024-01-15T09:15:01Z
        "%Y-%m-%d %H:%M:%S",        # 2024-01-15 09:15:01
    ]
    for fmt in formats:
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    return None


def _extract_numeric_fields(message: str) -> dict:
    """
    Extract numeric metrics embedded in log messages.

    ALGORITHM:
      Run each regex against the message string.
      If a match is found, convert to float and store.
      The agent uses these to identify memory trends and latency issues.

    Args:
        message: raw log message string

    Returns:
        dict with keys: memory_mi, cpu_pct, latency_ms, exit_code
    """
    fields: dict = {}

    match = MEMORY_PATTERN.search(message)
    if match:
        fields["memory_mi"] = float(match.group(1))

    match = CPU_PATTERN.search(message)
    if match:
        fields["cpu_pct"] = float(match.group(1))

    match = LATENCY_PATTERN.search(message)
    if match:
        fields["latency_ms"] = float(match.group(1))

    match = EXIT_CODE_PATTERN.search(message)
    if match:
        fields["exit_code"] = int(match.group(1))

    return fields


def _find_log_file(pod_name: str) -> Optional[Path]:
    """
    Find the log file for the given pod name in the logs/ directory.

    ALGORITHM:
      1. Strip namespace prefix if pod_name contains '/'
      2. Look for files containing the pod_name in their filename
      3. Prefer exact matches over partial matches
      4. Return None if no file found

    Args:
        pod_name: e.g. "web-service-7d8b9c" or "production/web-service-7d8b9c"

    Returns:
        Path to the log file or None
    """
    # Strip namespace if provided as "namespace/pod-name"
    if "/" in pod_name:
        pod_name = pod_name.split("/")[-1]

    if not LOGS_DIR.exists():
        logger.error("Logs directory not found: %s", LOGS_DIR.absolute())
        return None

    # Try exact match first
    for log_file in LOGS_DIR.glob("*.log"):
        if pod_name in log_file.name:
            logger.info("Found log file for pod %s: %s", pod_name, log_file.name)
            return log_file

    logger.warning("No log file found for pod: %s", pod_name)
    return None


# ---------------------------------------------------------------------------
# LANGCHAIN TOOL DEFINITION
# The @tool decorator registers this function as a LangChain tool.
# The docstring becomes the tool description the LLM sees when deciding
# which tool to call. Write it like an instruction manual for the LLM.
# ---------------------------------------------------------------------------

@tool
def read_pod_logs(pod_name: str, namespace: str = "production",
                  level_filter: str = "ALL") -> str:
    """
    Reads EKS pod logs from local log files and returns structured analysis.

    Use this tool FIRST when investigating any EKS pod issue.
    It parses the raw logs into structured data showing error counts,
    memory trends, and the timeline of events for the specified pod.

    Args:
        pod_name:     Name of the EKS pod to investigate.
                      Examples: "web-service-7d8b9c", "api-gateway-6f9a2b"
        namespace:    Kubernetes namespace. Default: "production"
        level_filter: Filter by log level. Options: ALL, ERROR, WARNING, ERROR_AND_WARNING
                      Default: ALL (returns everything for complete picture)

    Returns:
        JSON string containing:
        - entries:    List of parsed log entries (structured)
        - summary:    Statistics (error_count, peak_memory, etc.)
        - error_lines: Only ERROR/FATAL lines for quick review
    """
    logger.info("Tool read_pod_logs called — pod=%s namespace=%s filter=%s",
                pod_name, namespace, level_filter)

    # -----------------------------------------------------------------------
    # STEP 1: Find the log file
    # -----------------------------------------------------------------------
    log_file = _find_log_file(pod_name)
    if not log_file:
        return json.dumps({
            "error": f"No log file found for pod '{pod_name}' in namespace '{namespace}'",
            "available_pods": [f.stem for f in LOGS_DIR.glob("eks_pod_*.log")]
        })

    # -----------------------------------------------------------------------
    # STEP 2: Parse each log line
    # -----------------------------------------------------------------------
    entries: list[dict] = []
    parse_errors: int = 0
    peak_memory: float = 0.0
    memory_readings: list[float] = []

    with open(log_file, "r", encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            raw_line = raw_line.strip()

            # Skip comments and blank lines
            if not raw_line or raw_line.startswith("#"):
                continue

            match = LOG_LINE_PATTERN.match(raw_line)
            if not match:
                parse_errors += 1
                continue

            ts_str, level_str, service, pod_id, message = match.groups()

            # Parse timestamp
            ts = _parse_timestamp(ts_str)
            if ts is None:
                parse_errors += 1
                continue

            # Normalise log level — handle both "WARNING" and "WARN"
            level_str = level_str.upper()
            if level_str == "WARN":
                level_str = "WARNING"

            # Apply level filter
            if level_filter == "ERROR" and level_str not in ("ERROR", "FATAL"):
                continue
            if level_filter == "WARNING" and level_str not in ("WARNING",):
                continue
            if level_filter == "ERROR_AND_WARNING" and level_str not in ("ERROR", "FATAL", "WARNING"):
                continue

            # Extract numeric metrics from message
            numeric = _extract_numeric_fields(message)

            if numeric.get("memory_mi", 0) > peak_memory:
                peak_memory = numeric["memory_mi"]

            if "memory_mi" in numeric:
                memory_readings.append(numeric["memory_mi"])

            # Build entry dict (Pydantic model → dict for JSON serialisation)
            entry = {
                "timestamp": ts.isoformat(),
                "level":     level_str,
                "service":   service,
                "pod_id":    pod_id,
                "message":   message[:300],   # Truncate very long messages
                **numeric,
            }
            entries.append(entry)

    # -----------------------------------------------------------------------
    # STEP 3: Build summary statistics for the agent to reason about
    # -----------------------------------------------------------------------
    error_count   = sum(1 for e in entries if e["level"] in ("ERROR", "FATAL"))
    warning_count = sum(1 for e in entries if e["level"] == "WARNING")
    total_count   = len(entries)
    error_rate    = round((error_count / total_count * 100), 1) if total_count else 0

    # Detect memory trend: compare first third vs last third of readings
    memory_trend = "STABLE"
    if len(memory_readings) >= 6:
        first_avg  = sum(memory_readings[:len(memory_readings)//3]) / (len(memory_readings)//3)
        last_avg   = sum(memory_readings[-(len(memory_readings)//3):]) / (len(memory_readings)//3)
        growth_pct = ((last_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0
        if growth_pct > 20:
            memory_trend = "GROWING"
        elif growth_pct < -20:
            memory_trend = "SHRINKING"

    # Extract just the ERROR/FATAL lines for quick agent review
    error_lines = [
        f"{e['timestamp']} {e['level']} {e['message']}"
        for e in entries
        if e["level"] in ("ERROR", "FATAL")
    ]

    summary = {
        "pod_name":      pod_name,
        "namespace":     namespace,
        "log_file":      str(log_file),
        "total_entries": total_count,
        "error_count":   error_count,
        "warning_count": warning_count,
        "error_rate_pct": error_rate,
        "peak_memory_mi": peak_memory,
        "memory_trend":  memory_trend,
        "parse_errors":  parse_errors,
        "first_log_time": entries[0]["timestamp"] if entries else None,
        "last_log_time":  entries[-1]["timestamp"] if entries else None,
    }

    logger.info(
        "Pod log analysis complete — total=%d errors=%d warnings=%d error_rate=%.1f%%",
        total_count, error_count, warning_count, error_rate
    )

    # Return top 30 entries + full error lines (keeps context window manageable)
    result = {
        "summary":      summary,
        "error_lines":  error_lines,          # All errors — agent reads these closely
        "sample_entries": entries[:30],        # First 30 entries for context
    }

    return json.dumps(result, indent=2)


@tool
def list_available_pods() -> str:
    """
    Lists all EKS pod log files available in the logs directory.

    Use this tool FIRST if you are unsure which pods are available
    for investigation, or if you need to compare multiple pods.

    Returns:
        JSON string with list of available pods and their log files.
    """
    logger.info("Tool list_available_pods called")

    if not LOGS_DIR.exists():
        return json.dumps({"error": "logs/ directory not found"})

    pods = []
    for log_file in sorted(LOGS_DIR.glob("eks_pod_*.log")):
        # Extract pod name from filename: eks_pod_web_service_7d8b9c.log → web-service-7d8b9c
        stem = log_file.stem.replace("eks_pod_", "").replace("_", "-")
        # Last segment is the pod ID suffix
        parts = stem.rsplit("-", 1)
        service_name = parts[0] if len(parts) > 1 else stem
        pod_suffix   = parts[1] if len(parts) > 1 else "unknown"

        pods.append({
            "pod_name":    f"{service_name}-{pod_suffix}",
            "log_file":    log_file.name,
            "file_size_kb": round(log_file.stat().st_size / 1024, 1),
        })

    return json.dumps({
        "available_pods": pods,
        "total_pods":     len(pods),
        "logs_directory": str(LOGS_DIR.absolute()),
    }, indent=2)
