"""
=============================================================================
FILE: src/agent/plan_and_execute_agent.py
COURSE: AI Agentic SRE - Day 8: Deep Dive — Agent Architectures
TOPIC:  Plan-and-Execute Agent — KEY Day 8 addition (not in Day 6)
=============================================================================

PURPOSE:
  Implements the Plan-and-Execute architecture for EKS investigation.
  This is COMPLETELY NEW in Day 8 — Day 6 only had basic ReAct.

WHY PLAN-AND-EXECUTE EXISTS:
  Problem with pure ReAct for complex tasks:
    → ReAct is "reactive" — each step only looks one step ahead
    → Complex investigations need multi-step awareness
    → "If I find OOMKilled, I ALSO need to check node pressure"
    → ReAct may miss this dependency without upfront planning

  Solution: Separate PLANNER from EXECUTOR
    PLANNER:  "Here are all the steps I need to take, in order"
              (runs ONCE at the start — uses the LLM's broad knowledge)
    EXECUTOR: "Execute step 3: call read_k8s_events with these args"
              (runs for each step — uses tools to get real data)

  Benefit: The plan provides a "contract" — even if individual steps
  fail or produce unexpected results, the overall structure remains.

ARCHITECTURE DIAGRAM:
  ┌─────────────────────────────────────────────────────────────┐
  │                 PLAN-AND-EXECUTE AGENT                      │
  │                                                             │
  │  Input: "Investigate pod web-service-7d8b9c"               │
  │         ↓                                                   │
  │  ┌──────────────────────┐                                   │
  │  │   PLANNER (LLM)      │ → Creates structured plan        │
  │  │   - Knows the domain │   with N steps                   │
  │  │   - No tools needed  │                                   │
  │  └──────────────────────┘                                   │
  │         ↓ Plan (list of steps)                              │
  │  ┌──────────────────────┐                                   │
  │  │  EXECUTOR (ReAct)    │ → Executes each step             │
  │  │  - Has access to     │   with tools                     │
  │  │    all tools         │                                   │
  │  └──────────────────────┘                                   │
  │    ↓Step1  ↓Step2  ↓Step3  ↓Step4  ↓Step5                  │
  │   [tool]  [tool]  [tool]  [LLM]   [tool]                   │
  │         ↓                                                   │
  │  ┌──────────────────────┐                                   │
  │  │  SYNTHESISER (LLM)   │ → Combines all step results      │
  │  │  - No tools needed   │   into final report              │
  │  └──────────────────────┘                                   │
  └─────────────────────────────────────────────────────────────┘

ALGORITHM:
  Phase 1 — PLANNING:
    1. Send objective to PLANNER LLM with available tools list
    2. Parse JSON response → InvestigationPlan (ordered steps)
    3. Validate plan has required steps (fail fast)

  Phase 2 — EXECUTION:
    For each step in plan:
      4. Determine which tool to call (from plan step hint)
      5. Run the tool with appropriate parameters
      6. Store result in plan step
      7. If step fails → log error, continue to next step

  Phase 3 — SYNTHESIS:
    8. Compile all step results into a synthesis prompt
    9. Run SYNTHESISER LLM to produce final RCA report
    10. Return structured report

REQUIREMENTS (pip install):
  langchain>=0.2.0
  langchain-core>=0.2.0
  langchain-aws>=0.1.0
  pydantic>=2.0.0

=============================================================================
"""

import json
import re
from datetime import datetime
from typing import Optional

from langchain_core.messages import SystemMessage, HumanMessage

