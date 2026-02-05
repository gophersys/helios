import logging
from typing import Optional

from kubernetes import client as k8s_client
from kubernetes import config as k8s_config

logger = logging.getLogger(__name__)

# Global Kubernetes client instance
appKubernetesClient: Optional[k8s_client.ApiClient] = None


def init_kubernetes_client() -> Optional[k8s_client.ApiClient]:
    """Initialize the global Kubernetes client"""
    global appKubernetesClient

    # Try to load in-cluster config first, then fall back to kubeconfig
    try:
        k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        try:
            k8s_config.load_kube_config()
        except k8s_config.ConfigException:
            logger.warning("Kubernetes config not found — K8s features disabled")
            return None

    client = k8s_client.ApiClient()
    appKubernetesClient = client

    return client


def get_k8s_client() -> k8s_client.ApiClient:
    """Get the global Kubernetes client instance"""
    global appKubernetesClient

    if appKubernetesClient is None:
        raise RuntimeError("Kubernetes client not initialized. Call init_kubernetes_client() first.")

    return appKubernetesClient


def get_core_v1_api() -> k8s_client.CoreV1Api:
    """Get Core V1 API client using the global Kubernetes client"""
    return k8s_client.CoreV1Api(get_k8s_client())


def get_apps_v1_api() -> k8s_client.AppsV1Api:
    """Get Apps V1 API client using the global Kubernetes client"""
    return k8s_client.AppsV1Api(get_k8s_client())


def get_batch_v1_api() -> k8s_client.BatchV1Api:
    """Get Batch V1 API client using the global Kubernetes client"""
    return k8s_client.BatchV1Api(get_k8s_client())


def get_networking_v1_api() -> k8s_client.NetworkingV1Api:
    """Get Networking V1 API client using the global Kubernetes client"""
    return k8s_client.NetworkingV1Api(get_k8s_client())


def get_rbac_v1_api() -> k8s_client.RbacAuthorizationV1Api:
    """Get RBAC V1 API client using the global Kubernetes client"""
    return k8s_client.RbacAuthorizationV1Api(get_k8s_client())
