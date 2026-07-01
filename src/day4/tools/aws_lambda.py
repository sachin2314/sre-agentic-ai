import boto3
from datetime import datetime, timedelta

def get_lambda_metrics(function_name):
    client = boto3.client('cloudwatch')

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=60)

    metrics = client.get_metric_statistics(
        Namespace='AWS/Lambda',
        MetricName='Duration',
        Dimensions=[
            {
                'Name': 'FunctionName',
                'Value': function_name
            },
        ],
        StartTime=start_time,
        EndTime=end_time,
        Period=60,
        Statistics=['Average']
    )
    
    return metrics

from langchain_core.tools import tool

@tool
def lambda_metrics_tool(function_name: str):
    """Fetches lambda duration metrics"""
    return get_lambda_metrics(function_name)



