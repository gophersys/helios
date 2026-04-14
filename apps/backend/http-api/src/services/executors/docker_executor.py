"""Docker-based job executor — spawns containers via the local daemon.

Works in:
- Development (Docker Compose mounts docker.sock)
- K8s build-service (docker.sock DinD pattern)

Containers run in detached mode and report results back via HTTP callbacks
to the Concord API (same protocol as K8s Jobs).
"""

import logging
import re
import subprocess
from typing import Dict, List, Optional

from src.services.executors.base import ExecutorResult, JobExecutor, VolumeMount

logger = logging.getLogger(__name__)


class DockerExecutor(JobExecutor):
    """Spawns containers via the local Docker daemon (docker.sock)."""

    def __init__(
        self,
        network: str = "host",
        timeout: int = 3600,
        default_volumes: Optional[List[VolumeMount]] = None,
    ):
        self._network = network
        self._timeout = timeout
        self._default_volumes = default_volumes or []

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
        container_name = self._make_container_name(job_id, labels)

        docker_cmd = [
            "docker", "run",
            "-d",
            "--name", container_name,
            "--network", self._network,
        ]

        # Environment variables
        for key, value in env.items():
            docker_cmd.extend(["-e", f"{key}={value}"])

        # Labels
        for key, value in (labels or {}).items():
            docker_cmd.extend(["--label", f"{key}={value}"])

        # Volume mounts (explicit + defaults)
        all_volumes = (self._default_volumes or []) + (volumes or [])
        for vol in all_volumes:
            if vol.host_path:
                mode = "ro" if vol.read_only else "rw"
                docker_cmd.extend(["-v", f"{vol.host_path}:{vol.mount_path}:{mode}"])

        # Memory limit (from resource_limits if provided)
        if resource_limits and "memory" in resource_limits:
            docker_cmd.extend(["--memory", resource_limits["memory"]])

        # CPU limit
        if resource_limits and "cpu" in resource_limits:
            try:
                cpus = float(resource_limits["cpu"].rstrip("m")) / 1000 if resource_limits["cpu"].endswith("m") else float(resource_limits["cpu"])
                docker_cmd.extend(["--cpus", str(cpus)])
            except (ValueError, AttributeError) as e:
                logger.debug("Failed to parse CPU limit %r: %s", resource_limits.get("cpu"), e)

        # Stop timeout
        docker_cmd.extend(["--stop-timeout", str(timeout_seconds or self._timeout)])

        # Image + command
        docker_cmd.append(image)
        docker_cmd.extend(command)

        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or f"docker run exited with code {result.returncode}"
                logger.error("Failed to start container %s: %s", container_name, error_msg)
                return ExecutorResult(success=False, error=error_msg)

            container_id = result.stdout.strip()[:12]
            logger.info("Started container %s (id=%s) for job %s", container_name, container_id, job_id)
            return ExecutorResult(success=True, job_name=container_name)

        except subprocess.TimeoutExpired:
            error = f"docker run timed out after 30s for job {job_id}"
            logger.error(error)
            return ExecutorResult(success=False, error=error)
        except FileNotFoundError:
            error = "docker CLI not found — is Docker installed and docker.sock mounted?"
            logger.error(error)
            return ExecutorResult(success=False, error=error)
        except Exception as e:
            logger.exception("Unexpected error starting container for job %s", job_id)
            return ExecutorResult(success=False, error=str(e))

    def cancel(self, job_name: str, namespace: str = "default") -> bool:
        try:
            result = subprocess.run(
                ["docker", "kill", job_name],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                logger.info("Killed container %s", job_name)
                return True
            logger.warning("Failed to kill container %s: %s", job_name, result.stderr.strip())
            return False
        except Exception as e:
            logger.error("Error killing container %s: %s", job_name, e)
            return False

    def is_alive(self, job_name: str, namespace: str = "default") -> Optional[bool]:
        try:
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Running}}", job_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return False
            return result.stdout.strip().lower() == "true"
        except Exception:
            return None

    @staticmethod
    def _make_container_name(job_id: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Create a Docker-safe container name."""
        prefix = "concord"
        if labels and "app" in labels:
            prefix = labels["app"]
        prefix = re.sub(r"[^a-z0-9-]", "-", prefix.lower()).strip("-")
        short_id = re.sub(r"[^a-z0-9]", "", job_id.lower())[:12]
        name = f"{prefix}-{short_id}"
        return re.sub(r"-+", "-", name)[:63]
