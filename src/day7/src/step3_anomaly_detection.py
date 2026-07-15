"""
============================================================
STEP 3 — Anomaly Detection
============================================================

WHAT THIS FILE DOES
--------------------
Scans the parsed log entries (from Step 2) and flags anything
that looks unusual or dangerous.

We use THREE detection patterns, from simplest to smartest:
  1. THRESHOLD  — "more than N errors per minute is bad"
  2. STATISTICAL — "this response time is far above average"
  3. KEYWORD    — "these words always mean something broke"

Each detector returns a list of Anomaly objects.
The main function runs all three and combines the results.

------------------------------------------------------------
REQUIREMENTS (read this before writing any code)
------------------------------------------------------------
You need to build THESE pieces:

  Data class — Anomaly
  ~~~~~~~~~~~~~~~~~~~~~
  A dataclass to hold information about one detected anomaly.
  Fields:
    anomaly_type : str        "threshold" / "statistical" / "keyword"
    severity     : str        "LOW" / "MEDIUM" / "HIGH" / "CRITICAL"
    source       : str        which log file triggered this
    timestamp    : str        when it happened
    description  : str        human-readable explanation
    evidence     : list[str]  the raw log line(s) that triggered it

  Helper — group_by_minute(entries)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Input : list of log entry dicts (from step2)
  Output: dict where key = "YYYY-MM-DD HH:MM" and value = list of entries
  Rules : slice entry["timestamp"][:16] to get the minute key

  Detector 1 — detect_threshold_anomalies(entries, error_threshold=3)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Input : list of entries, optional threshold int
  Output: list of Anomaly objects
  Rules :
    - Group entries by minute (use group_by_minute)
    - For each minute, count entries where level is ERROR or FATAL
    - If count >= error_threshold → create an Anomaly with type="threshold"
    - Severity = HIGH if count >= 6, else MEDIUM

  Detector 2 — detect_statistical_anomalies(entries, z_threshold=2.0)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Input : list of entries, optional z-score threshold
  Output: list of Anomaly objects
  Rules :
    - Filter to only nginx_access entries that have a "response_time" field
    - Group by minute, compute average response_time per minute
    - Compute the overall mean and stdev of all per-minute averages
    - Z-score = (value - mean) / stdev
    - If z_score > z_threshold → create an Anomaly with type="statistical"
    - Severity = CRITICAL if z_score > 4, else HIGH

  Detector 3 — detect_keyword_anomalies(entries)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Input : list of entries
  Output: list of Anomaly objects
  Rules :
    - Define two keyword lists: CRITICAL_KEYWORDS and HIGH_KEYWORDS
    - For each entry, check if any keyword appears in the message (case-insensitive)
    - Check CRITICAL first. If found → create CRITICAL anomaly and skip HIGH check
    - If not critical → check HIGH keywords

  Runner — run_all_detectors(entries)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Input : list of entries
  Output: combined list of all anomalies, sorted by timestamp
  Rules : call all three detectors, combine with +, sort by timestamp

------------------------------------------------------------
ALGORITHM (plain English — try to code this yourself first)
------------------------------------------------------------

Step A  Define the Anomaly dataclass (use @dataclass decorator)

Step B  Write group_by_minute(entries):
    1.  Create empty dict called buckets
    2.  For each entry:
        a. Take entry["timestamp"][:16]  (cuts off the seconds)
           "2024-01-15 09:20:08"[:16] → "2024-01-15 09:20"
        b. If that key is not in buckets yet → set buckets[key] = []
        c. Append the entry to buckets[key]
    3.  Return buckets

Step C  Write detect_threshold_anomalies(entries, error_threshold=3):
    1.  Create empty list called anomalies
    2.  Call group_by_minute(entries) to get buckets
    3.  For each (minute, bucket_entries) in buckets.items():
        a. Filter bucket_entries to keep only ERROR and FATAL entries
        b. If len(filtered) >= error_threshold:
           - Collect sources (unique list of where the errors came from)
           - Build up to 3 evidence strings
           - Decide severity (HIGH if >= 6 errors, else MEDIUM)
           - Create an Anomaly object and append to anomalies
    4.  Return anomalies

Step D  Write detect_statistical_anomalies(entries, z_threshold=2.0):
    1.  Filter entries to nginx_access entries with "response_time" in fields
    2.  If fewer than 5 entries → return [] (not enough data)
    3.  Group by minute, compute average response_time per minute
    4.  If fewer than 3 minutes of data → return []
    5.  Compute mean = sum(averages) / len(averages)
    6.  Compute stdev using statistics.stdev(averages)
    7.  If stdev == 0 → return [] (all identical, can't compute z-score)
    8.  For each (minute, avg) in minute_averages:
        a. z_score = (avg - mean) / stdev
        b. If z_score > z_threshold:
           - severity = CRITICAL if z_score > 4 else HIGH
           - Create Anomaly and append
    9.  Return anomalies

Step E  Define CRITICAL_KEYWORDS and HIGH_KEYWORDS lists

Step F  Write detect_keyword_anomalies(entries):
    1.  Create empty list called anomalies
    2.  For each entry:
        a. message_lower = entry["message"].lower()
        b. Loop CRITICAL_KEYWORDS first:
           if keyword.lower() in message_lower:
               create CRITICAL Anomaly → append → break (stop checking)
        c. If no CRITICAL keyword matched (else clause on the for loop):
           Loop HIGH_KEYWORDS:
               if keyword.lower() in message_lower:
                   create HIGH Anomaly → append → break
    3.  Return anomalies

Step G  Write run_all_detectors(entries):
    1.  Call each detector
    2.  Combine all results with + (list concatenation)
    3.  Sort combined list by anomaly.timestamp
    4.  Return sorted list

------------------------------------------------------------
PYTHON CONCEPTS USED IN THIS FILE
------------------------------------------------------------
  @dataclass       — decorator that auto-generates __init__ and __repr__
  field()          — used in dataclass to set a default for a mutable field
  statistics.mean()  — computes arithmetic average
  statistics.stdev() — computes standard deviation
  list.sort()      — sort in place (modifies the original list)
  for...else       — the else runs if the for loop completes without break
  Counter          — counts occurrences of each value

------------------------------------------------------------
HOW TO RUN
------------------------------------------------------------
  python src/step3_anomaly_detection.py

------------------------------------------------------------
"""

