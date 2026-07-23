"""
=============================================================================
FILE: src/agent/react_agent.py
COURSE: AI Agentic SRE - Day 8: Deep Dive — Agent Architectures
TOPIC:  ReAct Agent — Deep Dive Implementation
=============================================================================

PURPOSE:
  Implements the ReAct (Reason + Act) agent for EKS pod investigation.
  This is the PRIMARY deliverable for Day 8.

  Day 6 vs Day 8 ReAct — KEY DIFFERENCES:
  ┌─────────────────────┬──────────────────────────┬──────────────────────────┐
  │ Aspect              │ Day 6                     │ Day 8                    │
  ├─────────────────────┼──────────────────────────┼──────────────────────────┤
  │ Depth               │ Introduced ReAct concept  │ Deep dive into internals │
  │ Tools               │ 1 tool (log reader)       │ 3 tools (pod+events+node)│
  │ Self-evaluation     │ Hallucination guardrails  │ Full self-reflection loop│
  │ Architecture        │ ReAct only                │ ReAct + Plan-and-Execute │
  │ Failure modes       │ Not covered               │ "Why agents fail" section│
  │ Domain              │ CloudWatch (AWS)          │ EKS pod failures (K8s)   │
  │ Output              │ Text summary              │ Structured + self-scored │
  └─────────────────────┴──────────────────────────┴──────────────────────────┘

REACT PATTERN DEEP DIVE:
  The ReAct loop is:
    1. THOUGHT:      LLM reasons about what to do next
    2. ACTION:       LLM decides which tool to call
    3. ACTION INPUT: LLM provides the tool arguments
    4. OBSERVATION:  Tool runs → result returned to LLM
    5. Repeat until LLM decides it has enough info for FINAL ANSWER

  Key insight: The LLM never executes code. It only REASONS about which
  tool to call. The framework executes the tool and feeds results back.
  This is the Reason-Act separation that makes agents reliable.

ALGORITHM:
  1. Define tools (read_pod_logs, read_k8s_events, read_node_metrics)
  2. Build ReAct prompt with SRE-specific system instructions
  3. Create agent with create_react_agent(llm, tools, prompt)
  4. Wrap in AgentExecutor (handles the Thought/Action/Observation loop)
  5. Run agent with investigation task
  6. Optionally wrap with SelfReflectingAgent for quality assurance

REQUIREMENTS (pip install):
  langchain>=0.2.0
  langchain-core>=0.2.0
  langchain-aws>=0.1.0
  pydantic>=2.0.0

=============================================================================
"""

import json
from datetime import datetime

from langchain_classic.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate

