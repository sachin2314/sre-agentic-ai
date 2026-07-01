import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from langchain_aws import ChatBedrockConverse
from langchain.agents import create_agent
from src.day4.tools.aws_cloudwatch_tool import cloudwatch_logs_tool
from src.day4.tools.aws_lambda import lambda_metrics_tool
from src.day4.safety.tool_guardrails import TOOL_SAFETY_RULES

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

model = ChatBedrockConverse(
    model=os.getenv("BEDROCK_MODEL_ID"),
    region_name=os.getenv("AWS_REGION")
)

tools = [cloudwatch_logs_tool, lambda_metrics_tool]

system_prompt = f"You are an AWS troubleshooter agent.\n{TOOL_SAFETY_RULES}"

agent = create_agent(model, tools, system_prompt=system_prompt)

FUNCTION_NAME = "file-upload-app-resize-lambda-helpful-gopher"  # replace with a real function name from your AWS account

response = agent.invoke({
    "messages": [{"role": "user", "content":
        f"Investigate lambda function '{FUNCTION_NAME}'. "
        f"Check its metrics and logs from log group /aws/lambda/{FUNCTION_NAME}. "
        f"Identify any errors or performance issues."
    }]
})

print(response["messages"][-1].content)
