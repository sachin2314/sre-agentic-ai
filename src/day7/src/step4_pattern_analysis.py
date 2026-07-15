"""
============================================================
STEP 4 — Pattern Analysis (Cross-Log Correlation)
============================================================

WHAT THIS FILE DOES
--------------------
Groups related anomalies together into "incident patterns".

A single anomaly in one log source might be noise.
But when 5 anomalies from 4 different sources all happen
within the same 5-minute window, that is almost certainly
one connected incident.

This step answers the question:
  "Which anomalies happened close together and are probably related?"

This is called cross-log correlation — connecting events
across different systems to see the full picture.

------------------------------------------------------------
REQUIREMENTS (read this before writing any code)
------------------------------------------------------------
You need to build THESE pieces:

  Data class — IncidentPattern
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Holds the result of grouping related anomalies together.
  Fields:
    pattern_id   : str           "INC-001"
    pattern_name : str           human-readable name e.g. "DB-driven failure"
    severity     : str           worst severity of all anomalies in group
    start_time   : str           earliest anomaly timestamp
    end_time     : str           latest anomaly timestamp
    sources      : list[str]     which log sources are involved
    anomalies    : list[Anomaly] the anomalies that belong to this pattern
    description  : str           one-line summary

  Helper — within_minutes(ts1, ts2, minutes=5)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Input : two timestamp strings, optional window size
  Output: True if the two timestamps are within 'minutes' of each other
  Rules :
    - Parse both strings using datetime.strptime with format "%Y-%m-%d %H:%M"
    - Take absolute difference in seconds
    - Return True if difference <= minutes * 60

  Helper — cluster_severity(anomalies_in_cluster)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Input : list of Anomaly objects
  Output: the worst severity string in the list
  Rules :
    - Define a rank dict: CRITICAL=4, HIGH=3, MEDIUM=2, LOW=1
    - Loop through anomalies and track the highest rank
    - Return the corresponding severity string

  Helper — name_pattern(anomalies_in_cluster)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Input : list of Anomaly objects
  Output: a descriptive name string
  Rules :
    - Get the set of sources involved
    - If database + (app or nginx) → "Database-driven application failure"
    - If kubernetes + app → "Pod restart / application outage"
    - If only nginx → "Upstream / gateway error spike"
    - If only database → "Database anomaly"
    - Otherwise → "General anomaly cluster"

  Main — cluster_anomalies(anomalies, window_minutes=5)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Input : list of Anomaly objects (sorted by timestamp)
  Output: list of clusters, each cluster is a list of Anomaly objects
  Rules :
    - Sort anomalies by timestamp
    - Start first cluster with the first anomaly
    - For each subsequent anomaly:
        if it is within window_minutes of the cluster's START → add to cluster
        else → start a new cluster
    - Return list of clusters

  Main — build_incident_patterns(clusters)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Input : list of clusters (list of list of Anomaly)
  Output: list of IncidentPattern objects
  Rules :
    - For each cluster:
        pattern_id   = "INC-001", "INC-002", etc.
        severity     = call cluster_severity()
        sources      = unique list of source names in the cluster
        start_time   = min timestamp in the cluster
        end_time     = max timestamp in the cluster
        pattern_name = call name_pattern()
        description  = build a summary string
    - Return list of IncidentPattern

  Runner — analyse_patterns(entries)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Input : list of parsed log entries (from step2)
  Output: list of IncidentPattern objects
  Rules :
    - Call run_all_detectors(entries) to get anomalies
    - Call cluster_anomalies() to group them
    - Call build_incident_patterns() to convert clusters to patterns
    - Return patterns

------------------------------------------------------------
ALGORITHM (plain English — try to code this yourself first)
------------------------------------------------------------

Step A  Define IncidentPattern dataclass

Step B  Write within_minutes(ts1, ts2, minutes=5):
    1.  Slice both timestamps to first 16 chars (strip seconds)
    2.  Parse with datetime.strptime(ts, "%Y-%m-%d %H:%M")
    3.  diff = abs((t2 - t1).total_seconds())
    4.  Return diff <= (minutes * 60)

Step C  Write cluster_severity(anomalies_in_cluster):
    1.  Define SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    2.  Start with worst = "LOW"
    3.  For each anomaly:
        if SEVERITY_RANK[anomaly.severity] > SEVERITY_RANK[worst]:
            worst = anomaly.severity
    4.  Return worst

Step D  Write name_pattern(anomalies_in_cluster):
    1.  sources = set(a.source for a in anomalies_in_cluster)
    2.  Check conditions and return appropriate name

Step E  Write cluster_anomalies(anomalies, window_minutes=5):
    1.  If no anomalies → return []
    2.  sorted_anomalies = sorted(anomalies, key=lambda a: a.timestamp)
    3.  current_cluster  = [sorted_anomalies[0]]
    4.  cluster_start    = sorted_anomalies[0].timestamp
    5.  clusters         = []
    6.  For each anomaly in sorted_anomalies[1:]:  (skip the first — already added)
        if within_minutes(cluster_start, anomaly.timestamp, window_minutes):
            current_cluster.append(anomaly)
        else:
            clusters.append(current_cluster)  (save the completed cluster)
            current_cluster = [anomaly]       (start a new cluster)
            cluster_start   = anomaly.timestamp
    7.  clusters.append(current_cluster)  (save the last cluster)
    8.  Return clusters

Step F  Write build_incident_patterns(clusters):
    1.  patterns = []
    2.  For idx, cluster in enumerate(clusters):
        a. pattern_id = f"INC-{idx + 1:03d}"   (INC-001, INC-002, ...)
        b. severity   = cluster_severity(cluster)
        c. sources    = list(set(a.source for a in cluster))
        d. start_time = min(a.timestamp for a in cluster)
        e. end_time   = max(a.timestamp for a in cluster)
        f. name       = name_pattern(cluster)
        g. description = f"{len(cluster)} anomalies across ... sources"
        h. Create IncidentPattern and append to patterns
    3.  Return patterns

Step G  Write analyse_patterns(entries):
    1.  anomalies = run_all_detectors(entries)
    2.  clusters  = cluster_anomalies(anomalies)
    3.  patterns  = build_incident_patterns(clusters)
    4.  Return patterns

------------------------------------------------------------
PYTHON CONCEPTS USED IN THIS FILE
------------------------------------------------------------
  @dataclass        — auto-generates __init__ for data classes
  datetime.strptime — parse a string into a datetime object
  abs()             — absolute value (makes negative diffs positive)
  .total_seconds()  — convert a timedelta to seconds
  set()             — removes duplicates from a list
  min() / max()     — find smallest / largest value in an iterable
  enumerate()       — loop with both index and value
  f"{n:03d}"        — format integer with leading zeros to 3 digits

------------------------------------------------------------
HOW TO RUN
------------------------------------------------------------
  python src/step4_pattern_analysis.py

------------------------------------------------------------
"""

