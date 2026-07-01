import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
load_dotenv()

from src.day4.tools.eks_logs_tool import eks_pod_logs_tool
result = eks_pod_logs_tool.invoke({"namespace": "default", "target_name": "file-upload"})
print(result)
