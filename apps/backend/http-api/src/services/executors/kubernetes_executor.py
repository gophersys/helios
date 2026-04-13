"""Kubernetes Job executor — creates batch/v1 Jobs via the K8s API.

Works in staging/production where the K8s API is available (in-cluster config).
Jobs run to completion with no retries (backoffLimit=0), same as the existing
build_job_runner.py and validation manual.py patterns.
"""

import logging
import re
from typing import Dict, List, Optional

from src.services.executors.base import ExecutorResult, JobExecutor, VolumeMount

logger = logging.getLogger(__name__)

# Lazy-loaded K8s API accessor — patched in tests
_batch_v1_api = None


def _get_batch_v1():
    """Get the K8s BatchV1Api. Deferred so import only happens in K8s envs."""
    from src.services.kubernetes.client import get_batch_v1_api
    return get_batch_v1_api()


class KubernetesExecutor(JobExecutor):
    """Creates K8s Jobs via the Kubernetes API."""

    def __init__(self, ttl_after_finished: int = 3600):
        self._ttl = ttl_after_finished

    def submit(
        self,
        image: str,
        job_id: str,
        env: Dict[str, str],
        command: List[str],
        *,
        namespace: str = "default",
        labels: Optional[Dict[str, str]] = None,
        resource_requests: Optional[Dict[str, str]] = None,
        resource_limits: Optional[Dict[str, str]] = None,
        node_selector: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 3600,
        volumes: Optional[List[VolumeMount]] = None,
    ) -> ExecutorResult:
        try:
            batch_v1_getter = _get_batch_v1
        except Exception:
            return ExecutorResult(success=False, error="K8s client not available")

        job_name = self._make_job_name(job_id, labels)

        # Build env list
        env_list = [{"name": k, "value": v} for k, v in env.items()]

        # Build volume specs
        k8s_volumes = []
        k8s_volume_mounts = []
        for i, vol in enumerate(volumes or []):
            vol_name = vol.name or f"vol-{i}"
            if vol.host_path:
                k8s_volumes.append({
                    "name": vol_name,
                    "hostPath": {"path": vol.host_path, "type": "DirectoryOrCreate"},
                })
            else:
                k8s_volumes.append({"name": vol_name, "emptyDir": {}})
            k8s_volume_mounts.append({
                "name": vol_name,
                "mountPath": vol.mount_path,
                "readOnly": vol.read_only,
            })

        container_name = re.sub(r"[^a-z0-9-]", "-", (labels or {}).get("app", "worker").lower())[:63]

        job_spec = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "namespace": namespace,
                "labels": labels or {},
            },
            "spec": {
                "backoffLimit": 0,
                "ttlSecondsAfterFinished": self._ttl,
                "activeDeadlineSeconds": timeout_seconds,
                "template": {
                    "metadata": {"labels": labels or {}},
                    "spec": {
                        "restartPolicy": "Never",
                        "terminationGracePeriodSeconds": 30,
                        **({"nodeSelector": node_selector} if node_selector else {}),
                        "containers": [{
                            "name": container_name,
                            "image": image,
                            "imagePullPolicy": "Always",
                            "command": command[:1] if command else ["/bin/sh"],
                            "args": command[1:] if len(command) > 1 else [],
                            "env": env_list,
                            **({"resources": {
                                **({"requests": resource_requests} if resource_requests else {}),
                                **({"limits": resource_limits} if resource_limits else {}),
                            }} if resource_requests or resource_limits else {}),
                            **({"volumeMounts": k8s_volume_mounts} if k8s_volume_mounts else {}),
                        }],
                        **({"volumes": k8s_volumes} if k8s_volumes else {}),
                    },
                },
            },
        }

        try:
            batch_v1 = _get_batch_v1()
            batch_v1.create_namespaced_job(namespace=namespace, body=job_spec)
            logger.info("Created K8s Job %s in namespace %s", job_name, namespace)
            return ExecutorResult(success=True, job_name=job_name)
        except Exception as e:
            error = f"Failed to create K8s Job {job_name}: {e}"
            logger.error(error)
            return ExecutorResult(success=False, error=error)

    def cancel(self, job_name: str, namespace: str = "default") -> bool:
        try:
            batch_v1 = _get_batch_v1()
            batch_v1.delete_namespaced_job(
                name=job_name,
                namespace=namespace,
                propagation_policy="Background",
            )
            logger.info("Deleted K8s Job %s in namespace %s", job_name, namespace)
            return True
        except Exception as e:
            logger.error("Failed to delete K8s Job %s: %s", job_name, e)
            return False

    def is_alive(self, job_name: str, namespace: str = "default") -> Optional[bool]:
        try:
            batch_v1 = _get_batch_v1()
            job = batch_v1.read_namespaced_job_status(name=job_name, namespace=namespace)
            if job.status.active and job.status.active > 0:
                return True
            if job.status.succeeded or job.status.failed:
                return False
            return None
        except Exception:
            return None

    @staticmethod
    def _make_job_name(job_id: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Create a K8s-compliant job name (max 63 chars, RFC 1123)."""
        prefix = (labels or {}).get("app", "concord-job")
        prefix = re.sub(r"[^a-z0-9-]", "-", prefix.lower()).strip("-")
        short_id = re.sub(r"[^a-z0-9]", "", job_id.lower())[:12]
        name = f"{prefix}-{short_id}"
        return re.sub(r"-+", "-", name)[:63]
