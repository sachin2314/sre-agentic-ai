"""
=============================================================================
FILE: src/agent/self_reflection.py
COURSE: AI Agentic SRE - Day 8: Deep Dive — Agent Architectures
TOPIC:  Self-Reflection Loop — KEY Day 8 concept
=============================================================================

PURPOSE:
  Implements the SELF-REFLECTION loop that wraps the ReAct agent.
  After the agent produces an answer, the reflection step asks the LLM
  to critique its own output and identify what's missing.

  This is one of the most important Day 8 concepts and a KEY difference
  from Day 6 (which had no self-evaluation).

WHY SELF-REFLECTION MATTERS:
  Problem with basic ReAct agents:
    → Agent may stop too early ("I found the error, job done")
    → Agent may miss corroborating evidence from a second source
    → Agent may provide vague recommendations ("fix the memory issue")
    → Agent may not check the node-level context

  Self-reflection fixes this by having the LLM ask:
    "Was my analysis COMPLETE? SPECIFIC? ACTIONABLE?"
    If No → run a targeted follow-up agent pass

  In production: This pattern is called "Reflexion" (Shinn et al., 2023)
  and has been shown to significantly improve agent task completion rates.

THE REFLECTION CHECKLIST FOR SRE ANALYSIS:
  ✅ Root cause clearly identified with specific evidence
  ✅ Timeline of events constructed (when did each thing happen?)
  ✅ All affected resources identified (pod + node)
  ✅ Recommendations are specific and actionable (not "fix memory")
  ✅ Runbook referenced if applicable
  ✅ Blast radius assessed (what else could be affected?)
  ✅ Prevention recommendations included (not just fix)

ALGORITHM:
  1. Run main agent → get initial output
  2. Feed output to REFLECTION PROMPT asking LLM to self-evaluate
  3. Parse structured JSON response (is_complete, missing_items, score)
  4. If is_complete=True OR max_iterations reached → return output
  5. If is_complete=False → construct targeted follow-up task
  6. Run agent again with targeted task → append result to output
  7. Repeat from step 2 (max 2 reflection iterations in practice)

REQUIREMENTS (pip install):
  langchain-core>=0.2.0
  langchain-aws>=0.1.0
  pydantic>=2.0.0

=============================================================================
"""

import json
import re
from typing import Callable

from src.models.schemas import ReflectionResult
from src.utils.app_logger import get_logger
from src.utils.bedrock_client import get_llm_for_reflection

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# REFLECTION PROMPT
# This is the system prompt for the reflection step.
# Crucially: the LLM is evaluating ITS OWN previous output.
# We must be very specific about what "complete" means for an SRE investigation.
# ---------------------------------------------------------------------------
REFLECTION_SYSTEM_PROMPT = """
You are a SENIOR SRE reviewing an AI agent's investigation output.
Your job is to evaluate whether the investigation is COMPLETE and ACTIONABLE.

Evaluate the investigation against this checklist:
1. ROOT_CAUSE: Is the root cause clearly identified with specific evidence from logs?
2. TIMELINE: Is there a clear chronological sequence of events?
3. ALL_RESOURCES: Were all affected resources identified? (pod logs + K8s events + node)
4. ACTIONABLE_FIXES: Are recommendations specific? ("increase memory limit to 1Gi" NOT "fix memory")
5. RUNBOOK: Was a relevant runbook referenced?
6. BLAST_RADIUS: Was the impact on other services assessed?
7. PREVENTION: Were preventive measures included?

You MUST respond in valid JSON only. No other text. Format:
{
  "is_complete": true/false,
  "completeness_pct": 0-100,
  "missing_items": ["item1 that is missing", "item2"],
  "quality_notes": ["what was done well"],
  "follow_up_task": "specific instruction for the agent to fill the gap (null if complete)"
}

IMPORTANT: Be STRICT. An investigation is only complete if ALL 7 checklist items are addressed
with specific evidence. Generic statements fail the check.
"""


