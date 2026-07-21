"""
============================================================
STEP 6 — Report Generator
============================================================

WHAT THIS FILE DOES
--------------------
Takes all the data produced by steps 1–5 and writes a
structured Markdown incident report to a file.

The report answers 6 key questions:
  1. WHAT happened?           (Executive Summary)
  2. HOW MUCH?                (Log Statistics)
  3. WHAT WAS DETECTED?       (Anomalies section)
  4. WHAT PATTERN EMERGED?    (Incident Patterns section)
  5. WHY DID IT HAPPEN?       (Root Cause Analysis section)
  6. WHAT DO WE DO?           (Recommendations)

The report is saved as Markdown (.md) in the reports/ folder.
Markdown is readable as plain text and renders on GitHub,
Confluence, Notion, Jira, and most documentation tools.

------------------------------------------------------------
REQUIREMENTS (read this before writing any code)
------------------------------------------------------------
You need to build TWO functions:

  Function 1 — build_report(entries, anomalies, patterns, rca_results=None)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Input  : everything produced by steps 1–5
  Output : one big string containing the full Markdown report
  Rules  :
    - Use datetime.datetime.now() for the timestamp at the top
    - Determine overall_severity = CRITICAL if any critical patterns,
      else HIGH if any high patterns, else MEDIUM
    - Build these sections (in order):
        Header (title, generated time, overall severity, counts)
        Executive Summary
        Log Statistics (table of level counts, table of source counts)
        Anomalies Detected (severity table + details)
        Incident Patterns (one subsection per pattern)
        Root Cause Analysis (LLM output OR manual rule-based analysis)
        Incident Timeline (hardcoded table for our fake log scenario)
        Recommendations (Immediate / Short-term / Long-term)
        Footer
    - Join all lines with "\n" and return the string

  Function 2 — save_report(content, filename=None)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Input  : the string from build_report(), optional filename
  Output : the full path where the file was saved
  Rules  :
    - If filename is None, auto-generate:
        "incident_report_YYYYMMDD_HHMMSS.md"
    - Create the reports/ directory if it doesn't exist (os.makedirs)
    - Write content to the file
    - Return the full file path

------------------------------------------------------------
ALGORITHM (plain English — try to code this yourself first)
------------------------------------------------------------

Step A  Write ensure_reports_dir():
    1.  Call os.makedirs(REPORTS_DIR, exist_ok=True)
        exist_ok=True means: don't error if the folder already exists

Step B  Write build_report(entries, anomalies, patterns, rca_results=None):
    1.  now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    2.  level_counts = Counter(e["level"] for e in entries)
    3.  critical_patterns = [p for p in patterns if p.severity == "CRITICAL"]
    4.  Determine overall_severity
    5.  lines = []  — build the report by appending to this list
    6.  Build each section by appending Markdown-formatted strings
        Markdown cheat sheet used here:
          # Title          → h1 heading
          ## Section       → h2 heading
          ### Subsection   → h3 heading
          **bold**         → bold text
          `code`           → inline code
          | col | col |    → table row
          |-----|-----|    → table separator
          - [ ] item       → checkbox (task)
          ---              → horizontal rule
    7.  Return "\n".join(lines)

Step C  Write save_report(content, filename=None):
    1.  ensure_reports_dir()
    2.  If filename is None:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"incident_report_{ts}.md"
    3.  filepath = os.path.join(REPORTS_DIR, filename)
    4.  with open(filepath, "w") as f:
            f.write(content)
    5.  Return filepath

------------------------------------------------------------
PYTHON CONCEPTS USED IN THIS FILE
------------------------------------------------------------
  datetime.datetime.now()     — current date and time
  .strftime()                 — format a datetime as a string
                                 %Y=4-digit year, %m=month, %d=day
                                 %H=hour, %M=minute, %S=second
  Counter                     — count occurrences of each value
  list comprehension          — [p for p in patterns if p.severity == "CRITICAL"]
  os.makedirs(exist_ok=True)  — create folder(s), don't error if already exists
  "\n".join(lines)            — join list of strings with newline between each

------------------------------------------------------------
HOW TO RUN
------------------------------------------------------------
  python src/step6_report_generator.py

  This runs WITHOUT an API key — no LLM call in this step.
  It uses rule-based analysis for the root cause section.

------------------------------------------------------------
"""

# ============================================================
# IMPORTS
# ============================================================

import os
import datetime
# datetime.datetime.now()  → current date and time as a datetime object
# .strftime("%Y-%m-%d %H:%M:%S")  → format it as "2024-01-15 09:22:00"
# We use this for the report timestamp and the auto-generated filename.