from src.tools.pod_log_reader import read_pod_logs, list_available_pods
from src.tools.k8s_event_reader import read_k8s_events, read_node_metrics
from src.models.schemas import InvestigationPlan, PlanStep
from src.utils.bedrock_client import get_llm, get_llm_for_planning
from src.utils.app_logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# PLANNER PROMPT
# The Planner LLM does NOT call tools — it only produces a plan.
# A good plan is: specific, ordered, and aware of dependencies.
# ---------------------------------------------------------------------------
PLANNER_SYSTEM_PROMPT = """You are an expert SRE Planner. Your job is to create
a detailed investigation plan for an EKS pod failure.

You have access to these investigation tools:
  1. list_available_pods    — lists available pod log files
  2. read_pod_logs          — reads pod container logs
  3. read_k8s_events        — reads Kubernetes events (OOMKilled, BackOff etc.)
  4. read_node_metrics      — reads node-level memory/CPU metrics

Create a step-by-step plan to investigate an EKS pod failure.
The plan should be comprehensive and ordered logically.

RULES:
  - Always start with list_available_pods
  - Always read pod logs before events (logs give context for events)
  - Always check node metrics if OOMKilled is suspected
  - Include a synthesis step at the end (no tool — just LLM analysis)
  - Maximum 8 steps

Respond with ONLY valid JSON in this format:
{
  "plan_id": "PLAN-001",
  "objective": "brief objective statement",
  "steps": [
    {
      "step_number": 1,
      "description": "what this step does",
      "tool_hint": "tool name to use or null for LLM-only step",
      "depends_on": []
    }
  ],
  "total_steps": N
}
"""

# ---------------------------------------------------------------------------
# SYNTHESISER PROMPT
# Takes all step results and writes the final RCA report.
# Separated from execution so the LLM focuses on WRITING not DOING.
# ---------------------------------------------------------------------------
SYNTHESISER_SYSTEM_PROMPT = """You are a Senior SRE writing an incident post-mortem.

Below are the results from each investigation step. 
Your job is to synthesise ALL findings into a comprehensive Root Cause Analysis report.

Structure your report as:
## 🔴 EXECUTIVE SUMMARY
[2-3 sentences for management]

## ⏱️ TIMELINE
[Chronological events with timestamps]

## 🔍 ROOT CAUSE
[Primary root cause with specific evidence]

## 🔗 CONTRIBUTING FACTORS
[Secondary factors that made it worse]

## ⚠️ ANOMALIES
[Each anomaly with severity, time, evidence]

## 🔧 IMMEDIATE ACTIONS (Do Now)
[Numbered list — specific and actionable]

## 🛡️ PREVENTION (Do Next Sprint)
[Numbered list — prevent recurrence]

## 📘 RUNBOOK
[Reference applicable runbook from runbooks/ directory]

Be SPECIFIC: use actual values from the data (e.g., "512Mi limit", "09:47 UTC", "restarts=3").
Generic statements like "increase resources" are NOT acceptable.
"""


