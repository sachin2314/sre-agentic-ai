from kubernetes import client, config

config.load_kube_config()

def get_pod_logs(namespace, pod_name):
    v1 = client.CoreV1Api()
    return v1.read_namespaced_pod_log(name=pod_name, namespace=namespace)
    
from langchain_core.tools import tool
@tool
def k8s_logs_tools(namespace: str, pod_name: str):
    """Fetches Kubernetes pod logs"""
    return get_pod_logs(namespace, pod_name)



