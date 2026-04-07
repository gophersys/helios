from .client import get_core_v1_api, get_apps_v1_api, get_batch_v1_api
from .serializers import serialize_namespace


def get_cluster_info() -> dict:
    """Get cluster version and high-level resource summary."""
    core = get_core_v1_api()

    # Version info and platform(s) from all nodes
    nodes = core.list_node()
    version_info = {}
    if nodes.items:
        ni = nodes.items[0].status.node_info
        platforms = sorted({
            f"{n.status.node_info.operating_system}/{n.status.node_info.architecture}"
            for n in nodes.items if n.status and n.status.node_info
        })
        version_info = {
            "kubernetesVersion": ni.kubelet_version if ni else "Unknown",
            "platforms": platforms if platforms else ["Unknown"],
        }

    # Resource counts
    all_pods = core.list_pod_for_all_namespaces()
    pod_phases = {"Running": 0, "Pending": 0, "Failed": 0, "Succeeded": 0, "Unknown": 0}
    for pod in all_pods.items:
        phase = pod.status.phase or "Unknown"
        pod_phases[phase] = pod_phases.get(phase, 0) + 1

    apps = get_apps_v1_api()
    all_deployments = apps.list_deployment_for_all_namespaces()
    dep_available = sum(1 for d in all_deployments.items if d.status.available_replicas and d.status.available_replicas > 0)

    all_services = core.list_service_for_all_namespaces()

    batch = get_batch_v1_api()
    all_jobs = batch.list_job_for_all_namespaces()
    job_active = sum(1 for j in all_jobs.items if j.status.active and j.status.active > 0)
    job_succeeded = sum(1 for j in all_jobs.items if j.status.succeeded and j.status.succeeded > 0)
    job_failed = sum(1 for j in all_jobs.items if j.status.failed and j.status.failed > 0)

    namespaces = core.list_namespace()

    return {
        **version_info,
        "nodeCount": len(nodes.items),
        "namespaceCount": len(namespaces.items),
        "resources": {
            "pods": {
                "running": pod_phases.get("Running", 0),
                "pending": pod_phases.get("Pending", 0),
                "failed": pod_phases.get("Failed", 0),
                "succeeded": pod_phases.get("Succeeded", 0),
                "total": len(all_pods.items),
            },
            "deployments": {
                "available": dep_available,
                "progressing": len(all_deployments.items) - dep_available,
                "total": len(all_deployments.items),
            },
            "services": {
                "total": len(all_services.items),
            },
            "jobs": {
                "active": job_active,
                "succeeded": job_succeeded,
                "failed": job_failed,
                "total": len(all_jobs.items),
            },
        },
    }


def list_namespaces() -> list[dict]:
    """List all Kubernetes namespaces."""
    core = get_core_v1_api()
    ns_list = core.list_namespace()
    return [serialize_namespace(ns) for ns in ns_list.items]
