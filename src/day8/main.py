"""
=============================================================================
FILE: main.py
COURSE: AI Agentic SRE - Day 8: Deep Dive — Agent Architectures
TOPIC:  Entry point — run ReAct or Plan-and-Execute EKS investigation
=============================================================================

PURPOSE:
  CLI entry point for the Day 8 EKS Investigation Agent.
  Supports three modes:
    1. react    — ReAct agent with self-reflection (recommended)
    2. plan     — Plan-and-Execute agent
    3. compare  — Run both and compare outputs

HOW TO RUN:
  # Basic ReAct investigation (with reflection)
  python main.py --mode react --pod web-service-7d8b9c

  # Plan-and-Execute investigation
  python main.py --mode plan --pod web-service-7d8b9c

  # Run both and compare (educational mode)
  python main.py --mode compare --pod web-service-7d8b9c

  # Disable self-reflection (faster, for development)
  python main.py --mode react --pod web-service-7d8b9c --no-reflection

  # Investigate a different pod
  python main.py --mode react --pod api-gateway-6f9a2b --namespace production

ALGORITHM:
  1. Parse CLI arguments (argparse)
  2. Load environment variables (.env)
  3. Validate pod name and namespace
  4. Run chosen agent mode
  5. Print final report to console
  6. Save report to reports/ directory

REQUIREMENTS (pip install — run: pip install -r requirements.txt):
  langchain>=0.2.0
  langchain-core>=0.2.0
  langchain-aws>=0.1.0
  boto3>=1.34.0
  pydantic>=2.0.0
  python-dotenv>=1.0.0

ENVIRONMENT SETUP:
  cp .env.example .env
  # Edit .env with your AWS credentials

=============================================================================
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load .env BEFORE importing agent modules (they read env vars at import time)
# ---------------------------------------------------------------------------
load_dotenv()

from src.agent.react_agent import run_react_investigation
from src.agent.plan_and_execute_agent import PlanAndExecuteAgent
from src.utils.app_logger import get_logger

logger = get_logger("main")


def save_report(content: str, pod_name: str, mode: str) -> Path:
    """
    Save the investigation report to the reports/ directory.

    ALGORITHM:
      1. Create reports/ if it doesn't exist
      2. Generate filename: report_{pod}_{mode}_{timestamp}.md
      3. Write markdown content to file
      4. Return the file path

    Args:
        content:  Report text (markdown)
        pod_name: Pod that was investigated
        mode:     "REACT" or "PLAN_AND_EXECUTE"

    Returns:
        Path to saved report file
    """
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_pod   = pod_name.replace("/", "_")
    filename   = f"report_{safe_pod}_{mode.lower()}_{timestamp}.md"
    filepath   = reports_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# EKS Investigation Report\n")
        f.write(f"**Pod:** {pod_name}  \n")
        f.write(f"**Mode:** {mode}  \n")
        f.write(f"**Generated:** {datetime.now().isoformat()}  \n\n")
        f.write("---\n\n")
        f.write(content)

    logger.info("Report saved: %s", filepath)
    return filepath


def print_separator(title: str = ""):
    """Print a visual separator for console output."""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}\n")
    else:
        print(f"\n{'='*60}\n")


def run_react_mode(args: argparse.Namespace) -> None:
    """Run the ReAct agent investigation."""
    print_separator(f"ReAct Agent — Investigating {args.pod}")

    result = run_react_investigation(
        pod_name=args.pod,
        namespace=args.namespace,
        enable_reflection=not args.no_reflection,
    )

    print(result["output"])

    if result.get("reflection_score"):
        print(f"\n📊 Reflection Score: {result['reflection_score']}%")

    print(f"\n⏱️  Duration: {result['metadata']['duration_secs']}s")
    print(f"🔁 Iterations: {result['metadata']['iterations']}")

    # Save report
    report_path = save_report(result["output"], args.pod, "REACT")
    print(f"\n💾 Report saved: {report_path}")


def run_plan_mode(args: argparse.Namespace) -> None:
    """Run the Plan-and-Execute agent investigation."""
    print_separator(f"Plan-and-Execute Agent — Investigating {args.pod}")

    agent  = PlanAndExecuteAgent()
    result = agent.investigate(pod_name=args.pod, namespace=args.namespace)

    # Print the plan first (educational)
    print("📋 INVESTIGATION PLAN:")
    if "plan" in result:
        for step in result["plan"]["steps"]:
            tool = step.get("tool_hint") or "LLM synthesis"
            print(f"  Step {step['step_number']}: {step['description']} [{tool}]")

    print_separator("INVESTIGATION REPORT")
    print(result["output"])
    print(f"\n⏱️  Duration: {result['metadata']['duration_secs']}s")
    print(f"📋 Steps executed: {result['metadata']['total_steps']}")

    # Save report
    report_path = save_report(result["output"], args.pod, "PLAN_AND_EXECUTE")
    print(f"\n💾 Report saved: {report_path}")


def run_compare_mode(args: argparse.Namespace) -> None:
    """Run both modes and compare — educational mode."""
    print_separator("COMPARISON MODE: ReAct vs Plan-and-Execute")
    print("This mode runs both agent architectures on the same problem.")
    print("Compare the outputs to understand the trade-offs.\n")

    # Run ReAct
    print_separator("Part 1: ReAct Agent")
    react_result = run_react_investigation(
        pod_name=args.pod,
        namespace=args.namespace,
        enable_reflection=True,
    )
    save_report(react_result["output"], args.pod, "REACT")

    # Run Plan-and-Execute
    print_separator("Part 2: Plan-and-Execute Agent")
    pae_agent  = PlanAndExecuteAgent()
    pae_result = pae_agent.investigate(pod_name=args.pod, namespace=args.namespace)
    save_report(pae_result["output"], args.pod, "PLAN_AND_EXECUTE")

    # Comparison summary
    print_separator("COMPARISON SUMMARY")
    print(f"{'Metric':<30} {'ReAct':>15} {'Plan-and-Execute':>20}")
    print("-" * 65)
    print(f"{'Duration (seconds)':<30} {react_result['metadata']['duration_secs']:>15} "
          f"{pae_result['metadata']['duration_secs']:>20}")
    print(f"{'Agent iterations':<30} {react_result['metadata']['iterations']:>15} "
          f"{pae_result['metadata']['total_steps']:>20}")
    if react_result.get("reflection_score"):
        print(f"{'Reflection score (%)':<30} {react_result['reflection_score']:>15} {'N/A':>20}")
    print("\n💡 KEY TRADE-OFFS:")
    print("  ReAct:             More flexible, adapts to what it finds")
    print("  Plan-and-Execute:  More predictable, ensures nothing is missed")
    print("  Best in practice:  Combine both — plan gives structure, ReAct fills gaps")


def main():
    """
    Main entry point — parse args and dispatch to the right mode.
    """
    parser = argparse.ArgumentParser(
        description="Day 8: EKS Pod Investigation Agent (ReAct + Plan-and-Execute)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --mode react  --pod web-service-7d8b9c
  python main.py --mode plan   --pod web-service-7d8b9c
  python main.py --mode compare --pod web-service-7d8b9c
  python main.py --mode react  --pod api-gateway-6f9a2b --no-reflection
        """
    )

    parser.add_argument(
        "--mode",
        choices=["react", "plan", "compare"],
        default="react",
        help="Agent mode: react, plan, or compare (default: react)",
    )
    parser.add_argument(
        "--pod",
        default="web-service-7d8b9c",
        help="Pod name to investigate (default: web-service-7d8b9c)",
    )
    parser.add_argument(
        "--namespace",
        default="production",
        help="Kubernetes namespace (default: production)",
    )
    parser.add_argument(
        "--no-reflection",
        action="store_true",
        default=False,
        help="Disable self-reflection loop (faster, less thorough)",
    )

    args = parser.parse_args()

    logger.info("Starting Day 8 EKS Investigation Agent")
    logger.info("Mode=%s Pod=%s Namespace=%s Reflection=%s",
                args.mode, args.pod, args.namespace, not args.no_reflection)

    print_separator("AI Agentic SRE - Day 8: Agent Architectures")
    print(f"🎯 Investigation Target: {args.namespace}/{args.pod}")
    print(f"🤖 Agent Mode:          {args.mode.upper()}")
    print(f"🔍 Self-Reflection:     {'DISABLED' if args.no_reflection else 'ENABLED'}")
    print(f"🧠 LLM:                 eu.anthropic.claude-haiku-4-5-20251001-v1:0")

    try:
        if args.mode == "react":
            run_react_mode(args)
        elif args.mode == "plan":
            run_plan_mode(args)
        elif args.mode == "compare":
            run_compare_mode(args)

    except KeyboardInterrupt:
        print("\n\n⚠️  Investigation interrupted by user.")
        sys.exit(0)
    except Exception as e:
        logger.error("Fatal error: %s", str(e), exc_info=True)
        print(f"\n❌ Error: {e}")
        print("Check that your .env file has valid AWS credentials.")
        sys.exit(1)


if __name__ == "__main__":
    main()
