from typing import Optional, Dict, Any, List

from kubernetes import client, config
from kubernetes.client import ApiException


def _load_kube_config():
    """
    Load Kubernetes configuration.
    Tries in-cluster first, then falls back to local kubeconfig.
    """
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()


def _find_pods_for_target(namespace: str, target_name: str) -> List[client.V1Pod]:
    """
    Try to interpret target_name as:
    1) A direct pod name.
    2) A deployment name (resolve to pods via label selector).
    """
    v1 = client.CoreV1Api()
    apps_v1 = client.AppsV1Api()

    # First, try as a direct pod name
    try:
        pod = v1.read_namespaced_pod(name=target_name, namespace=namespace)
        return [pod]
    except ApiException as e:
        if e.status != 404:
            raise

    # If not a pod, try as a deployment
    try:
        deployment = apps_v1.read_namespaced_deployment(name=target_name, namespace=namespace)
    except ApiException as e:
        if e.status == 404:
            # Neither pod nor deployment found
            return []
        raise

    # Get pods matching the deployment's selector
    selector = deployment.spec.selector.match_labels
    label_selector = ",".join(f"{k}={v}" for k, v in selector.items())

    pods = v1.list_namespaced_pod(namespace=namespace, label_selector=label_selector).items
    return pods


def get_eks_pod_logs_real(
    namespace: str,
    target_name: str,
    container: Optional[str] = None,
    tail_lines: int = 200
) -> Dict[str, Any]:
    """
    Fetch logs from a pod (or pods behind a deployment) in EKS.
    Returns a structured dictionary for the agent.
    """
    _load_kube_config()
    v1 = client.CoreV1Api()

    pods = _find_pods_for_target(namespace, target_name)

    if not pods:
        return {
            "namespace": namespace,
            "target": target_name,
            "pod": None,
            "container": None,
            "logs": f"No pods found for '{target_name}' in namespace '{namespace}'.",
            "truncated": False,
        }

    # For now, pick the first pod (you can later enhance to pick non-Running, etc.)
    pod = pods[0]
    pod_name = pod.metadata.name

    # Determine container
    containers = pod.spec.containers
    container_name = container

    if container_name is None:
        if len(containers) == 1:
            container_name = containers[0].name
        else:
            # Multiple containers and none specified; pick the first
            container_name = containers[0].name

    try:
        log_text = v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            container=container_name,
            tail_lines=tail_lines,
            timestamps=True,
        )
    except ApiException as e:
        return {
            "namespace": namespace,
            "target": target_name,
            "pod": pod_name,
            "container": container_name,
            "logs": f"Error fetching logs: {str(e)}",
            "truncated": False,
        }

    # We don't know if it's truncated exactly, but we can hint based on tail_lines
    truncated = False

    return {
        "namespace": namespace,
        "target": target_name,
        "pod": pod_name,
        "container": container_name,
        "logs": log_text,
        "truncated": truncated,
    }
