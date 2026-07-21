"""
============================================================
STEP 7 — Full End-to-End Pipeline Agent
============================================================

WHAT THIS FILE DOES
--------------------
This is the PORTFOLIO PROJECT deliverable.

It wires together all 6 previous steps into one agent class
that you run with a single command.

The LogAnalystAgent class orchestrates:
  Step 1 → load log files
  Step 2 → parse into structured entries
  Step 3 → detect anomalies (3 patterns)
  Step 4 → correlate into incident patterns
  Step 5 → root cause analysis via LLM (optional)
  Step 6 → generate and save Markdown report

------------------------------------------------------------
REQUIREMENTS (read this before writing any code)
------------------------------------------------------------
You need to build ONE class: LogAnalystAgent

  __init__(self, use_llm=True)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Sets up the agent. Stores whether to use the LLM.
  Also checks if the API key is actually available.
  Initialises all state variables to None.

  step1_load(self)
  ~~~~~~~~~~~~~~~~~~
  Calls load_all_logs() and stores result in self.raw_logs.
  Prints progress.

  step2_parse(self)
  ~~~~~~~~~~~~~~~~~~
  Calls parse_all_logs(self.raw_logs) and stores result in self.entries.
  Prints how many entries were parsed.

  step3_detect(self)
  ~~~~~~~~~~~~~~~~~~~
  Calls run_all_detectors(self.entries) and stores in self.anomalies.
  Prints counts by severity.

  step4_correlate(self)
  ~~~~~~~~~~~~~~~~~~~~~~
  Calls analyse_patterns(self.entries) and stores in self.patterns.
  Prints each pattern name and severity.

  step5_rca(self)
  ~~~~~~~~~~~~~~~~
  If self.use_llm is True: calls run_root_cause_analysis(self.patterns)
  If self.use_llm is False: sets self.rca_results = None
  Prints progress message.

  step6_report(self)
  ~~~~~~~~~~~~~~~~~~~
  Calls build_report() with all the data collected so far.
  Calls save_report() to write it to disk.
  Stores the path in self.report_path.
  Prints where the file was saved.

  run(self)
  ~~~~~~~~~~
  Calls all 6 steps in order.
  Records start time at the beginning, calculates elapsed at the end.
  Prints a final summary (duration, counts, report path).
  Returns the report path.

------------------------------------------------------------
ALGORITHM (plain English — try to code this yourself first)
------------------------------------------------------------

Step A  Define the class:
    class LogAnalystAgent:

Step B  Write __init__(self, use_llm=True):
    1.  self.use_llm = use_llm AND RCA_AVAILABLE AND bool(os.getenv("OPENAI_API_KEY"))
        (all three must be True for LLM to be used)
    2.  If use_llm was True but self.use_llm is now False:
        print("[INFO] API key not found — running without LLM RCA."
    3.  Set all data attributes to None:
        self.raw_logs, self.entries, self.anomalies
        self.patterns, self.rca_results, self.report_path

Step C  Write each step method (step1 through step6):
    Each one should:
    a. Print "[N/6] Step name..."
    b. Call the function from the imported module
    c. Store the result in self.attribute_name
    d. Print a confirmation message with counts

Step D  Write run(self):
    1.  Print header
    2.  start_time = time.time()  ← records current time as a float (seconds)
    3.  Call self.step1_load()
    4.  Call self.step2_parse()
    5.  Call self.step3_detect()
    6.  Call self.step4_correlate()
    7.  Call self.step5_rca()
    8.  Call self.step6_report()
    9.  elapsed = time.time() - start_time  ← difference gives duration in seconds
    10. Print summary (elapsed, counts, report path)
    11. Return self.report_path

------------------------------------------------------------
KEY DESIGN DECISIONS
------------------------------------------------------------

1. Why use a CLASS instead of just calling functions?
   A class groups related data (self.entries, self.anomalies, etc.)
   and related behaviour (step1–step6, run) together.
   Without a class, you'd have to pass every variable to every function
   or use many global variables. The class is cleaner and easier to test.

2. Why store intermediate results in self?
   Each step depends on the previous step's output.
   Storing results in self.raw_logs, self.entries, etc. means:
   - Each step method is short and focused
   - You can run steps individually during debugging:
       agent.step1_load()     ← just load
       print(agent.raw_logs)  ← inspect the raw data
       agent.step2_parse()    ← then parse
       print(agent.entries[:3])  ← inspect a few entries
   This is called "inspect and continue" debugging.

3. Why use try/except for importing step5?
   step5 requires langchain-openai to be installed.
   If it is not installed (e.g. someone clones the repo and skips pip install),
   the import fails with an ImportError.
   We catch this with try/except so the rest of the pipeline still works.
   The agent then runs without LLM RCA — graceful degradation.

4. Why time.time() for duration?
   time.time() returns the current time as a float of seconds since 1970.
   Subtracting two time.time() values gives elapsed seconds.
   It is simpler than datetime arithmetic for measuring code execution time.

------------------------------------------------------------
PYTHON CONCEPTS USED IN THIS FILE
------------------------------------------------------------
  class            — groups related data and methods together
  __init__()       — constructor: runs when you create an instance
  self             — refers to the current instance of the class
  try/except       — catch and handle import errors gracefully
  time.time()      — current time in seconds (float)
  bool()           — convert a value to True or False
  os.getenv()      — read an environment variable

------------------------------------------------------------
HOW TO RUN
------------------------------------------------------------
  # Without LLM (works immediately, no API key needed):
  python src/step7_full_pipeline.py

  # With LLM root cause analysis:
  export OPENAI_API_KEY=sk-...
  python src/step7_full_pipeline.py

------------------------------------------------------------
"""