# ============================================================
# IMPORTS
# ============================================================

from dataclasses import dataclass, field
from typing import List
from datetime import datetime
# datetime.strptime() parses a string into a datetime object.
# datetime objects support subtraction: t2 - t1 gives a timedelta object.
# timedelta.total_seconds() converts that difference into a float of seconds.

from step1_load_logs import load_all_logs
from step2_parse_logs import parse_all_logs
from step3_anomaly_detection import run_all_detectors, Anomaly


# ============================================================
# DATA CLASS — IncidentPattern
# ============================================================

@dataclass
class IncidentPattern:
    """
    Represents a group of related anomalies that form one incident.

    Multiple Anomaly objects (from different log sources) that
    happen in the same time window are grouped into one IncidentPattern.
    This gives SREs a single "incident" to investigate rather than
    dozens of individual anomaly alerts.
    """
    pattern_id:   str              # unique ID like "INC-001"
    pattern_name: str              # "Database-driven application failure"
    severity:     str              # the worst severity among anomalies
    start_time:   str              # earliest anomaly in this group
    end_time:     str              # latest anomaly in this group
    sources:      List[str]        # which log sources are in this group
    anomalies:    List[Anomaly]    # the full list of anomalies
    description:  str = ""         # summary sentence


# ============================================================
# HELPER — within_minutes
# ============================================================

def within_minutes(ts1, ts2, minutes=5):
    """
    Return True if two timestamps are within 'minutes' of each other.

    Parameters
    ----------
    ts1, ts2 : str
        Timestamp strings like "2024-01-15 09:20" or "2024-01-15 09:20:08"
    minutes  : int
        Maximum allowed gap in minutes (default 5)

    Returns
    -------
    bool

    Example
    -------
    within_minutes("2024-01-15 09:18", "2024-01-15 09:20", minutes=5)
    → True  (only 2 minutes apart)

    within_minutes("2024-01-15 09:00", "2024-01-15 09:20", minutes=5)
    → False (20 minutes apart — too far)

    Why datetime instead of string comparison?
    ------------------------------------------
    We can't just subtract strings like "09:20" - "09:18".
    datetime objects support subtraction and give us a timedelta
    that we can convert to seconds for precise comparison.
    """
    fmt = "%Y-%m-%d %H:%M"   # the format our timestamps use

    # Slice to 16 characters to strip seconds (if present).
    # "2024-01-15 09:20:08"[:16] → "2024-01-15 09:20"
    # "2024-01-15 09:20"[:16]    → "2024-01-15 09:20" (already correct)
    ts1_clean = ts1[:16]
    ts2_clean = ts2[:16]

    try:
        # strptime = "string parse time"
        # It converts a string into a datetime object using the given format.
        t1 = datetime.strptime(ts1_clean, fmt)
        t2 = datetime.strptime(ts2_clean, fmt)

        # Subtracting two datetime objects gives a timedelta object.
        # .total_seconds() converts the timedelta to a float of seconds.
        # abs() makes sure we handle both t1 > t2 and t2 > t1 cases.
        diff = abs((t2 - t1).total_seconds())

        # Return True if the difference is within the allowed window
        return diff <= (minutes * 60)   # convert minutes to seconds

    except ValueError:
        # If parsing fails (bad format), treat as "not close enough"
        return False