from collections import Counter
# Counter counts how many times each value appears in a list.
# Counter(["INFO", "ERROR", "INFO"]) → Counter({"INFO": 2, "ERROR": 1})
# Useful for the "Entries by log level" table in the report.

# Import from our earlier steps
from step1_load_logs import load_all_logs
from step2_parse_logs import parse_all_logs
from step3_anomaly_detection import run_all_detectors
from step4_pattern_analysis import analyse_patterns


# ============================================================
# CONSTANT — reports folder path
# ============================================================

# Build the path to the reports/ folder relative to this file.
# os.path.dirname(__file__)  → the folder containing this script (src/)
# os.path.join(..., "..", "reports")  → go up one level then into reports/
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")


# ============================================================
# HELPER — ensure_reports_dir
# ============================================================

def ensure_reports_dir():
    """
    Create the reports/ folder if it does not already exist.

    Why os.makedirs() instead of os.mkdir()?
    -----------------------------------------
    os.mkdir()  creates ONE directory — fails if parent folders are missing.
    os.makedirs() creates ALL missing parent directories too (like mkdir -p).

    exist_ok=True means: don't raise an error if the folder already exists.
    Without it, running the script a second time would crash here.
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)


# ============================================================
# FUNCTION 1 — build_report
# ============================================================

def build_report(entries, anomalies, patterns, rca_results=None):
    """
    Build the full incident report as a Markdown string.

    Parameters
    ----------
    entries     : list[dict]            — all parsed log entries (from step2)
    anomalies   : list[Anomaly]         — all detected anomalies (from step3)
    patterns    : list[IncidentPattern] — incident patterns (from step4)
    rca_results : list[dict] or None    — LLM RCA results (from step5), optional

    Returns
    -------
    str
        The complete Markdown report as one string.

    How we build the report
    -----------------------
    We build a list of strings (one per line or section),
    then join them at the end with newline characters.
    This is faster and cleaner than string concatenation (+=).
    """
    # Get the current time for the report header
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ---- Count log levels for the statistics table ----
    # Counter({level: count, ...})
    level_counts = Counter(e["level"] for e in entries)

    # ---- Determine overall incident severity ----
    # Look for the worst severity across all patterns.
    critical_patterns = [p for p in patterns if p.severity == "CRITICAL"]
    high_patterns     = [p for p in patterns if p.severity == "HIGH"]

    if critical_patterns:
        overall_severity = "CRITICAL"
    elif high_patterns:
        overall_severity = "HIGH"
    else:
        overall_severity = "MEDIUM"

    # ---- Start building the report ----
    lines = []   # each element is one line of the Markdown file

    # ==============================================================
    # SECTION: HEADER
    # ==============================================================
    # "# Title" creates a top-level heading in Markdown
    lines.append("# Incident Report — CloudWatch Log Analysis")
    lines.append("")   # blank line for spacing (Markdown needs these)
    lines.append(f"**Generated:** {now}")          # **text** = bold in Markdown
    lines.append(f"**Overall Severity:** {overall_severity}")
    lines.append(f"**Total Log Entries Analysed:** {len(entries)}")
    lines.append(f"**Total Anomalies Detected:** {len(anomalies)}")
    lines.append(f"**Incident Patterns:** {len(patterns)}")
    lines.append("")

    # ==============================================================
    # SECTION: EXECUTIVE SUMMARY
    # ==============================================================
    lines.append("---")   # "---" renders as a horizontal rule in Markdown
    lines.append("## 1. Executive Summary")
    lines.append("")

    if overall_severity == "CRITICAL":
        lines.append(
            "A **CRITICAL** incident was detected. Analysis of logs from "
            "application, Nginx, database, and Kubernetes sources reveals a "
            "cascading failure pattern beginning with database performance "
            "degradation and resulting in widespread 502 errors and pod restarts."
        )
    else:
        lines.append(
            f"Log analysis detected **{len(anomalies)}** anomalies across "
            f"{len(patterns)} incident pattern(s) with overall severity "
            f"**{overall_severity}**."
        )
    lines.append("")

    # ==============================================================
    # SECTION: LOG STATISTICS
    # ==============================================================
    lines.append("---")
    lines.append("## 2. Log Statistics")
    lines.append("")

    # Markdown table for log levels
    # Format: | Column1 | Column2 |
    #         |---------|---------|
    #         | Value1  | Value2  |
    lines.append("| Log Level | Count |")
    lines.append("|-----------|-------|")
    for level in ["INFO", "WARN", "WARNING", "ERROR", "FATAL", "CRITICAL", "CRIT", "NOTICE"]:
        count = level_counts.get(level, 0)   # .get returns 0 if level not in counter
        if count > 0:
            lines.append(f"| {level} | {count} |")
    lines.append("")

    # Markdown table for log sources
    source_counts = Counter(e["source"] for e in entries)
    lines.append("| Log Source | Entries |")
    lines.append("|------------|---------|")
    for source, count in sorted(source_counts.items()):   # sorted = alphabetical
        lines.append(f"| {source} | {count} |")
    lines.append("")

    # ==============================================================
    # SECTION: ANOMALIES
    # ==============================================================
    lines.append("---")
    lines.append("## 3. Anomalies Detected")
    lines.append("")
    lines.append(f"**Total:** {len(anomalies)} anomalies detected using three patterns:")
    lines.append("- **Threshold**: errors-per-minute exceeding the limit")
    lines.append("- **Statistical**: response times that are Z-score outliers")
    lines.append("- **Keyword**: known critical or high-severity keywords")
    lines.append("")

    # Severity breakdown table
    severity_counts = Counter(a.severity for a in anomalies)
    lines.append("| Severity | Count |")
    lines.append("|----------|-------|")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = severity_counts.get(sev, 0)
        if count > 0:
            lines.append(f"| {sev} | {count} |")
    lines.append("")

    # ==============================================================
    # SECTION: INCIDENT PATTERNS
    # ==============================================================
    lines.append("---")
    lines.append("## 4. Incident Patterns")
    lines.append("")

    for p in patterns:
        # "### " creates a level-3 heading (sub-subsection)
        lines.append(f"### {p.pattern_id} — {p.pattern_name}")
        lines.append(f"- **Severity:** {p.severity}")
        # Backticks around a value render as monospace/code font
        lines.append(f"- **Time Range:** `{p.start_time}` → `{p.end_time}`")
        lines.append(f"- **Sources Involved:** {', '.join(p.sources)}")
        lines.append(f"- **Anomaly Count:** {len(p.anomalies)}")
        lines.append("")
        lines.append("**Key Anomalies:**")
        for a in p.anomalies[:5]:   # show up to 5 anomalies
            lines.append(f"- `[{a.timestamp}]` [{a.severity}] {a.description[:100]}")
        if len(p.anomalies) > 5:
            # *(text)* renders as italic in Markdown
            lines.append(f"- *(and {len(p.anomalies) - 5} more)*")
        lines.append("")

    # ==============================================================
    # SECTION: ROOT CAUSE ANALYSIS
    # ==============================================================
    lines.append("---")
    lines.append("## 5. Root Cause Analysis")
    lines.append("")

    if rca_results:
        # LLM RCA is available — use it
        for result in rca_results:
            lines.append(f"### {result['pattern_id']} — LLM Analysis")
            lines.append("")
            lines.append(result["rca_text"])
            lines.append("")
    else:
        # No LLM results — explain why and provide rule-based analysis instead
        lines.append(
            "> *LLM-based root cause analysis was not run in this session.*\n"
            "> *To include it, set OPENAI_API_KEY and run step5_root_cause.py*"
        )
        lines.append("")
        lines.append("**Manual Analysis (based on log timeline):**")
        lines.append("")
        lines.append(
            "Based on the anomaly timeline across all log sources, "
            "the root cause chain is:"
        )
        lines.append("")
        # Numbered list: "1. Item" in Markdown
        lines.append("1. **09:18** — PostgreSQL autovacuum ran on the `orders` table, causing lock contention")
        lines.append("2. **09:19** — Lock contention caused slow queries (1200ms–4800ms) and connection buildup")
        lines.append("3. **09:20** — DB connection pool exhausted → application requests started timing out")
        lines.append("4. **09:20** — App memory exhausted waiting for DB connections → OOM kill")
        lines.append("5. **09:20** — All pods failed liveness probes → Kubernetes killed all pods")
        lines.append("6. **09:20** — Pod quota exceeded → HPA could not scale → 502 errors for all users")
        lines.append("7. **09:22** — DB recovered → app pods restarted → service restored")
        lines.append("")

    # ==============================================================
    # SECTION: TIMELINE
    # ==============================================================
    lines.append("---")
    lines.append("## 6. Incident Timeline")
    lines.append("")
    lines.append("| Time  | Event |")
    lines.append("|-------|-------|")
    lines.append("| 09:00 | Service operating normally |")
    lines.append("| 09:18 | Autovacuum starts on `orders` table |")
    lines.append("| 09:19 | Lock contention — slow queries begin |")
    lines.append("| 09:20 | DB connection pool exhausted (200/200) |")
    lines.append("| 09:20 | Application timeouts + OOM kill |")
    lines.append("| 09:20 | All pods fail liveness probe → restarted |")
    lines.append("| 09:20 | Pod quota exceeded → 502 errors for all users |")
    lines.append("| 09:21 | DB begins WAL replay / recovery |")
    lines.append("| 09:22 | DB accepts connections again |")
    lines.append("| 09:22 | Application pods restart successfully |")
    lines.append("| 09:30 | Full recovery confirmed |")
    lines.append("")

    # ==============================================================
    # SECTION: RECOMMENDATIONS
    # ==============================================================
    lines.append("---")
    lines.append("## 7. Recommendations")
    lines.append("")

    lines.append("### Immediate Actions (Do Right Now)")
    # "- [ ] item" renders as an unchecked checkbox in Markdown
    lines.append("- [ ] Increase pod quota in the `compute-resources` namespace quota")
    lines.append("- [ ] Add PgBouncer (connection pooling) between application and database")
    lines.append("- [ ] Reschedule autovacuum to run during low-traffic hours (02:00–04:00 UTC)")
    lines.append("- [ ] Add alert: DB connections > 80% of max_connections")
    lines.append("")

    lines.append("### Short-term (This Sprint)")
    lines.append("- [ ] Implement circuit breaker in application (fail fast, not pile up)")
    lines.append("- [ ] Add a database read replica to reduce primary DB load")
    lines.append("- [ ] Create a runbook for DB autovacuum-related incidents")
    lines.append("")

    lines.append("### Long-term (Next Quarter)")
    lines.append("- [ ] Migrate to full connection pooling architecture")
    lines.append("- [ ] Implement DB query timeout: `statement_timeout = 10s` in postgresql.conf")
    lines.append("- [ ] Add synthetic monitoring to detect latency before users do")
    lines.append("")

    # ==============================================================
    # FOOTER
    # ==============================================================
    lines.append("---")
    lines.append(
        "*This report was generated automatically by the CloudWatch Log Analyst Agent.*"
    )
    lines.append(f"*Analysis timestamp: {now}*")

    # Join all lines into one string with newline between each.
    # This is the complete Markdown document as a single string.
    return "\n".join(lines)


# ============================================================
# FUNCTION 2 — save_report
# ============================================================

def save_report(content, filename=None):
    """
    Save the report Markdown string to a file in the reports/ folder.

    Parameters
    ----------
    content  : str        — the full Markdown report from build_report()
    filename : str or None — optional filename; auto-generated if None

    Returns
    -------
    str
        The full absolute path of the saved file.

    Why save reports with timestamps in the filename?
    ------------------------------------------------
    If we always saved to "report.md", each run would overwrite the previous.
    A timestamped filename lets us keep a history of all reports:
      incident_report_20240115_092200.md
      incident_report_20240115_093500.md
    This is important for trend analysis and audit trails.
    """
    ensure_reports_dir()   # make sure the folder exists

    if filename is None:
        # Auto-generate a filename with the current timestamp.
        # strftime format codes:
        #   %Y = 4-digit year   (2024)
        #   %m = 2-digit month  (01)
        #   %d = 2-digit day    (15)
        #   %H = 2-digit hour   (09)
        #   %M = 2-digit minute (22)
        #   %S = 2-digit second (00)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"incident_report_{ts}.md"

    # Build the full path: REPORTS_DIR + "/" + filename
    filepath = os.path.join(REPORTS_DIR, filename)

    print("Value of filepath is as follows ", filepath)

    # Open the file in write mode ("w") and write the content.
    # "w" creates the file if it doesn't exist, overwrites if it does.
    # "with" ensures the file is closed even if an error occurs.
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath   # return the path so callers know where the file was saved


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("=" * 55)
    print("STEP 6 — Report Generator")
    print("=" * 55)

    # Run the full pipeline up to step 4 (no LLM needed for this step)
    raw_logs  = load_all_logs()
    entries   = parse_all_logs(raw_logs)
    anomalies = run_all_detectors(entries)
    patterns  = analyse_patterns(entries)

    # Build the report without LLM RCA (pass rca_results=None)
    report_content = build_report(
        entries=entries,
        anomalies=anomalies,
        patterns=patterns,
        rca_results=None,   # None = use rule-based analysis section
    )

    # Save the report to disk
    saved_path = save_report(report_content)

    print("Value of saved path is as follows - ", saved_path)

    print(f"\nReport saved to: {saved_path}")
    print(f"\nFirst 20 lines of report preview:")
    print("-" * 40)
    for line in report_content.split("\n")[:20]:
        print(line)