# ============================================================
# IMPORTS
# ============================================================

import os
import time
# time.time() returns current time in seconds since Jan 1, 1970 (Unix epoch).
# We use it to measure how long the pipeline takes to run.
# time.time() gives a float: e.g. 1705312920.45
# elapsed = time.time() - start_time  gives the number of seconds elapsed.

# ---- Import all the functions we built in steps 1–6 ----
from step1_load_logs         import load_all_logs
from step2_parse_logs        import parse_all_logs
from step3_anomaly_detection import run_all_detectors
from step4_pattern_analysis  import analyse_patterns
from step6_report_generator  import build_report, save_report


# ============================================================
# OPTIONAL IMPORT — step5 (LLM Root Cause Analysis)
# ============================================================
# We use try/except here because step5 requires langchain-openai.
# If that package is not installed, the import fails.
# With try/except, the pipeline still works — it just skips LLM RCA.
#
# try:   attempt to run the code inside
# except ImportError:  if an ImportError occurs, run this block instead
#
# RCA_AVAILABLE is a flag that tells __init__ whether step5 is usable.

try:
    from step5_root_cause import run_root_cause_analysis
    RCA_AVAILABLE = True    # step5 imported successfully
except ImportError:
    RCA_AVAILABLE = False   # step5 import failed — will run without LLM


# ============================================================
# CLASS — LogAnalystAgent
# ============================================================