# ============================================================
# IMPORTS
# ============================================================

import statistics
# Built-in Python library for basic statistics.
# statistics.mean()  → arithmetic average of a list of numbers
# statistics.stdev() → standard deviation of a list of numbers
# No pip install needed.

from dataclasses import dataclass, field
# dataclass : a decorator that auto-generates boilerplate like __init__
# field()   : used to declare a mutable default (like an empty list)
# We use these to define the Anomaly class cleanly.

from typing import List
# List is used in type annotations like List[str].
# This is for documentation only — Python doesn't enforce types at runtime.

from collections import Counter
# Counts occurrences. Used in the __main__ section.

from step1_load_logs import load_all_logs
from step2_parse_logs import parse_all_logs


# ============================================================
# DATA CLASS — Anomaly
# ============================================================
# @dataclass is a Python decorator introduced in Python 3.7.
# It reads the field annotations below and automatically generates:
#   __init__()   → the constructor  (so you can write Anomaly(type="threshold", ...))
#   __repr__()   → a string representation for printing
#
# Without @dataclass, you'd have to write the __init__ yourself — tedious.

@dataclass
class Anomaly:
    """
    Represents one detected anomaly.

    Think of this like a named tuple but more powerful.
    Every field below becomes a parameter in __init__.
    """
    anomaly_type: str    # "threshold", "statistical", or "keyword"
    severity:     str    # "LOW", "MEDIUM", "HIGH", or "CRITICAL"
    source:       str    # which log source triggered this e.g. "database"
    timestamp:    str    # when it happened e.g. "2024-01-15 09:20"
    description:  str    # human-readable explanation of what was detected

    # 'evidence' is a list, and lists are mutable — you can't set a mutable
    # value as a default directly in a dataclass.  You must use field(default_factory=...)
    # which tells the dataclass to call list() freshly for each new instance.
    evidence: List[str] = field(default_factory=list)


# ============================================================
# HELPER — group_by_minute
# ============================================================

