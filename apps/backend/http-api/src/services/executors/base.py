"""Abstract base for job executors."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ExecutorResult:
    """Result of a job submission."""

    success: bool
    job_name: Optional[str] = None
    error: Optional[str] = None


@dataclass
class VolumeMount:
    """Volume mount specification (portable across Docker and K8s)."""

    name: str
    host_path: Optional[str] = None
    mount_path: str = ""
    read_only: bool = False


class JobExecutor(ABC):
    """Abstract base for dispatching containerized workloads.

    Implementations exist for Docker (local daemon via docker.sock)
    and Kubernetes (batch/v1 Jobs). Both use the same callback protocol:
    containers report results back to the Concord HTTP API.
    """

    @abstractmethod
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
        """Submit a container workload. Returns immediately after submission."""
        ...

    @abstractmethod
    def cancel(self, job_name: str, namespace: str = "default") -> bool:
        """Cancel/kill a running job. Returns True if successful."""
        ...

    @abstractmethod
    def is_alive(self, job_name: str, namespace: str = "default") -> Optional[bool]:
        """Check if a job is running. None=unknown, True=running, False=done."""
        ...