# ============================================================
# HELPER — cluster_severity
# ============================================================

# Map severity names to numeric ranks so we can compare them.
# A higher number = more severe.
SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}


def cluster_severity(anomalies_in_cluster):
    """
    Find the worst severity in a cluster of anomalies.

    Parameters
    ----------
    anomalies_in_cluster : list[Anomaly]

    Returns
    -------
    str
        The worst severity found: "CRITICAL", "HIGH", "MEDIUM", or "LOW"

    Example
    -------
    If a cluster has [HIGH, MEDIUM, CRITICAL, HIGH] → returns "CRITICAL"
    """
    worst = "LOW"   # start with the lowest possible severity

    for anomaly in anomalies_in_cluster:
        # Compare numeric ranks.
        # .get(key, 0) returns 0 if the key is not in SEVERITY_RANK
        # (handles unexpected severity values gracefully).
        if SEVERITY_RANK.get(anomaly.severity, 0) > SEVERITY_RANK.get(worst, 0):
            worst = anomaly.severity   # upgrade to the more severe level

    return worst


# ============================================================
# HELPER — name_pattern
# ============================================================

def name_pattern(anomalies_in_cluster):
    """
    Give a human-readable name to an incident cluster based on
    which log sources are involved.

    Parameters
    ----------
    anomalies_in_cluster : list[Anomaly]

    Returns
    -------
    str
        A descriptive pattern name.

    Why name patterns?
    ------------------
    "INC-001 had anomalies in database, app, nginx, kubernetes" is not useful.
    "Database-driven application failure" immediately tells the SRE what kind
    of incident they are dealing with and which runbook to follow.
    """
    # Collect all unique sources involved in this cluster
    sources = set(a.source for a in anomalies_in_cluster)
    # set() removes duplicates — if "app" appears 10 times, we keep one.

    # Check combinations from most specific to least specific.
    # Python's 'in' operator on sets is O(1) — very fast.
    if "database" in sources and ("app" in sources or "nginx_access" in sources):
        return "Database-driven application failure"

    if "kubernetes" in sources and "app" in sources:
        return "Pod restart / application outage"

    if "nginx_access" in sources or "nginx_error" in sources:
        return "Upstream / gateway error spike"

    if "database" in sources:
        return "Database anomaly"

    # Fallback name when we can't identify a specific pattern
    return "General anomaly cluster"


# ============================================================
# MAIN — cluster_anomalies
# ============================================================

def cluster_anomalies(anomalies, window_minutes=5):
    """
    Group anomalies that happened within 'window_minutes' of each other.

    Parameters
    ----------
    anomalies      : list[Anomaly]  — all detected anomalies
    window_minutes : int            — time window for grouping (default 5)

    Returns
    -------
    list[list[Anomaly]]
        A list of clusters.  Each cluster is itself a list of Anomaly objects.

    Algorithm: Greedy Time-Window Clustering
    -----------------------------------------
    1. Sort anomalies by timestamp.
    2. Take the first anomaly — it starts the first cluster.
       Remember this cluster's start time.
    3. For each subsequent anomaly:
       - If it is within window_minutes of the cluster's START time → add it
       - If it is farther away → close the current cluster, start a new one
    4. After the loop, save the last cluster.

    Why use the CLUSTER START time (not the previous anomaly's time)?
    -----------------------------------------------------------------
    Using the previous anomaly's time causes "chain linking":
      anomaly at 09:00 → starts cluster
      anomaly at 09:04 → within 5 min of 09:00 → added
      anomaly at 09:08 → within 5 min of 09:04 → added  ← WRONG!
      anomaly at 09:12 → within 5 min of 09:08 → added  ← WRONG!
    Using the cluster's START time (09:00) limits the cluster to:
      anomaly at 09:00 → starts cluster
      anomaly at 09:04 → within 5 min of 09:00 → added ✓
      anomaly at 09:06 → within 5 min of 09:00 → added ✓
      anomaly at 09:08 → within 5 min of 09:00 → CLOSES cluster, new cluster starts
    This gives tighter, more meaningful groups.

    Example Output
    --------------
    [[anomaly_09:18, anomaly_09:19, anomaly_09:20, anomaly_09:20, ...],
     [anomaly_09:25]]
    """
    if not anomalies:
        return []   # handle empty input gracefully

    # Sort by timestamp so we process anomalies in time order.
    sorted_anomalies = sorted(anomalies, key=lambda a: a.timestamp)

    # Initialise the first cluster with the very first anomaly.
    clusters = []
    current_cluster = [sorted_anomalies[0]]
    cluster_start   = sorted_anomalies[0].timestamp   # remember when this cluster started

    # Process all remaining anomalies (starting from index 1, skipping index 0)
    for anomaly in sorted_anomalies[1:]:
        if within_minutes(cluster_start, anomaly.timestamp, window_minutes):
            # This anomaly is close enough in time → add to current cluster
            current_cluster.append(anomaly)
        else:
            # Too far away in time → save the current cluster and start a new one
            clusters.append(current_cluster)     # save completed cluster
            current_cluster = [anomaly]          # start fresh cluster
            cluster_start   = anomaly.timestamp  # new cluster's start time

    # Don't forget to save the LAST cluster after the loop ends
    clusters.append(current_cluster)

    return clusters


