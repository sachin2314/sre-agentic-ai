"""
============================================================
STEP 5 — Root Cause Analysis using LangChain + AWS Bedrock
============================================================

WHAT THIS FILE DOES
--------------------
Takes the incident patterns from Step 4 and asks an LLM
(Claude via AWS Bedrock) to analyse them and explain:
  1. ROOT CAUSE — what first went wrong?
  2. CASCADE    — how did that cause further failures?
  3. IMMEDIATE ACTIONS — what to do right now?
  4. PREVENTION — how to stop this happening again?

KEY DESIGN DECISION:
  The LLM does NOT see raw log files.
  It receives a structured text summary of the incident.
  This prevents token overflow and focuses the LLM on reasoning.

------------------------------------------------------------
REQUIREMENTS
------------------------------------------------------------
  pip install langchain-aws boto3

  AWS credentials must be configured via one of:
    - Environment variables:
        export AWS_ACCESS_KEY_ID=...
        export AWS_SECRET_ACCESS_KEY=...
        export AWS_DEFAULT_REGION=us-east-1
    - AWS CLI:  aws configure
    - IAM role attached to the compute instance

  The IAM principal needs the bedrock:InvokeModel permission
  on the model ARN you choose.

------------------------------------------------------------
MODEL SELECTION
------------------------------------------------------------
  Change BEDROCK_MODEL_ID to any model you have access to:

    anthropic.claude-3-haiku-20240307-v1:0    ← fast / cheap
    anthropic.claude-3-sonnet-20240229-v1:0   ← balanced
    anthropic.claude-3-opus-20240229-v1:0     ← most capable
    amazon.titan-text-express-v1              ← Amazon native

  You must first enable the model in the AWS Console:
    Bedrock → Model access → Request access

------------------------------------------------------------
"""

# ============================================================
# IMPORTS
# ============================================================

import sys
import os
from dotenv import load_dotenv
import boto3

sys.stdout.reconfigure(encoding='utf-8')
from langchain_core.prompts import ChatPromptTemplate

from langchain_aws import ChatBedrockConverse
# ChatBedrock is LangChain's wrapper around Amazon Bedrock's
# Converse / InvokeModel API.
# Install with:  pip install langchain-aws

#from langchain.prompts import ChatPromptTemplate

from step1_load_logs import load_all_logs
from step2_parse_logs import parse_all_logs
from step4_pattern_analysis import analyse_patterns, IncidentPattern


# ============================================================
# CONFIGURATION
# ============================================================

# The Bedrock model ID to use.  Change this to match the model
# you have enabled in your AWS account's Bedrock console.
#BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"



load_dotenv()

# AWS region where Bedrock is available for the chosen model.
# Bedrock is not available in every region — us-east-1 and
# us-west-2 have the broadest model coverage.
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID")

# model = ChatBedrockConverse(
#         model=os.getenv("BEDROCK_MODEL_ID"),
#         region_name=os.getenv("AWS_REGION")
#     )


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
    lines = []


    lines.append(f"Incident ID:  {pattern.pattern_id}")
    lines.append(f"Severity:     {pattern.severity}")
    lines.append(f"Time range:   {pattern.start_time} → {pattern.end_time}")
    lines.append(f"Log sources:  {', '.join(pattern.sources)}")
    lines.append(f"Pattern name: {pattern.pattern_name}")
    lines.append("")   # blank separator line

    lines.append("Anomalies detected:")

    for a in pattern.anomalies:
        lines.append(f"  - [{a.severity}] [{a.source}] {a.description}")

        # One piece of evidence per anomaly, capped at 120 chars
        for ev in a.evidence[:1]:
            lines.append(f"    Evidence: {ev[:120]}")

    return "\n".join(lines)


# ============================================================
# BUILDER — build_rca_chain
# ============================================================