def group_by_minute(entries):
    """
    Group log entries by their minute (YYYY-MM-DD HH:MM).

    Parameters
    ----------
    entries : list[dict]
        Parsed log entries from step2.

    Returns
    -------
    dict[str, list[dict]]
        Key = "YYYY-MM-DD HH:MM"
        Value = list of entries that happened in that minute

    Why group by minute?
    --------------------
    A single error is noise. 10 errors in the same minute is a signal.
    Grouping by minute lets us count errors per time window.

    Example
    -------
    "2024-01-15 09:20:08"[:16]  →  "2024-01-15 09:20"
    "2024-01-15 09:20:44"[:16]  →  "2024-01-15 09:20"  (same bucket!)
    "2024-01-15 09:21:03"[:16]  →  "2024-01-15 09:21"  (different bucket)
    """
    buckets = {}   # will become { "2024-01-15 09:20": [entry1, entry2, ...], ... }

    for entry in entries:
        # entry["timestamp"] is like "2024-01-15 09:20:08"
        # [:16] slices the first 16 characters → "2024-01-15 09:20"
        # This strips the seconds, grouping all entries in the same minute together.
        minute_key = entry["timestamp"][:16]

        # If this minute is not in the dict yet, create an empty list for it.
        if minute_key not in buckets:
            buckets[minute_key] = []
        # Add this entry to the correct bucket.
        buckets[minute_key].append(entry)
    return buckets


# ============================================================
# DETECTOR 1 — Threshold-Based
# ============================================================

def detect_threshold_anomalies(entries, error_threshold=3):
    """
    Flag any minute that has more than 'error_threshold' ERROR/FATAL entries.

    Parameters
    ----------
    entries         : list[dict]  — all parsed log entries
    error_threshold : int         — how many errors/minute triggers an anomaly

    Returns
    -------
    list[Anomaly]

    How it works
    ------------
    Think of it as: "set an alarm if the error counter goes above N".
    We count errors per minute, and if the count exceeds our threshold,
    we create an Anomaly record.

    Tuning
    ------
    Lower threshold → more sensitive → more false positives
    Higher threshold → less sensitive → may miss real incidents
    """
    anomalies = []   # we'll add Anomaly objects here

    # Group all entries into 1-minute buckets
    buckets = group_by_minute(entries)

    
    # Examine each minute bucket
    for minute, bucket_entries in buckets.items():

        # Keep only entries that are ERROR or FATAL level
        # (WARN is not serious enough to trigger a threshold alert)
        bad_entries = [
            e for e in bucket_entries
            if e["level"] in ("ERROR", "FATAL", "CRIT")
        ]

        # This is a list comprehension with a filter condition:
        # [item for item in iterable if condition]

        # If the number of bad entries is at or above our threshold → anomaly!
        if len(bad_entries) >= error_threshold:

            # Collect the unique sources that produced errors this minute
            # set() removes duplicates — if "app" appears 5 times, we only keep one.
            sources = list(set(e["source"] for e in bad_entries))
            # Build evidence strings (up to 3 examples so the report isn't huge)
            evidence = [
                f"[{e['source']}] {e['message'][:80]}"
                for e in bad_entries[:3]
            ]

            # Decide severity based on count
            # >= 6 errors in a minute is very serious → HIGH
            # Anything below but above threshold is MEDIUM
            severity = "HIGH" if len(bad_entries) >= 6 else "MEDIUM"

            # Create an Anomaly object and add it to our results
            anomalies.append(Anomaly(
                anomaly_type="threshold",
                severity=severity,
                source=", ".join(sources),   # e.g. "app, database"
                timestamp=minute,            # "2024-01-15 09:20"
                description=(
                    f"Error spike: {len(bad_entries)} errors in 1 minute "
                    f"(threshold={error_threshold}). Sources: {sources}"
                ),
                evidence=evidence,
            ))

    return anomalies


# ============================================================
# DETECTOR 2 — Statistical (Z-Score)
# ============================================================