# ============================================================
# MAIN — build_incident_patterns
# ============================================================

def build_incident_patterns(clusters):
    """
    Convert each cluster of anomalies into a named IncidentPattern object.

    Parameters
    ----------
    clusters : list[list[Anomaly]]
        Output from cluster_anomalies()

    Returns
    -------
    list[IncidentPattern]

    Why convert clusters to IncidentPattern objects?
    ------------------------------------------------
    A plain list of anomalies is hard to work with.
    IncidentPattern wraps them with useful metadata:
    a name, a severity, a time range, and the list of sources.
    This makes it easy for Step 5 (RCA) and Step 6 (report) to consume.
    """
    patterns = []

    # enumerate() gives us both the index and the value in each iteration.
    # idx=0, cluster=[...] → idx=1, cluster=[...] → etc.
    for idx, cluster in enumerate(clusters):

        # Build a human-readable ID like INC-001, INC-002, etc.
        # f"{idx + 1:03d}"  formats the integer with leading zeros to 3 digits:
        #   1 → "001", 2 → "002", 10 → "010", 100 → "100"
        pattern_id = f"INC-{idx + 1:03d}"

        severity     = cluster_severity(cluster)
        sources      = list(set(a.source for a in cluster))   # unique sources
        start_time   = min(a.timestamp for a in cluster)      # earliest timestamp
        end_time     = max(a.timestamp for a in cluster)      # latest timestamp
        pattern_name = name_pattern(cluster)

        description = (
            f"{len(cluster)} anomalies across {len(sources)} source(s) "
            f"from {start_time} to {end_time}."
        )

        patterns.append(IncidentPattern(
            pattern_id=pattern_id,
            pattern_name=pattern_name,
            severity=severity,
            start_time=start_time,
            end_time=end_time,
            sources=sources,
            anomalies=cluster,
            description=description,
        ))

    return patterns


# ============================================================
# RUNNER — analyse_patterns
# ============================================================

def analyse_patterns(entries):
    """
    Full analysis pipeline: detect anomalies → cluster → build patterns.

    Parameters
    ----------
    entries : list[dict]  — parsed log entries from step2

    Returns
    -------
    list[IncidentPattern]

    This is the main function to call from outside this module.
    It chains together all the steps in this file.
    """
    # Step 1: Run all three anomaly detectors
    anomalies = run_all_detectors(entries)

    # Step 2: Group close-in-time anomalies into clusters
    clusters = cluster_anomalies(anomalies, window_minutes=5)

    # Step 3: Convert clusters into named IncidentPattern objects
    patterns = build_incident_patterns(clusters)

    return patterns


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("=" * 55)
    print("STEP 4 — Pattern Analysis")
    print("=" * 55)

    raw_logs = load_all_logs()
    entries  = parse_all_logs(raw_logs)
    patterns = analyse_patterns(entries)

    print(f"\nIncident patterns found: {len(patterns)}")


    for p in patterns:
        print(f"\n{'=' * 50}")
        print(f"  {p.pattern_id}  [{p.severity}]  {p.pattern_name}")
        print(f"  Time range: {p.start_time} → {p.end_time}")
        print(f"  Sources:    {', '.join(p.sources)}")
        print(f"  Summary:    {p.description}")
        print(f"  Anomalies in this pattern:")
        for a in p.anomalies[:4]:
            print(f"    [{a.severity:8s}] [{a.anomaly_type:12s}] {a.description[:80]}")
        if len(p.anomalies) > 4:
            print(f"    ... and {len(p.anomalies) - 4} more")
