import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from src.day4.agents.aws_troubleshooter_agent import run_aws_troubleshooter

# Example 1: Lambda issue
result = run_aws_troubleshooter(
    "Investigate why the Lambda function 'file-upload-app-resize-lambda-helpful-gopher' is failing."
)

print(result["messages"][-1].content)