def detect_statistical_anomalies(entries, z_threshold=2.0):
    """
    Flag any minute where the average nginx response time is unusually high.

    Parameters
    ----------
    entries     : list[dict]  — all parsed log entries
    z_threshold : float       — how many standard deviations = anomalous

    Returns
    -------
    list[Anomaly]

    What is a Z-score?
    ------------------
    Z-score = (value - mean) / standard_deviation

    It measures "how far is this value from average, in units of std dev".

      Z = 0  → exactly average
      Z = 1  → 1 std dev above average  (normal range)
      Z = 2  → 2 std devs above average (~5% of values are this high)
      Z = 3  → 3 std devs above average (~0.3% of values — very unusual)

    We use Z-score instead of a fixed threshold because "slow" is relative.
    200ms might be normal for one service and terrible for another.
    Z-score adapts automatically based on what "normal" looks like for this data.

    Example
    -------
    Average response times per minute:
        09:00 = 0.05s, 09:05 = 0.04s, 09:10 = 0.06s  ← normal
        09:20 = 1.80s  ← very high

    mean  = (0.05 + 0.04 + 0.06 + 1.80) / 4 = 0.49s
    stdev = statistics.stdev([0.05, 0.04, 0.06, 1.80]) ≈ 0.87s
    z_score at 09:20 = (1.80 - 0.49) / 0.87 ≈ 1.51  → flag if > z_threshold
    """
    anomalies = []

    # Filter to only nginx_access entries that have a response_time value.
    # We can only compute a Z-score on numeric data.
    nginx_entries = [
        e for e in entries
        if e["source"] == "nginx_access" and "response_time" in e["fields"]
    ]

    # We need at least 5 entries to compute meaningful statistics.
    # With fewer data points, the mean and stdev are unreliable.
    if len(nginx_entries) < 5:
        return anomalies   # return empty list — not enough data

    # Compute average response time for each minute
    buckets = group_by_minute(nginx_entries)
    minute_averages = {}   # { "2024-01-15 09:20": 1.795, ... }

    for minute, bucket_entries in buckets.items():
        times = []   # collect response times for this minute

        for e in bucket_entries:
            try:
                # e["fields"]["response_time"] is a string like "5.001"
                # float() converts it to a number: 5.001
                times.append(float(e["fields"]["response_time"]))
            except ValueError:
                pass   # skip if the value can't be converted to float

        if times:
            # Store the average response time for this minute
            minute_averages[minute] = sum(times) / len(times)

    # We need at least 3 data points (3 different minutes) to compute std dev
    if len(minute_averages) < 3:
        return anomalies

    # Compute the OVERALL mean and standard deviation
    all_averages = list(minute_averages.values())

    mean  = statistics.mean(all_averages)    # arithmetic average
    stdev = statistics.stdev(all_averages)   # measure of spread

    # If stdev is 0, all values are identical → no anomaly possible
    if stdev == 0:
        return anomalies

    # Now check each minute: is its average response time an outlier?
    for minute, avg_time in minute_averages.items():
        # Compute the Z-score for this minute
        z_score = (avg_time - mean) / stdev

        if z_score > z_threshold:
            # This minute's average is unusually high
            severity = "CRITICAL" if z_score > 4 else "HIGH"

            anomalies.append(Anomaly(
                anomaly_type="statistical",
                severity=severity,
                source="nginx_access",
                timestamp=minute,
                description=(
                    f"Latency spike: avg response={avg_time:.3f}s "
                    f"(overall mean={mean:.3f}s, z-score={z_score:.1f})"
                ),
                evidence=[
                    f"Average response time at {minute} = {avg_time:.3f}s "
                    f"vs normal average of {mean:.3f}s"
                ],
            ))

    return anomalies


# ============================================================
# KEYWORD LISTS for Detector 3
# ============================================================

# These words, when found in a log message, ALWAYS indicate a critical problem.
# We keep them as a list so it is easy to add new keywords.
CRITICAL_KEYWORDS = [
    "OOMKilling",           # Kubernetes is killing a process due to OOM
    "Out of memory",        # Application or OS out of memory
    "oom killer",           # Linux kernel OOM killer triggered
    "FATAL",                # Fatal-level log entry
    "Deadlock",             # Database deadlock — transactions blocking each other
    "Connection limit reached",  # Database at max connections
    "no live upstreams",    # Nginx has no working backend servers
    "exceeded quota",       # Kubernetes pod quota exceeded — can't scale
    "CrashLoopBackOff",     # Pod is restarting in a crash loop
]

# These words indicate a serious (but not yet critical) problem.
HIGH_KEYWORDS = [
    "timeout",              # A request or query timed out
    "Connection refused",   # A service refused the connection
    "Back-off restarting",  # Kubernetes is retrying a failed container
    "Unhealthy",            # A pod failed its health check
    "pool exhausted",       # Connection pool is full
    "shared memory",        # Database ran out of shared memory
]