def build_rca_chain():
    """
    Build a LangChain chain for Root Cause Analysis backed by AWS Bedrock.

    Returns
    -------
    Runnable
        A LangChain chain:  prompt_template | llm

    When you call chain.invoke({"incident_summary": "..."}):
      1. The prompt template fills in the placeholder with your summary
      2. The formatted messages are sent to the Bedrock API via boto3
      3. The API returns an AIMessage with the model's response
      4. You access the text via response.content

    Why temperature=0?
    ------------------
    0 = deterministic (same input → same output, factual)
    1 = creative (more varied outputs)
    For root cause analysis we want consistent, factual reasoning → use 0.
    """

    # boto3 client for Bedrock.
    # ChatBedrock accepts an existing client so you can control the
    # region and credential chain explicitly rather than relying on
    # whatever boto3 picks up from the environment.
    bedrock_client = boto3.client(
        service_name="bedrock-runtime",
        region_name=AWS_REGION,
    )

    # ChatBedrock mirrors the ChatOpenAI interface, so the rest of
    # the chain code is identical.
    llm = ChatBedrockConverse(
        model=os.getenv("BEDROCK_MODEL_ID"),
        region_name=os.getenv("AWS_REGION"),
        # model_id=BEDROCK_MODEL_ID,
        client=bedrock_client,
        model_kwargs={"temperature": 0},
        # max_tokens can be set here too, e.g. max_tokens=2048
    )



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

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human",
         "Analyse the following incident data and provide root cause analysis:"
         "\n\n{incident_summary}"),
    ])

    # prompt | llm  — the pipe chains the two components together
    return prompt | llm


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
    summary  = build_pattern_summary(pattern)
    chain    = build_rca_chain()

    print(f"\n  Querying Bedrock ({BEDROCK_MODEL_ID}) for {pattern.pattern_id}...")

    response = chain.invoke({"incident_summary": summary})
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
          "pattern_id" : str            — e.g. "INC-001"
          "severity"   : str            — "CRITICAL" or "HIGH"
          "pattern"    : IncidentPattern — the original pattern object
          "rca_text"   : str            — the LLM's analysis text

    Why only CRITICAL/HIGH?
    -----------------------
    API calls cost money and take time.
    We only spend resources on patterns that need human attention.
    MEDIUM/LOW patterns are included in the report but without LLM analysis.
    """
    results = []

    for pattern in patterns:
        if pattern.severity in ("CRITICAL", "HIGH"):
            rca_text = analyse_root_cause(pattern)
            results.append({
                "pattern_id": pattern.pattern_id,
                "severity":   pattern.severity,
                "pattern":    pattern,
                "rca_text":   rca_text,
            })
        else:
            print(f"  Skipping {pattern.pattern_id} (severity={pattern.severity})")

    return results


# ============================================================
# CREDENTIAL CHECK
# ============================================================

def _check_aws_credentials():
    """
    Verify AWS credentials are available before making API calls.
    Fails fast with a helpful message rather than a cryptic boto3 error.
    """
    try:
        # STS GetCallerIdentity is a free, read-only call that works
        # with any valid AWS credential — the cheapest way to verify auth.
        sts = boto3.client("sts", region_name=AWS_REGION)
        identity = sts.get_caller_identity()
        print(f"  AWS identity: {identity['Arn']}")
        return True
    except Exception as e:
        print(f"\n[ERROR] AWS credentials not found or invalid: {e}")
        print("  Configure credentials via one of:")
        print("    export AWS_ACCESS_KEY_ID=...")
        print("    export AWS_SECRET_ACCESS_KEY=...")
        print("    export AWS_DEFAULT_REGION=us-east-1")
        print("  Or run:  aws configure")
        return False


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("=" * 55)
    print("STEP 5 — Root Cause Analysis (AWS Bedrock)")
    print("=" * 55)
    print(f"\n  Model:  {BEDROCK_MODEL_ID}")
    print(f"  Region: {AWS_REGION}")

    if not _check_aws_credentials():
        exit(1)

    raw_logs = load_all_logs()
    entries  = parse_all_logs(raw_logs)
    patterns = analyse_patterns(entries)

    print(f"\nFound {len(patterns)} incident pattern(s).")
    print("Running root cause analysis on CRITICAL/HIGH patterns...\n")

    rca_results = run_root_cause_analysis(patterns)

    for result in rca_results:
        print(f"\n{'=' * 55}")
        print(f"  RCA for {result['pattern_id']}  [{result['severity']}]")
        print(f"{'=' * 55}")
        print(result["rca_text"])