from src.tools.pod_log_reader import read_pod_logs, list_available_pods
from src.tools.k8s_event_reader import read_k8s_events, read_node_metrics
from src.agent.self_reflection import SelfReflectingAgent
from src.utils.bedrock_client import get_llm
from src.utils.app_logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# REACT PROMPT TEMPLATE
#
# This is the MOST IMPORTANT part of the agent.
# The prompt DEFINES the agent's behaviour:
#   - What reasoning style it uses (step-by-step SRE methodology)
#   - When it decides it has enough info (completeness criteria)
#   - How it formats its final output (structured report)
#
# PROMPT ANATOMY:
#   {tools}      → injected by LangChain: list of tool descriptions
#   {tool_names} → injected by LangChain: comma-separated tool names
#   {input}      → the user's task/question
#   {agent_scratchpad} → the running Thought/Action/Observation history
# ---------------------------------------------------------------------------
REACT_PROMPT_TEMPLATE = """You are an expert SRE (Site Reliability Engineer) AI Agent 
specialising in Kubernetes and EKS incident investigation.

Your investigation methodology follows this EXACT sequence:
  Step 1: List available pods (always do this first to confirm what's available)
  Step 2: Read pod logs for the failing pod
  Step 3: Read Kubernetes events for the namespace and pod
  Step 4: Read node metrics if OOMKilled or node pressure is suspected
  Step 5: Synthesise root cause from ALL evidence
  Step 6: Provide SPECIFIC, ACTIONABLE recommendations

SRE INVESTIGATION RULES:
  - NEVER skip reading K8s events after pod logs — events give the cluster view
  - ALWAYS check node metrics when OOMKilled is detected
  - ALWAYS provide specific values in recommendations (e.g., "increase to 1Gi" not "increase memory")
  - ALWAYS construct a timeline showing WHEN each event happened
  - Reference runbooks by name when available (e.g., RB-K8S-002-oomkilled.md)

TOOLS AVAILABLE:
{tools}

OUTPUT FORMAT for Final Answer — use EXACTLY this structure:
## 🔴 INCIDENT SUMMARY
[2-3 sentence executive summary]

## ⏱️ TIMELINE OF EVENTS  
[Chronological list of key events with timestamps]

## 🔍 ROOT CAUSE ANALYSIS
[Specific root cause with evidence from logs]

## ⚠️ ANOMALIES DETECTED
[List each anomaly with type, time, evidence]

## 🔧 RECOMMENDATIONS
[Numbered list of SPECIFIC, ACTIONABLE items]

## 📘 RUNBOOK REFERENCE
[Reference to applicable runbook file]

# ---------------------------------------------------------------------------
# FIX (duplicate-report bug): without this branch, every reflection follow-up
# re-ran the FULL format above from scratch — same Timeline/Root Cause/
# Recommendations restated near-verbatim each time. This tells the agent to
# emit only the delta when it's answering a follow-up question.
# ---------------------------------------------------------------------------
IF THE QUESTION BEGINS WITH "FOLLOW-UP INVESTIGATION REQUIRED":
  Do NOT repeat the Incident Summary, Timeline, Root Cause, Anomalies,
  Recommendations, or Runbook Reference sections you already produced.
  Your Final Answer must contain ONLY:

  ## 🔄 SUPPLEMENTAL FINDINGS
  [Address ONLY the specific missing items named in the Question — nothing else]

---
Use the following format throughout your investigation:

Question: {input}
Thought: [reason about what to do next]
Action: [one of: {tool_names}]
Action Input: [tool input as a simple string or JSON]
Observation: [tool output]
... (repeat Thought/Action/Observation as needed)
Thought: I now have sufficient information for a complete root cause analysis.
Final Answer: [your complete investigation report following the OUTPUT FORMAT above]

Begin!

Question: {input}
Thought: {agent_scratchpad}"""


