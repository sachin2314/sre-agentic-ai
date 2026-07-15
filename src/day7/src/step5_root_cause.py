"""
============================================================
STEP 5 — Root Cause Analysis using LangChain + LLM
============================================================

WHAT THIS FILE DOES
--------------------
Takes the incident patterns from Step 4 and asks an LLM
(Large Language Model like GPT-4) to analyse them and explain:
  1. ROOT CAUSE — what first went wrong?
  2. CASCADE    — how did that cause further failures?
  3. IMMEDIATE ACTIONS — what to do right now?
  4. PREVENTION — how to stop this happening again?

KEY DESIGN DECISION:
  The LLM does NOT see raw log files.
  It receives a structured text summary of the incident.
  This prevents token overflow and focuses the LLM on reasoning.

------------------------------------------------------------
REQUIREMENTS (read this before writing any code)
------------------------------------------------------------
You need to build THESE pieces:

  Helper — build_pattern_summary(pattern)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Input : one IncidentPattern object
  Output: a plain-English string summarising the incident
  Rules :
    - Build a multi-line string listing:
        Incident ID, Severity, Time range, Sources, Pattern name
        Then for each anomaly: [SEVERITY] [source] description + evidence
    - Return the full string (this becomes the LLM's input)

  Builder — build_rca_chain()
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Output: a LangChain chain (prompt | llm)
  Rules :
    - Create a ChatOpenAI LLM with temperature=0, model="gpt-4o-mini"
    - Create a ChatPromptTemplate with a system message (SRE role) and
      a human message template that includes {incident_summary}
    - Return prompt | llm  (the pipe operator creates a chain)

  Runner — analyse_root_cause(pattern)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Input : one IncidentPattern
  Output: str — the LLM's analysis text
  Rules :
    - Call build_pattern_summary() to get the text summary
    - Call build_rca_chain() to get the chain
    - Call chain.invoke({"incident_summary": summary})
    - Return response.content.strip()

  Runner — run_root_cause_analysis(patterns)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Input : list of IncidentPattern
  Output: list of dicts [{"pattern_id": ..., "rca_text": ...}, ...]
  Rules :
    - Only process patterns where severity is CRITICAL or HIGH
    - For each qualifying pattern: call analyse_root_cause()
    - Build a dict with pattern_id, severity, pattern, rca_text
    - Return the list of dicts

------------------------------------------------------------
ALGORITHM (plain English — try to code this yourself first)
------------------------------------------------------------

Step A  Write build_pattern_summary(pattern):
    1.  Create a list called 'lines'
    2.  Append: "Incident ID: {pattern.pattern_id}"
    3.  Append: "Severity:    {pattern.severity}"
    4.  Append: "Time range:  {pattern.start_time} → {pattern.end_time}"
    5.  Append: "Sources:     {', '.join(pattern.sources)}"
    6.  Append: "Pattern:     {pattern.pattern_name}"
    7.  Append: "" (blank line separator)
    8.  Append: "Anomalies detected:"
    9.  For each anomaly in pattern.anomalies:
        a. Append: "  - [{severity}] [{source}] {description}"
        b. If anomaly has evidence: append "    Evidence: {evidence[0][:120]}"
    10. Join lines with "\n" and return

Step B  Write build_rca_chain():
    1.  Create llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, ...)
    2.  Create a system_message string explaining the SRE role
    3.  Create prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human",  "Analyse ... \n\n{incident_summary}")
        ])
    4.  Return prompt | llm
        The | (pipe) operator chains two LangChain components together.
        When you call chain.invoke(), the input flows:
          prompt → formats the message → llm → returns a response

Step C  Write analyse_root_cause(pattern):
    1.  summary = build_pattern_summary(pattern)
    2.  chain   = build_rca_chain()
    3.  Print a progress message
    4.  response = chain.invoke({"incident_summary": summary})
    5.  Return response.content.strip()

Step D  Write run_root_cause_analysis(patterns):
    1.  results = []
    2.  For each pattern in patterns:
        a. If severity not in ("CRITICAL", "HIGH"):
           print "Skipping {id}..." → continue
        b. Else:
           rca_text = analyse_root_cause(pattern)
           results.append({
               "pattern_id": pattern.pattern_id,
               "severity":   pattern.severity,
               "pattern":    pattern,
               "rca_text":   rca_text,
           })
    3.  Return results

------------------------------------------------------------
HOW LangChain WORKS (the key concept)
------------------------------------------------------------
LangChain's core idea is the "chain": components connected with |

  prompt  |  llm

When you call chain.invoke({"incident_summary": "..."}):
  1. LangChain fills the {incident_summary} placeholder in the prompt
  2. The formatted prompt is sent to the LLM (OpenAI API)
  3. The LLM's response is returned as an AIMessage object
  4. response.content  gives you the text string

ChatPromptTemplate structures the messages correctly for a chat model:
  - "system" message: tells the LLM what role to play
  - "human"  message: the actual question / request

temperature=0 means "be deterministic and factual, not creative".
  0.0 = always the same output for the same input (good for RCA)
  1.0 = more random/creative output (good for writing)

------------------------------------------------------------
PYTHON CONCEPTS USED IN THIS FILE
------------------------------------------------------------
  langchain_openai.ChatOpenAI    — wrapper around OpenAI's API
  ChatPromptTemplate.from_messages — create a prompt with roles
  chain.invoke(dict)             — run the chain with input values
  response.content               — get the text from the LLM response
  os.getenv("KEY")               — read environment variables safely
  | operator (pipe)              — chain LangChain components together

------------------------------------------------------------
HOW TO RUN
------------------------------------------------------------
  # You need an OpenAI API key:
  export OPENAI_API_KEY=sk-...

  python src/step5_root_cause.py

  # If no API key is set, step7 will skip this step automatically.

------------------------------------------------------------
"""

