import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))



from typing import Optional

from langchain.tools import tool
from src.day4.tools.eks_logs import get_eks_pod_logs


@tool
def eks_pod_logs_tool(namespace: str, target_name: str, container: Optional[str] = None):
    """
    Fetch recent logs from a pod or deployment in an EKS cluster.

    - namespace: Kubernetes namespace (e.g. 'default').
    - target_name: Pod name or deployment name (e.g. 'file-upload').
    - container: Optional container name if the pod has multiple containers.

    Returns structured logs for analysis.
    """
    return get_eks_pod_logs(namespace=namespace, target_name=target_name, container=container)