# ============================================================
# DETECTOR 3 — Keyword-Based
# ============================================================

def detect_keyword_anomalies(entries):
    """
    Scan every log entry for known critical or high-severity keywords.

    Parameters
    ----------
    entries : list[dict]  — all parsed log entries

    Returns
    -------
    list[Anomaly]

    Why use keyword detection?
    --------------------------
    Threshold and statistical detectors look at patterns across time.
    But some individual log messages are ALWAYS serious — they never appear
    during normal operation.  A single "OOMKilling" line is already a P1.

    We check CRITICAL_KEYWORDS first.
    The 'for...else' pattern:
        - 'break' exits the for loop early (we found a critical keyword)
        - The 'else' clause runs ONLY if we did NOT break
          → i.e. only if no critical keyword was found
        → then we check high-severity keywords
    This means each log entry produces at most ONE anomaly.
    """
    anomalies = []

    for entry in entries:
        # Convert message to lowercase so our keyword check is case-insensitive.
        # "OOMKilling" and "oomkilling" both match "oomkilling".lower()
        message_lower = entry["message"].lower()

        # Check CRITICAL keywords first
        for keyword in CRITICAL_KEYWORDS:
            if keyword.lower() in message_lower:
                anomalies.append(Anomaly(
                    anomaly_type="keyword",
                    severity="CRITICAL",
                    source=entry["source"],
                    timestamp=entry["timestamp"],
                    description=(
                        f"Critical keyword '{keyword}' found: "
                        f"{entry['message'][:100]}"
                    ),
                    evidence=[entry["message"]],
                ))
                break   # stop checking — one anomaly per entry is enough
                # 'break' also means the 'else' block below will NOT run

        else:
            # 'else' on a for loop: runs only if the loop finished WITHOUT break.
            # Meaning: we checked all CRITICAL_KEYWORDS and none matched.
            # Now check HIGH_KEYWORDS.
            for keyword in HIGH_KEYWORDS:
                if keyword.lower() in message_lower:
                    anomalies.append(Anomaly(
                        anomaly_type="keyword",
                        severity="HIGH",
                        source=entry["source"],
                        timestamp=entry["timestamp"],
                        description=(
                            f"High-severity keyword '{keyword}' found: "
                            f"{entry['message'][:100]}"
                        ),
                        evidence=[entry["message"]],
                    ))
                    break   # one anomaly per entry

    return anomalies


# ============================================================
# RUNNER — run_all_detectors
# ============================================================

def run_all_detectors(entries):
    """
    Run all three detectors and return a combined, sorted list.

    Parameters
    ----------
    entries : list[dict]  — all parsed log entries

    Returns
    -------
    list[Anomaly]
        All anomalies from all three detectors, sorted by timestamp.

    Why run all three?
    ------------------
    Each detector catches different categories of problem:
      Threshold   → catches error rate spikes
      Statistical → catches performance degradation
      Keyword     → catches critical known events
    Running all three gives us the broadest coverage.
    """
    
    threshold_anomalies = detect_threshold_anomalies(entries)
    statistical_anomalies = detect_statistical_anomalies(entries)
    keyword_anomalies     = detect_keyword_anomalies(entries)

    # Combine all three lists using + (list concatenation)
    all_anomalies = threshold_anomalies + statistical_anomalies + keyword_anomalies

    # Sort by timestamp so anomalies appear in chronological order
    all_anomalies.sort(key=lambda a: a.timestamp)

    return all_anomalies


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("=" * 55)
    print("STEP 3 — Anomaly Detection")
    print("=" * 55)

    raw_logs  = load_all_logs()
    entries   = parse_all_logs(raw_logs)

    anomalies = run_all_detectors(entries)

    print(f"\nTotal anomalies detected: {len(anomalies)}")
    print()

    # # Count anomalies by severity
    severity_counts = Counter(a.severity for a in anomalies)
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = severity_counts.get(sev, 0)   # .get(key, default) — safe dict access
        print(f"  {sev:10s}: {count}")

    print("\n--- Anomaly Detail ---")
    for a in anomalies:
        print(f"\n  [{a.timestamp}] [{a.severity:8s}] [{a.anomaly_type:12s}] [{a.source}]")
        print(f"    {a.description}")
        for ev in a.evidence[:2]:   # show up to 2 evidence lines
            print(f"    Evidence: {ev[:90]}")