# ============================================================
# IMPORTS
# ============================================================

import os
# os.getenv("OPENAI_API_KEY") reads environment variables.
# Environment variables are key-value pairs set in your shell.
# They let us store secrets (like API keys) outside the code.
# Set one with:  export OPENAI_API_KEY=sk-...

from langchain_openai import ChatOpenAI
# ChatOpenAI is LangChain's wrapper around the OpenAI API.
# It handles authentication, API calls, and response parsing.
# Install with:  pip install langchain-openai

from langchain.prompts import ChatPromptTemplate
# ChatPromptTemplate lets us define a structured prompt with:
#   - a "system" message (the role/persona for the LLM)
#   - a "human"  message (the actual question, with {placeholders})
# The {placeholders} are filled in when we call chain.invoke().

from step1_load_logs import load_all_logs
from step2_parse_logs import parse_all_logs
from step4_pattern_analysis import analyse_patterns, IncidentPattern


# ============================================================
# HELPER — build_pattern_summary
# ============================================================

def build_pattern_summary(pattern: IncidentPattern) -> str:
    """
    Convert an IncidentPattern into a plain-English text summary.

    Parameters
    ----------
    pattern : IncidentPattern
        One incident pattern from step4.

    Returns
    -------
    str
        A multi-line string the LLM can read and reason about.

    Why build a summary instead of passing raw logs?
    ------------------------------------------------
    LLMs have a "context window" — a limit on how much text they
    can process at once.  Our full log files might be 10,000 words.
    The summary is ~200 words and contains only the important facts.
    This is cheaper, faster, and produces better LLM output because
    the model isn't distracted by thousands of normal log lines.
    """
    lines = []   # list of strings we'll join at the end

    # Add the key facts about this incident
    lines.append(f"Incident ID:  {pattern.pattern_id}")
    lines.append(f"Severity:     {pattern.severity}")
    lines.append(f"Time range:   {pattern.start_time} → {pattern.end_time}")
    lines.append(f"Log sources:  {', '.join(pattern.sources)}")
    lines.append(f"Pattern name: {pattern.pattern_name}")
    lines.append("")   # blank separator line

    lines.append("Anomalies detected:")

    for a in pattern.anomalies:
        # Add a bullet point for each anomaly
        lines.append(f"  - [{a.severity}] [{a.source}] {a.description}")

        # Add one piece of evidence (the raw log line that triggered this anomaly)
        # We limit evidence to the first item and 120 chars to keep the summary short.
        for ev in a.evidence[:1]:
            lines.append(f"    Evidence: {ev[:120]}")

    # Join all lines into one big string, with newlines between them
    return "\n".join(lines)


# ============================================================
# BUILDER — build_rca_chain
# ============================================================