class PlanAndExecuteAgent:
    """
    Plan-and-Execute agent for EKS pod failure investigation.

    This implements a three-phase architecture:
      Phase 1: PLAN   — LLM creates investigation plan
      Phase 2: EXECUTE — Tools execute each step
      Phase 3: SYNTHESISE — LLM writes final report from results

    This is more structured than ReAct but less flexible:
      ReAct:             adapts dynamically based on each observation
      Plan-and-Execute:  follows a predetermined plan with less adaptation

    Best used when:
      - The investigation workflow is well-known (like OOMKilled)
      - You need predictable step execution
      - You want to ensure nothing is missed

    Compare with ReAct when:
      - The issue is novel and the investigation path is unknown
      - You need maximum flexibility in tool selection
    """

    def __init__(self):
        self.planner_llm      = get_llm_for_planning()
        self.executor_llm     = get_llm()
        self.synthesiser_llm  = get_llm()

        # Map tool names to callable functions
        self.tool_map = {
            "list_available_pods":  list_available_pods,
            "read_pod_logs":        read_pod_logs,
            "read_k8s_events":      read_k8s_events,
            "read_node_metrics":    read_node_metrics,
        }

        logger.info("PlanAndExecuteAgent initialised")

    # -----------------------------------------------------------------------
    # PHASE 1: PLANNING
    # -----------------------------------------------------------------------

    def _create_plan(self, pod_name: str, namespace: str) -> InvestigationPlan:
        """
        Call the Planner LLM to create an investigation plan.

        ALGORITHM:
          1. Build messages with planner system prompt
          2. Include pod_name and namespace in user message
          3. Parse JSON response into InvestigationPlan
          4. Validate step count and required steps
        """
        logger.info("[PLAN] Creating investigation plan for %s/%s", namespace, pod_name)

        user_message = (
            f"Create an investigation plan for: "
            f"EKS pod '{pod_name}' in namespace '{namespace}' has failed. "
            f"We need to determine the root cause."
        )

        messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]

        response = self.planner_llm.invoke(messages)
        raw_plan = response.content

        logger.debug("[PLAN] Raw planner output: %s", raw_plan[:500])

        # Parse JSON — strip markdown fences if present
        cleaned = raw_plan.strip()
        cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)

        try:
            plan_data = json.loads(cleaned)
            steps = [
                PlanStep(
                    step_number=s["step_number"],
                    description=s["description"],
                    tool_hint=s.get("tool_hint"),
                    depends_on=s.get("depends_on", []),
                )
                for s in plan_data["steps"]
            ]

            plan = InvestigationPlan(
                plan_id=plan_data.get("plan_id", "PLAN-001"),
                created_at=datetime.now().isoformat(),
                objective=plan_data.get("objective", f"Investigate {pod_name} failure"),
                target_pod=pod_name,
                target_namespace=namespace,
                steps=steps,
                total_steps=len(steps),
            )

            logger.info("[PLAN] Plan created — %d steps: %s",
                        plan.total_steps,
                        [s.description[:40] for s in steps])

            return plan

        except (json.JSONDecodeError, KeyError) as e:
            logger.error("[PLAN] Failed to parse planner output: %s", e)
            # Fallback: create a default plan
            return self._default_plan(pod_name, namespace)

    def _default_plan(self, pod_name: str, namespace: str) -> InvestigationPlan:
        """
        Fallback plan if the Planner LLM produces invalid JSON.
        Hardcoded to ensure investigation always proceeds.
        """
        logger.warning("[PLAN] Using default fallback plan")
        steps = [
            PlanStep(step_number=1, description="List available pod log files",
                     tool_hint="list_available_pods"),
            PlanStep(step_number=2, description=f"Read pod logs for {pod_name}",
                     tool_hint="read_pod_logs", depends_on=[1]),
            PlanStep(step_number=3, description=f"Read K8s events for {namespace}/{pod_name}",
                     tool_hint="read_k8s_events", depends_on=[2]),
            PlanStep(step_number=4, description="Read node metrics for memory pressure",
                     tool_hint="read_node_metrics", depends_on=[3]),
            PlanStep(step_number=5, description="Synthesise root cause analysis",
                     tool_hint=None, depends_on=[2, 3, 4]),
        ]
        return InvestigationPlan(
            plan_id="PLAN-FALLBACK",
            created_at=datetime.now().isoformat(),
            objective=f"Investigate {pod_name} failure in {namespace}",
            target_pod=pod_name,
            target_namespace=namespace,
            steps=steps,
            total_steps=len(steps),
        )

    # -----------------------------------------------------------------------
    # PHASE 2: EXECUTION
    # -----------------------------------------------------------------------

    def _execute_step(self, step: PlanStep, pod_name: str, namespace: str,
                      previous_results: dict) -> str:
        """
        Execute a single plan step.

        ALGORITHM:
          1. Check if step has a tool_hint → call the appropriate tool
          2. If no tool_hint → LLM synthesis step
          3. Build appropriate tool arguments from pod_name + namespace
          4. Handle tool call errors gracefully (don't abort the plan)
          5. Return result string

        TOOL ARGUMENT MAPPING:
          Different tools need different arguments.
          We build them from the step context and previous results.
        """
        logger.info("[EXEC] Step %d: %s (tool=%s)",
                    step.step_number, step.description[:60], step.tool_hint)

        if not step.tool_hint:
            # ---------------------------------------------------------------
            # LLM-only synthesis step (no tool call)
            # ---------------------------------------------------------------
            synthesis_input = (
                f"Based on these investigation findings:\n\n"
                + "\n\n".join([
                    f"Step {k}: {v[:2000]}" for k, v in previous_results.items()
                ])
                + f"\n\nProvide a brief intermediate analysis for pod {pod_name}"
            )
            messages = [HumanMessage(content=synthesis_input)]
            response = self.executor_llm.invoke(messages)
            return response.content

        # -------------------------------------------------------------------
        # Tool execution step
        # -------------------------------------------------------------------
        tool_fn = self.tool_map.get(step.tool_hint)
        if not tool_fn:
            return f"ERROR: Unknown tool '{step.tool_hint}'"

        try:
            # Build tool-specific arguments
            if step.tool_hint == "list_available_pods":
                result = tool_fn.invoke({})

            elif step.tool_hint == "read_pod_logs":
                result = tool_fn.invoke({
                    "pod_name": pod_name,
                    "namespace": namespace,
                    "level_filter": "ALL",
                })

            elif step.tool_hint == "read_k8s_events":
                result = tool_fn.invoke({
                    "namespace": namespace,
                    "pod_name": pod_name,
                    "event_type": "ALL",
                })

            elif step.tool_hint == "read_node_metrics":
                result = tool_fn.invoke({})

            else:
                result = tool_fn.invoke({})

            logger.info("[EXEC] Step %d complete — result length=%d chars",
                        step.step_number, len(str(result)))
            return str(result)

        except Exception as e:
            error_msg = f"Tool {step.tool_hint} failed: {str(e)}"
            logger.error("[EXEC] %s", error_msg)
            return error_msg

    # -----------------------------------------------------------------------
    # PHASE 3: SYNTHESIS
    # -----------------------------------------------------------------------

    def _synthesise_report(self, plan: InvestigationPlan,
                           step_results: dict) -> str:
        """
        Call the Synthesiser LLM to write the final report.

        ALGORITHM:
          1. Build compilation of all step results
          2. Add the investigation objective and plan for context
          3. Call synthesiser LLM with structured prompt
          4. Return formatted report
        """
        logger.info("[SYNTH] Synthesising final report from %d step results",
                    len(step_results))

        # Build the input for the synthesiser
        steps_summary = "\n\n".join([
            f"=== STEP {step_num}: {plan.steps[step_num-1].description} ===\n{result[:3000]}"
            for step_num, result in sorted(step_results.items())
        ])

        synthesis_prompt = (
            f"Investigation Target: {plan.target_namespace}/{plan.target_pod}\n"
            f"Objective: {plan.objective}\n\n"
            f"Investigation Results:\n\n{steps_summary}"
        )

        messages = [
            SystemMessage(content=SYNTHESISER_SYSTEM_PROMPT),
            HumanMessage(content=synthesis_prompt),
        ]

        response = self.synthesiser_llm.invoke(messages)
        return response.content

    # -----------------------------------------------------------------------
    # MAIN ENTRY POINT
    # -----------------------------------------------------------------------

    def investigate(self, pod_name: str, namespace: str = "production") -> dict:
        """
        Run the full Plan-and-Execute investigation.

        Args:
            pod_name:  Pod to investigate
            namespace: K8s namespace

        Returns:
            dict with plan, step_results, final_report, metadata
        """
        start_time = datetime.now()

        logger.info("=" * 60)
        logger.info("Plan-and-Execute Investigation Started")
        logger.info("Pod: %s | Namespace: %s", pod_name, namespace)
        logger.info("=" * 60)

        # PHASE 1: Create plan
        plan = self._create_plan(pod_name, namespace)
        logger.info("[PLAN] ✅ Plan created with %d steps", plan.total_steps)

        # PHASE 2: Execute each step
        step_results: dict[int, str] = {}
        for step in plan.steps:
            result = self._execute_step(step, pod_name, namespace, step_results)
            step_results[step.step_number] = result
            step.completed = True
            step.result    = result[:500]   # Store truncated in model

        logger.info("[EXEC] ✅ All %d steps executed", len(step_results))

        # PHASE 3: Synthesise final report
        final_report = self._synthesise_report(plan, step_results)
        logger.info("[SYNTH] ✅ Report synthesised")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("Plan-and-Execute complete — duration=%.1fs", duration)

        return {
            "output":       final_report,
            "mode":         "PLAN_AND_EXECUTE",
            "plan":         plan.model_dump(),
            "step_results": {k: v[:1000] for k, v in step_results.items()},
            "metadata": {
                "pod_name":      pod_name,
                "namespace":     namespace,
                "total_steps":   plan.total_steps,
                "started_at":    start_time.isoformat(),
                "completed_at":  end_time.isoformat(),
                "duration_secs": round(duration, 1),
            }
        }