def build_react_agent(enable_reflection: bool = True) -> tuple:
    """
    Builds the ReAct agent with all tools and optional self-reflection.

    ALGORITHM:
      1. Initialise the LLM (Claude Haiku via Bedrock)
      2. Assemble the tool list
      3. Create the PromptTemplate (LangChain formatting)
      4. Call create_react_agent() → returns Runnable agent
      5. Wrap in AgentExecutor → handles the loop
      6. Optionally wrap in SelfReflectingAgent

    Args:
        enable_reflection: If True, wraps agent with self-reflection loop
                          Set False for faster runs during development

    Returns:
        tuple: (agent_executor, reflecting_agent_or_None)
    """
    logger.info("Building ReAct agent — reflection=%s", enable_reflection)

    # -----------------------------------------------------------------------
    # STEP 1: Get the LLM
    # -----------------------------------------------------------------------
    llm = get_llm()
    logger.info("LLM initialised: eu.anthropic.claude-haiku-4-5-20251001-v1:0")

    # -----------------------------------------------------------------------
    # STEP 2: Tool list — only 2 PRIMARY tools as per Day 8 spec
    #         (list_available_pods + read_node_metrics are bonus tools)
    # -----------------------------------------------------------------------
    tools = [
        list_available_pods,    # Day 8: Tool 0 (helper)
        read_pod_logs,          # Day 8: Tool 1 — PRIMARY
        read_k8s_events,        # Day 8: Tool 2 — PRIMARY
        read_node_metrics,      # Day 8: Tool 3 (bonus for node pressure)
    ]

    logger.info("Tools registered: %s", [t.name for t in tools])

    # -----------------------------------------------------------------------
    # STEP 3: Build the prompt
    # LangChain's PromptTemplate handles the variable injection
    # -----------------------------------------------------------------------
    prompt = PromptTemplate.from_template(REACT_PROMPT_TEMPLATE)

    # -----------------------------------------------------------------------
    # STEP 4: Create the ReAct agent
    # create_react_agent produces a Runnable that knows how to:
    #   - Format the prompt with tools and input
    #   - Parse LLM output to extract Action and Action Input
    #   - Continue the loop until "Final Answer:" is produced
    # -----------------------------------------------------------------------
    react_agent = create_react_agent(
        llm=llm,
        tools=tools,
        prompt=prompt,
    )

    # -----------------------------------------------------------------------
    # STEP 5: Wrap in AgentExecutor
    # AgentExecutor is the "runner" — it:
    #   - Calls the agent's __call__ method
    #   - Dispatches tool calls to the right function
    #   - Feeds tool output back as Observation
    #   - Enforces max_iterations to prevent infinite loops
    # -----------------------------------------------------------------------
    agent_executor = AgentExecutor(
        agent=react_agent,
        tools=tools,
        verbose=True,       # Prints each Thought/Action/Observation step
        max_iterations=15,  # Safety: stop after 15 iterations (prevents runaway)
        handle_parsing_errors=True,  # Don't crash on LLM output format errors
        return_intermediate_steps=True,  # Keep all steps for debugging
    )

    logger.info("AgentExecutor created — max_iterations=15")

    # -----------------------------------------------------------------------
    # STEP 6: Optionally wrap with self-reflection
    # -----------------------------------------------------------------------
    reflecting_agent = None
    if enable_reflection:
        def agent_fn(task: str) -> str:
            """Adapter function: AgentExecutor expects dict input, returns dict output."""
            result = agent_executor.invoke({"input": task})
            return result.get("output", str(result))

        reflecting_agent = SelfReflectingAgent(
            agent_fn=agent_fn,
            max_reflections=2,
        )
        logger.info("SelfReflectingAgent wrapper created — max_reflections=2")

    return agent_executor, reflecting_agent


def run_react_investigation(pod_name: str,
                             namespace: str = "production",
                             enable_reflection: bool = True) -> dict:
    """
    Main entry point for ReAct-based EKS pod investigation.

    Args:
        pod_name:          Pod to investigate e.g. "web-service-7d8b9c"
        namespace:         K8s namespace e.g. "production"
        enable_reflection: Enable self-reflection quality check

    Returns:
        dict with:
            output:           Final investigation report text
            mode:             "REACT"
            reflection_score: Completeness score if reflection enabled
            metadata:         Timing and metadata
    """
    start_time = datetime.now()

    task = (
        f"Investigate the EKS pod failure for pod '{pod_name}' "
        f"in namespace '{namespace}'. "
        f"Determine the root cause, timeline of events, and provide "
        f"specific actionable recommendations to prevent recurrence."
    )

    logger.info("=" * 60)
    logger.info("Starting ReAct Investigation")
    logger.info("Pod: %s | Namespace: %s", pod_name, namespace)
    logger.info("=" * 60)

    agent_executor, reflecting_agent = build_react_agent(enable_reflection)

    # -----------------------------------------------------------------------
    # Run with or without reflection
    # -----------------------------------------------------------------------
    if enable_reflection and reflecting_agent:
        logger.info("Running with self-reflection enabled")
        reflection_output = reflecting_agent.run(task)

        final_output     = reflection_output["final_output"]
        reflection_score = reflection_output["reflection_score"]
        iterations       = reflection_output["iterations"]

    else:
        logger.info("Running without self-reflection")
        result = agent_executor.invoke({"input": task})

        final_output     = result.get("output", "")
        reflection_score = None
        iterations       = 1

    end_time  = datetime.now()
    duration  = (end_time - start_time).total_seconds()

    logger.info("Investigation complete — duration=%.1fs score=%s", duration, reflection_score)

    return {
        "output":           final_output,
        "mode":             "REACT",
        "reflection_score": reflection_score,
        "metadata": {
            "pod_name":       pod_name,
            "namespace":      namespace,
            "started_at":     start_time.isoformat(),
            "completed_at":   end_time.isoformat(),
            "duration_secs":  round(duration, 1),
            "iterations":     iterations,
            "reflection":     enable_reflection,
        }
    }
