from typing import Optional, Dict, Any
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))


from src.day4.tools.eks_logs_real import get_eks_pod_logs_real
from src.day4.tools.eks_logs_mock import get_eks_pod_logs_mock

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "false").lower() == "true"



def get_eks_pod_logs(
    namespace: str,
    target_name: str,
    container: Optional[str] = None,
    tail_lines: int = 200
) -> Dict[str, Any]:
    """
    Route to real or mock EKS logs based on SIMULATION_MODE.
    """
    if SIMULATION_MODE:
        return get_eks_pod_logs_mock(namespace, target_name, container, tail_lines)
    else:
        return get_eks_pod_logs_real(namespace, target_name, container, tail_lines)
