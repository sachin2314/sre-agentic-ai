"""
=============================================================================
FILE: src/tools/k8s_event_reader.py
COURSE: AI Agentic SRE - Day 8: Deep Dive — Agent Architectures
TOPIC:  Tool 2 of 2 — Read Kubernetes events from local files
=============================================================================

PURPOSE:
  This is TOOL 2 used by the ReAct agent.
  Reads and parses Kubernetes events from local log files.

  K8s events are CRITICAL for SRE investigation because they record:
  - OOMKilled events (container killed due to memory limit)
  - CrashLoopBackOff (pod restart loop detected)
  - Node memory pressure (node running low on memory)
  - Scheduling decisions (which node a pod was placed on)

  While pod logs show WHAT happened inside the container,
  K8s events show WHAT the Kubernetes control plane DID in response.
  You need BOTH to do proper RCA.

  In production, this would call:
    kubectl get events -n production --sort-by='.lastTimestamp' -o json
  or the Kubernetes API:
    k8s_client.CoreV1Api().list_namespaced_event(namespace=...)

HOW THIS FITS INTO THE REACT LOOP:
  After read_pod_logs shows OOM errors, the agent calls:
  Thought:      "Pod logs show OOMKilled. I need K8s events to confirm"
  Action:       read_k8s_events
  Action Input: {"namespace": "production", "pod_name": "web-service-7d8b9c"}
  Observation:  [JSON with OOMKilling events, CrashLoopBackOff events]
  → Agent now has BOTH pod-internal AND cluster-level evidence

ALGORITHM TO IMPLEMENT:
  1. Accept namespace and optional pod_name filter
  2. Find the k8s_events_<namespace>.log file
  3. Read line by line, skip comments
  4. Parse each line with regex to extract:
       - timestamp
       - event type (Normal / Warning)
       - reason (OOMKilled, BackOff, Scheduled, etc.)
       - object reference (pod/name or node/name)
       - message
  5. Filter by pod_name if provided
  6. Group Warning events separately (these are the important ones)
  7. Return structured JSON with:
       - all events (chronological)
       - warning events only
       - event type counts (OOMKilled: 3, BackOff: 2, etc.)
       - restart count (from BackOff/CrashLoopBackOff events)

REGEX PATTERN FOR EVENT LINE:
  ^(\S+)\s+(Normal|Warning)\s+(\S+)\s+(pod/\S+|node/\S+)\s+(.+)$
  Groups: (timestamp, type, reason, object, message)

REQUIREMENTS (pip install):
  pydantic>=2.0.0
  langchain-core>=0.2.0

=============================================================================
"""

import re
import json
from pathlib import Path
from datetime import datetime
from collections import Counter
from typing import Optional

from langchain_core.tools import tool

from src.utils.app_logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------
LOGS_DIR = Path("logs")

# Regex for Kubernetes event lines
# Example:
# 2024-01-15T09:47:05.000Z  Warning  OOMKilled  pod/web-service-7d8b9c  Container web-service OOMKilled
K8S_EVENT_PATTERN = re.compile(
    r"^(\S+)"                                       # Group 1: timestamp
    r"\s+(Normal|Warning)"                          # Group 2: type
    r"\s+(\S+)"                                     # Group 3: reason
    r"\s+((?:pod|node|deployment|service)/\S+)"     # Group 4: object reference
    r"\s+(.+)$"                                     # Group 5: message
)

# Events that indicate serious problems — agent should highlight these
CRITICAL_REASONS = {
    "OOMKilled", "OOMKilling", "CrashLoopBackOff", "BackOff",
    "FailedScheduling", "Evicted", "NodeNotReady", "MemoryPressure"
}


def _parse_timestamp(ts_str: str) -> Optional[datetime]:
    """Parse ISO8601 timestamp — same helper pattern as pod_log_reader."""
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    return None


def _find_events_file(namespace: str) -> Optional[Path]:
    """
    Find the K8s events file for the given namespace.

    ALGORITHM:
      Look for: k8s_events_{namespace}.log
      Fall back to: k8s_events_production.log
    """
    candidates = [
        LOGS_DIR / f"k8s_events_{namespace}.log",
        LOGS_DIR / "k8s_events_production.log",
    ]
    for candidate in candidates:
        if candidate.exists():
            logger.info("Found K8s events file: %s", candidate.name)
            return candidate

    logger.warning("No K8s events file found for namespace: %s", namespace)
    return None


