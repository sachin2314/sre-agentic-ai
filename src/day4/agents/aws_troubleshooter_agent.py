import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from typing import Any, Dict
from dotenv import load_dotenv

load_dotenv()

from langchain_aws import ChatBedrockConverse
from langchain.agents import create_agent
from src.day4.tools.aws_cloudwatch_tool import cloudwatch_logs_tool
from src.day4.tools.eks_logs_tool import eks_pod_logs_tool
import sys
sys.stdout.reconfigure(encoding='utf-8')

def build_aws_troubleshooter_agent():
    """
    Build and return the AWS Troubleshooter agent.
    The agent can:
      - Investigate Lambda issues using CloudWatch logs.
      - Investigate EKS issues using pod/deployment logs.
    """

    tools = [
        cloudwatch_logs_tool,
        eks_pod_logs_tool,
    ]

    system_prompt = """
You are an AWS Troubleshooter SRE agent.

Your responsibilities:
- Investigate issues in AWS Lambda and EKS.
- Use ONLY the provided tools to fetch logs and information.
- Operate in READ-ONLY mode. Never modify, delete, or create resources.
- Base your conclusions on actual tool outputs (logs, statuses, metrics if available).
- When unsure, state your uncertainty and what additional data would help.

How to reason:
1. First, understand the user's question:
   - Is it about a Lambda function?
   - Is it about an EKS service/pod/deployment?
   - If unclear, ask a brief clarifying question.

2. For Lambda issues:
   - Use the cloudwatch_logs_tool with the Lambda function name.
   - Read the logs carefully.
   - Look for patterns:
     - Timeouts (e.g. "Task timed out after...")
     - Missing dependencies (e.g. "No module named ...")
     - Permission issues (e.g. "AccessDeniedException")
     - Runtime errors and stack traces
   - Classify the failure (timeout, dependency, permission, config, internal bug).
   - Produce a root cause hypothesis and concrete remediation steps.

3. For EKS issues:
   - Use the eks_pod_logs_tool with the namespace and target name
     (pod name or deployment name).
   - Read the pod logs carefully.
   - Look for patterns:
     - Crash at startup (config/env issues, missing dependencies)
     - Image pull errors
     - Connection failures
     - OOMKilled or resource issues
   - Classify the failure and propose concrete remediation steps.

4. Answer format:
   - Summary: 1–3 sentences describing what is wrong.
   - Root cause (most likely): clear, concise statement.
   - Evidence: specific log lines or observations that support your conclusion.
   - Severity: low / medium / high / critical.
   - Recommended actions: step-by-step remediation.
   - Follow-up checks: what to verify after applying the fix.
   - Uncertainties (if any): what you are not sure about and why.

Always:
- Prefer precision over vagueness.
- Quote exact log snippets when referencing evidence.
- Do NOT invent logs or metrics that were not returned by tools.
"""

    model = ChatBedrockConverse(
        model=os.getenv("BEDROCK_MODEL_ID"),
        region_name=os.getenv("AWS_REGION")
    )

    return create_agent(model, tools, system_prompt=system_prompt)


def run_aws_troubleshooter(query: str) -> Dict[str, Any]:
    """
    Run the AWS Troubleshooter Agent on a natural language query.
    """
    agent = build_aws_troubleshooter_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": query}]})
    return result