class LogAnalystAgent:
    """
    End-to-end log analysis agent.

    This class orchestrates all six pipeline steps.
    Each step is a separate method so you can see clearly where
    one step ends and the next begins.

    Usage
    -----
    # Basic usage (no LLM):
    agent = LogAnalystAgent(use_llm=False)
    report_path = agent.run()

    # With LLM (needs OPENAI_API_KEY set):
    agent = LogAnalystAgent(use_llm=True)
    report_path = agent.run()

    # Debug a single step:
    agent = LogAnalystAgent(use_llm=False)
    agent.step1_load()
    print(agent.raw_logs["app.log"][:3])  # inspect first 3 lines
    agent.step2_parse()
    print(agent.entries[:2])              # inspect first 2 parsed entries
    """

    def __init__(self, use_llm=True):
        """
        Initialise the agent.

        Parameters
        ----------
        use_llm : bool
            If True AND OPENAI_API_KEY is set AND step5 imported OK:
            the agent will call the OpenAI API for root cause analysis.
            If any condition is False: skip LLM, use rule-based analysis.

        Why check three conditions?
        ---------------------------
        use_llm         — the caller's preference
        RCA_AVAILABLE   — step5 module imported without errors
        OPENAI_API_KEY  — the API key is set in the environment
        All three must be True to actually use the LLM.
        """
        # bool() converts a string to True (non-empty) or False (None / empty)
        # os.getenv("OPENAI_API_KEY") returns None if the key is not set.
        # bool(None) → False, bool("sk-...") → True
        self.use_llm = (
            use_llm
            and RCA_AVAILABLE
            and bool(os.getenv("OPENAI_API_KEY"))
        )

        # If the caller wanted LLM but it's not available, let them know.
        if use_llm and not self.use_llm:
            print("  [INFO] OPENAI_API_KEY not found — running without LLM RCA.")

        # Initialise all data attributes to None.
        # Each step method will populate these as it runs.
        # Storing data on self means all methods can access it without
        # passing it as arguments.
        self.raw_logs    = None   # populated by step1_load()
        self.entries     = None   # populated by step2_parse()
        self.anomalies   = None   # populated by step3_detect()
        self.patterns    = None   # populated by step4_correlate()
        self.rca_results = None   # populated by step5_rca() (or stays None)
        self.report_path = None   # populated by step6_report()

    # ----------------------------------------------------------
    def step1_load(self):
        """Step 1: Load all log files into self.raw_logs."""
        print("\n[1/6] Loading log files...")

        # Call the function from step1 and store the result.
        # self.raw_logs is now a dict: {"app.log": [lines], ...}
        self.raw_logs = load_all_logs()

        # Compute total line count across all files for the summary message.
        # sum(len(v) for v in self.raw_logs.values()) is a generator expression:
        # it loops over all value lists and sums their lengths.
        total_lines = sum(len(v) for v in self.raw_logs.values())
        print(f"      Loaded {len(self.raw_logs)} files, {total_lines} lines total.")

    # ----------------------------------------------------------
    def step2_parse(self):
        """Step 2: Parse raw lines into structured entry dicts."""
        print("\n[2/6] Parsing log entries...")

        # parse_all_logs() takes the dict from step1 and returns a list of dicts.
        self.entries = parse_all_logs(self.raw_logs)

        print(f"      Parsed {len(self.entries)} structured entries.")

    # ----------------------------------------------------------
    def step3_detect(self):
        """Step 3: Run anomaly detection on parsed entries."""
        print("\n[3/6] Detecting anomalies...")

        self.anomalies = run_all_detectors(self.entries)

        # Count by severity for the summary line
        from collections import Counter
        counts = Counter(a.severity for a in self.anomalies)
        print(
            f"      Detected {len(self.anomalies)} anomalies: "
            f"CRITICAL={counts.get('CRITICAL', 0)}, "
            f"HIGH={counts.get('HIGH', 0)}, "
            f"MEDIUM={counts.get('MEDIUM', 0)}"
        )

    # ----------------------------------------------------------
    def step4_correlate(self):
        """Step 4: Correlate anomalies into incident patterns."""
        print("\n[4/6] Correlating patterns...")

        self.patterns = analyse_patterns(self.entries)

        print(f"      Found {len(self.patterns)} incident pattern(s).")

        # Print a summary line for each pattern
        for p in self.patterns:
            print(f"        {p.pattern_id}: [{p.severity}] {p.pattern_name}")

    # ----------------------------------------------------------
    def step5_rca(self):
        """Step 5: Root cause analysis (LLM or rule-based)."""
        if self.use_llm:
            print("\n[5/6] Running LLM root cause analysis...")
            # Call step5's function — it returns a list of dicts
            self.rca_results = run_root_cause_analysis(self.patterns)
            print(f"      Completed RCA for {len(self.rca_results)} pattern(s).")
        else:
            print("\n[5/6] Skipping LLM RCA (no API key). Rule-based analysis will be used.")
            # rca_results stays None — build_report() handles this case
            self.rca_results = None

    # ----------------------------------------------------------
    def step6_report(self):
        """Step 6: Generate the report and save it to disk."""
        print("\n[6/6] Generating report...")

        # build_report() takes all our collected data and returns a Markdown string
        content = build_report(
            entries=self.entries,
            anomalies=self.anomalies,
            patterns=self.patterns,
            rca_results=self.rca_results,   # can be None — build_report handles it
        )

        # save_report() writes the string to a .md file and returns the path
        self.report_path = save_report(content)
        print(f"      Report saved: {self.report_path}")

    # ----------------------------------------------------------
    def run(self):
        """
        Run the complete pipeline from start to finish.

        Returns
        -------
        str
            Path to the generated report file.

        This is the ENTRY POINT — the one method you call to
        run the whole agent.  It calls steps 1–6 in order.
        """
        print("=" * 55)
        print("  CloudWatch Log Analyst Agent — Starting")
        print("=" * 55)

        # Record start time BEFORE any processing begins.
        # time.time() returns seconds since Unix epoch (Jan 1, 1970).
        start_time = time.time()

        # ---- Run all 6 steps in sequence ----
        # Each step reads from self (data from previous step)
        # and writes its output to self (for the next step).
        self.step1_load()
        self.step2_parse()
        self.step3_detect()
        self.step4_correlate()
        self.step5_rca()
        self.step6_report()

        # Calculate how long the whole pipeline took
        elapsed = time.time() - start_time   # difference in seconds

        # ---- Print final summary ----
        print("\n" + "=" * 55)
        print("  PIPELINE COMPLETE")
        print("=" * 55)
        print(f"  Duration:    {elapsed:.1f}s")    # .1f = 1 decimal place
        print(f"  Log lines:   {sum(len(v) for v in self.raw_logs.values())}")
        print(f"  Entries:     {len(self.entries)}")
        print(f"  Anomalies:   {len(self.anomalies)}")
        print(f"  Patterns:    {len(self.patterns)}")
        print(f"  Report:      {self.report_path}")
        print("=" * 55)

        return self.report_path


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    # Create an instance of the agent.
    # use_llm=True  → try to use OpenAI if OPENAI_API_KEY is set.
    #                 If no key found, automatically falls back.
    # use_llm=False → always skip LLM (useful for offline/testing).
    agent = LogAnalystAgent(use_llm=True)

    # Call run() to execute all 6 steps and produce the report.
    report_path = agent.run()

    # The report is now saved at report_path.
    # Open it in any Markdown viewer, or just read it as plain text.