# ---------------------------------------------------------------------------
# LANGCHAIN TOOL DEFINITIONS
# ---------------------------------------------------------------------------

@tool
def read_k8s_events(namespace: str = "production",
                    pod_name: Optional[str] = None,
                    event_type: str = "ALL") -> str:
    """
    Reads Kubernetes events for a namespace and returns structured event data.

    Use this tool AFTER read_pod_logs to get the cluster-level view of
    what happened. Kubernetes events show OOMKilled, CrashLoopBackOff,
    and node pressure events that explain WHY a pod failed.

    Args:
        namespace:   Kubernetes namespace to query. Default: "production"
        pod_name:    Optional pod name to filter events.
                     If provided, only returns events for that specific pod.
                     Example: "web-service-7d8b9c"
        event_type:  Filter by event type. Options: ALL, Warning, Normal
                     Default: ALL. Use "Warning" to focus on problems.

    Returns:
        JSON string containing:
        - warning_events:  Only Warning-type events (most important for RCA)
        - all_events:      All events in chronological order
        - event_counts:    Count by reason type (OOMKilled: 3, BackOff: 2)
        - restart_count:   Number of container restarts detected
        - critical_events: Events with critical reasons (OOMKilled etc.)
        - timeline:        Key events in chronological order for RCA
    """
    logger.info("Tool read_k8s_events called — namespace=%s pod=%s type=%s",
                namespace, pod_name, event_type)

    # -----------------------------------------------------------------------
    # STEP 1: Find the events file
    # -----------------------------------------------------------------------
    events_file = _find_events_file(namespace)
    if not events_file:
        return json.dumps({
            "error": f"No K8s events file found for namespace '{namespace}'",
            "tip": "Available event files: " + str(
                [f.name for f in LOGS_DIR.glob("k8s_events_*.log")]
            )
        })

    # -----------------------------------------------------------------------
    # STEP 2: Parse each event line
    # -----------------------------------------------------------------------
    all_events: list[dict] = []
    parse_errors: int = 0
    reason_counter: Counter = Counter()
    restart_count: int = 0

    with open(events_file, "r", encoding="utf-8") as f:
        for raw_line in f:
            raw_line = raw_line.strip()

            # Skip comments and blank lines
            if not raw_line or raw_line.startswith("#"):
                continue

            match = K8S_EVENT_PATTERN.match(raw_line)
            if not match:
                parse_errors += 1
                continue

            ts_str, e_type, reason, obj_ref, message = match.groups()

            ts = _parse_timestamp(ts_str)
            if ts is None:
                parse_errors += 1
                continue

            # ---------------------------------------------------------------
            # STEP 3: Apply pod_name filter
            # If pod_name filter is set, only keep events for that pod
            # BUT also keep node-level events (they affect all pods on node)
            # ---------------------------------------------------------------
            if pod_name:
                # Keep events for this specific pod
                pod_match = pod_name in obj_ref
                # Also keep node events (they may explain why the pod failed)
                node_event = obj_ref.startswith("node/")

                if not pod_match and not node_event:
                    continue

            # Apply event_type filter
            if event_type != "ALL" and e_type != event_type:
                continue

            # ---------------------------------------------------------------
            # STEP 4: Count restarts from BackOff/CrashLoopBackOff events
            # ---------------------------------------------------------------
            if reason in ("BackOff", "CrashLoopBackOff"):
                # Extract restart_count from message if present
                rc_match = re.search(r"restart[s_]?[=_:]?(\d+)", message, re.IGNORECASE)
                if rc_match:
                    restart_count = max(restart_count, int(rc_match.group(1)))

            reason_counter[reason] += 1

            event = {
                "timestamp":  ts.isoformat(),
                "type":       e_type,
                "reason":     reason,
                "object":     obj_ref,
                "message":    message[:300],
                "is_critical": reason in CRITICAL_REASONS,
            }
            all_events.append(event)

    # -----------------------------------------------------------------------
    # STEP 5: Separate warning and critical events
    # -----------------------------------------------------------------------
    warning_events  = [e for e in all_events if e["type"] == "Warning"]
    critical_events = [e for e in all_events if e["is_critical"]]

    # Build timeline: unique reason + message combos in order
    seen = set()
    timeline = []
    for e in all_events:
        key = f"{e['reason']}:{e['object']}"
        if key not in seen:
            seen.add(key)
            timeline.append({
                "time":    e["timestamp"],
                "type":    e["type"],
                "reason":  e["reason"],
                "object":  e["object"],
                "summary": e["message"][:150],
            })

    # -----------------------------------------------------------------------
    # STEP 6: Build summary for agent reasoning
    # -----------------------------------------------------------------------
    summary = {
        "namespace":          namespace,
        "pod_filter":         pod_name,
        "total_events":       len(all_events),
        "warning_count":      len(warning_events),
        "critical_count":     len(critical_events),
        "restart_count":      restart_count,
        "reason_counts":      dict(reason_counter.most_common(10)),
        "has_oomkilled":      "OOMKilled" in reason_counter or "OOMKilling" in reason_counter,
        "has_crashloopbackoff": "CrashLoopBackOff" in reason_counter,
        "has_node_pressure":  "MemoryPressure" in reason_counter,
        "parse_errors":       parse_errors,
    }

    logger.info(
        "K8s events parsed — total=%d warnings=%d critical=%d restarts=%d",
        len(all_events), len(warning_events), len(critical_events), restart_count
    )

    result = {
        "summary":        summary,
        "timeline":       timeline,           # Deduplicated chronological view
        "critical_events": critical_events,   # OOMKilled, CrashLoopBackOff etc.
        "warning_events": warning_events,     # All Warning events
    }

    return json.dumps(result, indent=2)


