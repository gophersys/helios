# Standard includes
from typing import Dict, List, Optional, Set

from corekinect.utils import Logger
from kubernetes import client as k8s_client

# App includes
from src.services.kubernetes.client import get_batch_v1_api, get_core_v1_api
from src.services.log.logger import get_logger


def get_available_nodes_for_product(product: str, required_features: Optional[Dict[str, str]] = None) -> List[str]:
    """
    Get list of available nodes for a product that don't have running validation jobs.

    NOTE: With Kubernetes-native scheduling (using pod anti-affinity), this function
    is mainly useful for monitoring/debugging. Kubernetes scheduler automatically
    handles node selection and ensures only one validation job per node via pod
    anti-affinity rules. Jobs are created without hostname assignment and Kubernetes
    schedules them automatically when nodes become available.

    Args:
        product: Product name (e.g., "sigma5")
        required_features: Optional dict of required feature labels (e.g., {"joulescope": "true"})

    Returns:
        List of available node hostnames
    """
    logger: Logger = get_logger()
    core_v1 = get_core_v1_api()
    batch_v1 = get_batch_v1_api()

    try:
        # Get all nodes with the product label
        label_selector = f"corekinect.com/validation-product={product}"
        nodes = core_v1.list_node(label_selector=label_selector)

        if not nodes.items:
            logger.warning(f"No nodes found for product: {product}")
            return []

        # Get all running validation jobs for this product
        job_label_selector = f"corekinect.com/validation-product={product}"
        jobs = batch_v1.list_job_for_all_namespaces(label_selector=job_label_selector)

        # Get pods for running jobs
        running_pods = []
        for job in jobs.items:
            if job.status.active:  # Job is still running
                # Get pods for this job
                pod_label_selector = f"job-name={job.metadata.name}"
                pods = core_v1.list_pod_for_all_namespaces(label_selector=pod_label_selector)
                running_pods.extend(pods.items)

        # Get set of nodes that have running validation jobs
        nodes_with_jobs: Set[str] = set()
        for pod in running_pods:
            if pod.spec.node_name:
                nodes_with_jobs.add(pod.spec.node_name)

        # Filter nodes by required features and check availability
        available_nodes = []
        for node in nodes.items:
            node_name = node.metadata.name

            # Skip if node already has a running job
            if node_name in nodes_with_jobs:
                continue

            # Check if node has required features
            if required_features:
                node_labels = node.metadata.labels or {}
                has_all_features = True
                for feature_key, feature_value in required_features.items():
                    label_key = f"corekinect.com/validation/{feature_key}"
                    if node_labels.get(label_key) != feature_value:
                        has_all_features = False
                        break

                if not has_all_features:
                    continue

            available_nodes.append(node_name)

        logger.info(f"Found {len(available_nodes)} available nodes for product {product}")
        return available_nodes

    except Exception as e:
        logger.error(f"Error getting available nodes: {str(e)}")
        return []


def get_node_running_jobs(node_hostname: str, product: str) -> List[str]:
    """
    Get list of running job names on a specific node for a product.

    Args:
        node_hostname: Node hostname
        product: Product name

    Returns:
        List of running job names
    """
    logger: Logger = get_logger()
    batch_v1 = get_batch_v1_api()
    core_v1 = get_core_v1_api()

    try:
        # Get all running jobs for this product
        job_label_selector = f"corekinect.com/validation-product={product}"
        jobs = batch_v1.list_job_for_all_namespaces(label_selector=job_label_selector)

        running_job_names = []
        for job in jobs.items:
            if job.status.active:
                # Check if any pod for this job is on the target node
                pod_label_selector = f"job-name={job.metadata.name}"
                pods = core_v1.list_pod_for_all_namespaces(label_selector=pod_label_selector)
                for pod in pods.items:
                    if pod.spec.node_name == node_hostname:
                        running_job_names.append(job.metadata.name)
                        break

        return running_job_names

    except Exception as e:
        logger.error(f"Error getting running jobs for node {node_hostname}: {str(e)}")
        return []


def is_node_available(node_hostname: str, product: str) -> bool:
    """
    Check if a node is available (no running validation jobs).

    Args:
        node_hostname: Node hostname
        product: Product name

    Returns:
        True if node is available, False otherwise
    """
    running_jobs = get_node_running_jobs(node_hostname, product)
    return len(running_jobs) == 0


def get_job_status_from_k8s(k8s_job_name: str, namespace: str = "default") -> Optional[Dict]:
    """
    Get job status from Kubernetes.

    Args:
        k8s_job_name: Kubernetes job name
        namespace: Kubernetes namespace

    Returns:
        Dict with job status info or None if job not found
    """
    logger: Logger = get_logger()
    batch_v1 = get_batch_v1_api()

    try:
        job = batch_v1.read_namespaced_job(name=k8s_job_name, namespace=namespace)

        status_info = {
            "name": job.metadata.name,
            "active": job.status.active or 0,
            "succeeded": job.status.succeeded or 0,
            "failed": job.status.failed or 0,
            "conditions": [],
        }

        if job.status.conditions:
            for condition in job.status.conditions:
                status_info["conditions"].append(
                    {
                        "type": condition.type,
                        "status": condition.status,
                        "reason": condition.reason,
                        "message": condition.message,
                        "last_transition_time": (
                            condition.last_transition_time.isoformat() if condition.last_transition_time else None
                        ),
                    }
                )

        return status_info

    except k8s_client.rest.ApiException as e:
        if e.status == 404:
            logger.warning(f"Job {k8s_job_name} not found in namespace {namespace}")
            return None
        logger.error(f"Error getting job status: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        return None


def delete_k8s_job(k8s_job_name: str, namespace: str = "default") -> Optional[str]:
    """
    Delete a Kubernetes job.

    Args:
        k8s_job_name: Kubernetes job name
        namespace: Kubernetes namespace

    Returns:
        Error message if deletion failed, None otherwise
    """
    logger: Logger = get_logger()
    batch_v1 = get_batch_v1_api()

    try:
        # Delete the job with propagation policy to delete pods
        batch_v1.delete_namespaced_job(
            name=k8s_job_name,
            namespace=namespace,
            propagation_policy="Foreground",  # Delete pods immediately
        )
        logger.info(f"Successfully deleted Kubernetes job: {k8s_job_name}")
        return None

    except k8s_client.rest.ApiException as e:
        if e.status == 404:
            logger.warning(f"Job {k8s_job_name} not found, may already be deleted")
            return None
        logger.error(f"Error deleting job: {str(e)}")
        return f"Error deleting job: {str(e)}"
    except Exception as e:
        logger.error(f"Error deleting job: {str(e)}")
        return f"Error deleting job: {str(e)}"
