from typing import Optional, Dict, Any


def get_eks_pod_logs_mock(
    namespace: str,
    target_name: str,
    container: Optional[str] = None,
    tail_lines: int = 200
) -> Dict[str, Any]:
    """
    Return simulated EKS pod logs for testing without a real cluster.
    """
    sample_logs = """
2024-05-26T10:00:00Z Container starting...
2024-05-26T10:00:01Z Loading configuration...
2024-05-26T10:00:02Z ERROR: Failed to connect to S3 endpoint
Traceback (most recent call last):
  File "/app/app.py", line 42, in <module>
    main()
  File "/app/app.py", line 21, in main
    s3_client.list_buckets()
botocore.exceptions.EndpointConnectionError: Could not connect to the endpoint URL: "https://s3.eu-west-2.amazonaws.com"
"""

    return {
        "namespace": namespace,
        "target": target_name,
        "pod": "simulated-pod-123",
        "container": container or "file-upload",
        "logs": sample_logs.strip(),
        "truncated": False,
    }