def build_rca_chain():
    """
    Build a LangChain chain for Root Cause Analysis.

    Returns
    -------
    Runnable
        A LangChain chain:  prompt_template | llm

    When you call chain.invoke({"incident_summary": "..."}):
      1. The prompt template fills in the placeholder with your summary
      2. The formatted messages are sent to the OpenAI API
      3. The API returns an AIMessage with the LLM's response
      4. You access the text via response.content

    Why temperature=0?
    ------------------
    temperature controls randomness in the LLM's output.
    0 = deterministic (same input → same output, factual)
    1 = creative (same input → different outputs each time)
    For root cause analysis we want consistent, factual reasoning → use 0.
    """

    # Create the LLM client.
    # gpt-4o-mini is a good balance of quality and cost for this task.
    # os.getenv() reads the OPENAI_API_KEY environment variable.
    # If not set, it returns None, and OpenAI will raise an authentication error.
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )

    # The system message defines the LLM's persona and output format.
    # It runs once at the start of the conversation.
    system_message = """You are a senior Site Reliability Engineer (SRE).
You analyse incident data from production systems.
Your job is to:
1. Identify the ROOT CAUSE of the incident (the first thing that went wrong).
2. Explain the CASCADE (how that root cause caused other failures).
3. Provide 3-5 IMMEDIATE ACTION items to resolve the incident.
4. Suggest 2-3 LONG-TERM PREVENTION measures.

Be specific, concise, and use SRE/DevOps terminology.
Format your response clearly with the headings:
Root Cause, Cascade, Immediate Actions, Prevention."""

    # ChatPromptTemplate.from_messages() takes a list of (role, content) tuples.
    # "system" → sets the LLM's role/persona
    # "human"  → the user's question, with {incident_summary} as a placeholder
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human",
         "Analyse the following incident data and provide root cause analysis:"
         "\n\n{incident_summary}"),
    ])

    # The | (pipe) operator creates a chain: prompt → llm
    # When invoked, data flows left to right:
    #   1. prompt receives {"incident_summary": "..."} and formats the messages
    #   2. llm receives the formatted messages and returns an AIMessage
    chain = prompt | llm

    return chain


# ============================================================
# RUNNER — analyse_root_cause
# ============================================================

def analyse_root_cause(pattern: IncidentPattern) -> str:
    """
    Run root cause analysis on one incident pattern.

    Parameters
    ----------
    pattern : IncidentPattern

    Returns
    -------
    str
        The LLM's root cause analysis as plain text.
    """
    # Step 1: Build the structured summary from the pattern
    summary = build_pattern_summary(pattern)

    # Step 2: Get the LangChain chain
    chain = build_rca_chain()

    # Print progress so the user knows an API call is happening
    print(f"\n  Querying LLM for {pattern.pattern_id}...")

    # Step 3: Invoke the chain.
    # chain.invoke() sends the prompt to the LLM and waits for the response.
    # The dict argument fills in the {incident_summary} placeholder.
    response = chain.invoke({"incident_summary": summary})

    # response is an AIMessage object.
    # response.content is the actual text the LLM generated.
    # .strip() removes any leading/trailing whitespace.
    return response.content.strip()


# ============================================================
# RUNNER — run_root_cause_analysis
# ============================================================

def run_root_cause_analysis(patterns):
    """
    Run RCA on any CRITICAL or HIGH severity pattern.

    Parameters
    ----------
    patterns : list[IncidentPattern]
        Output from analyse_patterns() in step4.

    Returns
    -------
    list[dict]
        Each dict contains:
          "pattern_id" : str           — e.g. "INC-001"
          "severity"   : str           — "CRITICAL" or "HIGH"
          "pattern"    : IncidentPattern — the original pattern object
          "rca_text"   : str           — the LLM's analysis text

    Why only CRITICAL/HIGH?
    -----------------------
    LLM API calls cost money and take time.
    We only spend resources on patterns that need human attention.
    MEDIUM/LOW patterns are included in the report but without LLM analysis.
    """
    results = []

    for pattern in patterns:
        if pattern.severity in ("CRITICAL", "HIGH"):
            # This pattern is serious enough to warrant LLM analysis
            rca_text = analyse_root_cause(pattern)
            results.append({
                "pattern_id": pattern.pattern_id,
                "severity":   pattern.severity,
                "pattern":    pattern,
                "rca_text":   rca_text,
            })
        else:
            # Skip lower severity patterns
            print(f"  Skipping {pattern.pattern_id} (severity={pattern.severity})")

    return results


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("=" * 55)
    print("STEP 5 — Root Cause Analysis")
    print("=" * 55)

    # Check for API key before doing anything.
    # Fail fast with a clear message rather than a confusing API error.
    if not os.getenv("OPENAI_API_KEY"):
        print("\n[ERROR] OPENAI_API_KEY is not set.")
        print("  Set it in your terminal with:")
        print("    export OPENAI_API_KEY=sk-...")
        print("\n  NOTE: step7_full_pipeline.py will still work without")
        print("  an API key — it uses rule-based analysis instead.")
        exit(1)   # exit with error code 1 (non-zero = failure)

    # Load and parse logs
    raw_logs = load_all_logs()
    entries  = parse_all_logs(raw_logs)

    # Find incident patterns
    patterns = analyse_patterns(entries)
    print(f"\nFound {len(patterns)} incident pattern(s).")
    print("Running root cause analysis on CRITICAL/HIGH patterns...\n")

    # Run RCA
    rca_results = run_root_cause_analysis(patterns)

    # Print results
    for result in rca_results:
        print(f"\n{'=' * 55}")
        print(f"  RCA for {result['pattern_id']}  [{result['severity']}]")
        print(f"{'=' * 55}")
        print(result["rca_text"])
