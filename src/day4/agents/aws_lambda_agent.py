import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
load_dotenv()

from src.day4.tools.aws_cloudwatch_tool import cloudwatch_logs_tool

result = cloudwatch_logs_tool.invoke("/aws/lambda/file-upload-app-resize-lambda-helpful-gopher")
print(result)
