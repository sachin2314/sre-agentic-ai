import os
import boto3
from botocore.exceptions import ClientError
from langchain_core.tools import tool

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "false").lower() == "true"

MOCK_LOGS = """START RequestId: 123 Version: $LATEST
Simulated failure: Missing S3 permissions
Traceback (most recent call last):
  File "/var/task/app.py", line 10, in handler
    raise Exception("Simulated failure")
Exception: Simulated failure
END RequestId: 123
REPORT RequestId: 123 Duration: 3000 ms Billed Duration: 3000 ms Memory Size: 128 MB Max Memory Used: 120 MB"""


@tool
def cloudwatch_logs_tool(log_group: str) -> dict:
    """Fetch recent CloudWatch logs for a given log group."""
    if SIMULATION_MODE:
        return {"log_group": log_group, "log_stream": "SIMULATED", "events": MOCK_LOGS, "event_count": 8}

    client = boto3.client("logs")
    try:
        streams = client.describe_log_streams(
            logGroupName=log_group, orderBy="LastEventTime", descending=True, limit=1
        )
        if not streams.get("logStreams"):
            return {"log_group": log_group, "events": "No log streams found — Lambda may never have been invoked.", "event_count": 0}

        log_stream = streams["logStreams"][0]["logStreamName"]
        response = client.get_log_events(logGroupName=log_group, logStreamName=log_stream, limit=50, startFromHead=False)
        messages = [e["message"] for e in response.get("events", [])]
        return {"log_group": log_group, "log_stream": log_stream, "events": "\n".join(messages), "event_count": len(messages)}

    except ClientError as e:
        return {"log_group": log_group, "events": f"Error: {str(e)}", "event_count": 0}