def _parse_reflection_json(llm_output: str) -> ReflectionResult:
    """
    Parse the reflection LLM output into a ReflectionResult model.

    ALGORITHM:
      1. Strip markdown code fences if present (LLMs sometimes add ```json)
      2. Try json.loads() on the cleaned string
      3. Build ReflectionResult from parsed dict
      4. Fall back to a "complete" result if parsing fails (fail-safe)

    Args:
        llm_output: Raw LLM response string

    Returns:
        ReflectionResult: parsed and validated reflection
    """
    # Strip markdown code fences that LLMs sometimes add
    cleaned = llm_output.strip()
    cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
    cleaned = re.sub(r"\n?```$", "", cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        return ReflectionResult(
            is_complete      = bool(data.get("is_complete", False)),
            completeness_pct = int(data.get("completeness_pct", 50)),
            missing_items    = list(data.get("missing_items", [])),
            quality_notes    = list(data.get("quality_notes", [])),
            follow_up_task   = data.get("follow_up_task"),
        )
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Reflection JSON parse failed: %s — using fallback", e)
        # Fail-safe: treat as complete to avoid infinite retry loops
        return ReflectionResult(
            is_complete      = True,
            completeness_pct = 70,
            missing_items    = [],
            quality_notes    = ["(Reflection parsing failed — proceeding with output)"],
            follow_up_task   = None,
        )


class SelfReflectingAgent:
    """
    Wraps a ReAct agent with a self-reflection loop.

    USAGE:
        from src.agent.self_reflection import SelfReflectingAgent

        # agent_fn is any callable: task_string → result_string
        reflecting_agent = SelfReflectingAgent(
            agent_fn=my_react_agent.run,
            max_reflections=2
        )
        final_output = reflecting_agent.run("Investigate EKS pod failure for web-service-7d8b9c")

    HOW IT DIFFERS FROM BASIC REACT (Day 6):
        Day 6: Agent runs → produces output → DONE
        Day 8: Agent runs → produces output → REFLECT → is it complete?
                → if NO: run targeted follow-up → REFLECT AGAIN
                → if YES: DONE

    The reflection adds ~1-2 LLM calls per investigation but significantly
    improves output quality — especially completeness and specificity.
    """

    def __init__(self, agent_fn: Callable[[str], str], max_reflections: int = 2):
        """
        Args:
            agent_fn:        Callable that takes a task string and returns result string
                             (typically AgentExecutor.invoke or similar)
            max_reflections: Maximum number of reflection-and-retry cycles.
                             Set to 0 to disable reflection.
                             In production, 2 is the sweet spot (quality vs cost).
        """
        self.agent_fn        = agent_fn
        self.max_reflections = max_reflections
        self.reflection_llm  = get_llm_for_reflection()
        logger.info("SelfReflectingAgent initialised — max_reflections=%d", max_reflections)

    def run(self, initial_task: str) -> dict:
        """
        Run the agent with self-reflection loop.

        ALGORITHM:
          Step 1: Run agent with initial task
          Step 2: Run reflection check
          Step 3: If incomplete AND iterations remaining → run targeted follow-up
          Step 4: Repeat from Step 2
          Step 5: Return compiled output with reflection metadata

        Args:
            initial_task: The investigation task string

        Returns:
            dict with keys:
                final_output:      Combined agent output (all iterations)
                reflection_result: Last ReflectionResult
                iterations:        How many times the agent ran
                reflection_score:  Completeness percentage (0-100)
        """
        logger.info("=" * 60)
        logger.info("SelfReflectingAgent.run() — task: %s", initial_task[:100])
        logger.info("=" * 60)

        accumulated_output: list[str] = []
        reflection_result: ReflectionResult = None
        iterations: int = 0

        # -----------------------------------------------------------------------
        # ITERATION 0: Initial agent run
        # -----------------------------------------------------------------------
        logger.info("[Iteration %d] Running initial agent pass...", iterations)

        initial_result = self.agent_fn(initial_task)
        accumulated_output.append(f"=== INITIAL ANALYSIS ===\n{initial_result}")
        iterations += 1

        logger.info("[Iteration %d] Initial run complete. Starting reflection...", iterations)

        # -----------------------------------------------------------------------
        # REFLECTION LOOP: Up to max_reflections additional passes
        # -----------------------------------------------------------------------
        for reflection_num in range(self.max_reflections):
            combined_so_far = "\n\n".join(accumulated_output)

            reflection_result = self._reflect(combined_so_far)

            logger.info(
                "[Reflection %d] Score=%d%% Complete=%s Missing=%s",
                reflection_num + 1,
                reflection_result.completeness_pct,
                reflection_result.is_complete,
                reflection_result.missing_items,
            )

            # ---------------------------------------------------------------
            # STOP CONDITION: Analysis is complete
            # ---------------------------------------------------------------
            if reflection_result.is_complete:
                logger.info(
                    "✅ Reflection passed — analysis is complete (score=%d%%)",
                    reflection_result.completeness_pct
                )
                break

            # ---------------------------------------------------------------
            # RETRY: Run agent with targeted follow-up task
            # ---------------------------------------------------------------
            if not reflection_result.follow_up_task:
                logger.info("No follow-up task provided — stopping reflection")
                break

            follow_up_task = (
                f"FOLLOW-UP INVESTIGATION REQUIRED.\n"
                f"Previous analysis was incomplete (score: {reflection_result.completeness_pct}%).\n"
                f"Missing items: {', '.join(reflection_result.missing_items)}\n\n"
                f"Please address specifically: {reflection_result.follow_up_task}"
            )

            logger.info(
                "[Iteration %d] Running follow-up agent pass: %s",
                iterations + 1,
                reflection_result.follow_up_task[:100]
            )

            follow_up_result = self.agent_fn(follow_up_task)
            accumulated_output.append(
                f"\n=== FOLLOW-UP ANALYSIS (Iteration {iterations + 1}) ===\n"
                f"Addressing: {', '.join(reflection_result.missing_items)}\n\n"
                f"{follow_up_result}"
            )
            iterations += 1

        # Final reflection score
        score = reflection_result.completeness_pct if reflection_result else 0

        return {
            "final_output":      "\n\n".join(accumulated_output),
            "reflection_result": reflection_result,
            "iterations":        iterations,
            "reflection_score":  score,
            "quality_notes":     reflection_result.quality_notes if reflection_result else [],
        }

    def _reflect(self, agent_output: str) -> ReflectionResult:
        """
        Run the reflection LLM call against the agent's output.

        ALGORITHM:
          1. Build prompt: system (reflection checklist) + user (agent output)
          2. Call LLM with temperature=0 (deterministic evaluation)
          3. Parse JSON response into ReflectionResult
          4. Return result

        Args:
            agent_output: The full output from the agent so far

        Returns:
            ReflectionResult: structured evaluation
        """
        from langchain_core.messages import SystemMessage, HumanMessage

        messages = [
            SystemMessage(content=REFLECTION_SYSTEM_PROMPT),
            HumanMessage(content=(
                "Please evaluate the following SRE investigation output:\n\n"
                "---BEGIN INVESTIGATION OUTPUT---\n"
                f"{agent_output[:6000]}\n"   # Truncate to keep within context window
                "---END INVESTIGATION OUTPUT---\n\n"
                "Respond with ONLY the JSON evaluation. No other text."
            )),
        ]

        logger.info("Calling reflection LLM...")
        response = self.reflection_llm.invoke(messages)
        raw_output = response.content

        logger.debug("Raw reflection output: %s", raw_output[:500])

        return _parse_reflection_json(raw_output)