@tool
def read_node_metrics(node_name: Optional[str] = None) -> str:
    """
    Reads EKS node-level memory and CPU metrics from local metric files.

    Use this tool when pod OOMKilled events suggest node memory pressure.
    Node pressure means multiple pods on the same node are competing for
    memory — not just a single pod issue.

    Args:
        node_name: Optional node to filter by. Example: "node-worker-3"
                   If None, returns metrics for all nodes.

    Returns:
        JSON with node metrics, memory pressure periods, and peak usage times.
    """
    logger.info("Tool read_node_metrics called — node=%s", node_name)

    metrics_file = LOGS_DIR / "k8s_node_metrics.log"
    if not metrics_file.exists():
        return json.dumps({"error": "Node metrics file not found: k8s_node_metrics.log"})

    node_data: list[dict] = []

    # Regex for node metric lines
    # 2024-01-15T09:20:00.000Z  node-worker-3  memory_utilization=72.5%  ...
    line_pattern = re.compile(
        r"^(\S+)"                           # timestamp
        r"\s+(node-\S+)"                    # node name
        r"\s+memory_utilization=(\S+)"      # memory %
        r"\s+memory_used=(\S+)"             # used
        r"\s+memory_capacity=(\S+)"         # capacity
        r"\s+cpu_utilization=(\S+)"         # cpu %
        r"(.*)$"                            # optional extra fields
    )

    with open(metrics_file, "r", encoding="utf-8") as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line or raw_line.startswith("#"):
                continue

            match = line_pattern.match(raw_line)
            if not match:
                continue

            ts_str, node, mem_pct, mem_used, mem_cap, cpu_pct, extra = match.groups()

            if node_name and node != node_name:
                continue

            ts = _parse_timestamp(ts_str)
            if ts is None:
                continue

            # Parse MEMORY_PRESSURE flag from extra fields
            is_pressure = "MEMORY_PRESSURE=true" in extra
            oom_candidate = re.search(r"OOM_KILL_CANDIDATE=(\S+)", extra)

            node_data.append({
                "timestamp":       ts.isoformat(),
                "node":            node,
                "memory_pct":      mem_pct,
                "memory_used":     mem_used,
                "memory_capacity": mem_cap,
                "cpu_pct":         cpu_pct,
                "memory_pressure": is_pressure,
                "oom_candidate":   oom_candidate.group(1) if oom_candidate else None,
            })

    # Find pressure periods
    pressure_periods = [d for d in node_data if d["memory_pressure"]]
    oom_candidates   = [d for d in node_data if d.get("oom_candidate")]

    result = {
        "node_metrics":       node_data,
        "pressure_periods":   pressure_periods,
        "oom_kill_candidates": oom_candidates,
        "total_readings":     len(node_data),
        "nodes_with_pressure": list({d["node"] for d in pressure_periods}),
    }

    return json.dumps(result, indent=2)
