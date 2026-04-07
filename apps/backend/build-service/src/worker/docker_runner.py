"""Docker Build Runner — spawns firmware builds inside dynamic container images.

Instead of running builds inside the build-service's own container (which would
require baking in every possible NCS toolchain version), this runner:

1. Reads the firmware repo's .devcontainer/devcontainer.json
2. Pulls the specified builder image (cached by Docker daemon)
3. Spawns a sibling container with the cloned repo + ccache mounted
4. Streams build output for real-time logging
5. Collects artifacts from the shared output directory

Works identically in development (Docker Compose), staging, and production (K8s)
because all environments mount the Docker socket.
"""

import json
import logging
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

log = logging.getLogger("build-service")


@dataclass
class DevcontainerConfig:
    """Parsed devcontainer.json configuration relevant to CI builds."""
    image: str = ""
    container_env: Dict[str, str] = field(default_factory=dict)
    post_create_command: Optional[str] = None


class DockerBuildRunner:
    """Runs firmware builds inside dynamically-selected Docker containers."""

    def __init__(
        self,
        workspace_volume: str = "",
        ccache_volume: str = "",
        builder_network: str = "host",
        builder_timeout: int = 1800,
        default_image: str = "containers.ad.corekinect.com/ncs-fw-dev:2.7.0",
    ):
        self.workspace_volume = workspace_volume
        self.ccache_volume = ccache_volume
        self.builder_network = builder_network
        self.builder_timeout = builder_timeout
        self.default_image = default_image
        self._current_container: Optional[str] = None

    # ------------------------------------------------------------------
    # Image resolution
    # ------------------------------------------------------------------

    @staticmethod
    def extract_builder_image(repo_dir: Path) -> Optional[str]:
        """Read the builder image from a repo's .devcontainer/devcontainer.json.

        Returns the full image URL (e.g., 'containers.ad.corekinect.com/ncs-fw-dev:2.7.0')
        or None if not found.
        """
        devcontainer = repo_dir / ".devcontainer" / "devcontainer.json"
        if not devcontainer.exists():
            return None
        try:
            text = devcontainer.read_text()
            # Strip // comments (common in devcontainer.json)
            text = re.sub(r"//.*$", "", text, flags=re.MULTILINE)
            data = json.loads(text)
            image = data.get("image", "")
            if image:
                log.info("Resolved builder image from devcontainer.json: %s", image)
                return image
        except Exception as e:
            log.warning("Failed to parse devcontainer.json in %s: %s", repo_dir, e)
        return None

    @staticmethod
    def parse_devcontainer(repo_dir: Path) -> DevcontainerConfig:
        """Parse a repo's .devcontainer/devcontainer.json for CI-relevant fields.

        Extracts:
          - image: container image URL
          - containerEnv: environment variables to pass to the builder
          - postCreateCommand: command to run after container creation (before build)

        Returns a DevcontainerConfig with defaults for any missing fields.
        """
        devcontainer = repo_dir / ".devcontainer" / "devcontainer.json"
        config = DevcontainerConfig()

        if not devcontainer.exists():
            return config

        try:
            text = devcontainer.read_text()
            # Strip // comments (common in devcontainer.json)
            text = re.sub(r"//.*$", "", text, flags=re.MULTILINE)
            data = json.loads(text)

            config.image = data.get("image", "")
            config.container_env = data.get("containerEnv", {})

            # postCreateCommand can be a string or a list
            pcc = data.get("postCreateCommand")
            if isinstance(pcc, list):
                config.post_create_command = " && ".join(pcc)
            elif isinstance(pcc, str):
                config.post_create_command = pcc

            if config.image:
                log.info("Parsed devcontainer.json: image=%s, env_vars=%d, postCreate=%s",
                         config.image, len(config.container_env),
                         "yes" if config.post_create_command else "no")
        except Exception as e:
            log.warning("Failed to parse devcontainer.json in %s: %s", repo_dir, e)

        return config

    @staticmethod
    def extract_ncs_version(image: str) -> Optional[str]:
        """Extract NCS version from an image tag like 'registry/ncs-fw-dev:2.7.0'."""
        match = re.search(r":(\d+\.\d+\.\d+)", image)
        return match.group(1) if match else None

    # ------------------------------------------------------------------
    # Orphan container cleanup
    # ------------------------------------------------------------------

    @staticmethod
    def cleanup_orphaned_containers():
        """Kill any lingering concord-build-* containers from a previous instance.

        Called at startup to clean up containers left behind if the
        orchestrator was killed mid-build (e.g., during a rolling update).
        """
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=concord-build-", "--format", "{{.Names}}"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return

            containers = [c.strip() for c in result.stdout.strip().split("\n") if c.strip()]
            for name in containers:
                log.warning("Killing orphaned builder container: %s", name)
                try:
                    subprocess.run(["docker", "kill", name], capture_output=True, timeout=10)
                    subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=10)
                except Exception as e:
                    log.warning("Failed to cleanup container %s: %s", name, e)

            if containers:
                log.info("Cleaned up %d orphaned builder container(s)", len(containers))
        except Exception as e:
            log.warning("Orphan container cleanup failed: %s", e)

    # ------------------------------------------------------------------
    # Image management
    # ------------------------------------------------------------------

    def ensure_image(self, image: str) -> bool:
        """Ensure the builder image is available locally. Pulls if not cached."""
        # Check if already cached
        result = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True, timeout=10,
        )
        if result.returncode == 0:
            log.info("Builder image cached: %s", image)
            return True

        # Pull the image
        log.info("Pulling builder image: %s (this may take a few minutes on first run)...", image)
        result = subprocess.run(
            ["docker", "pull", image],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode == 0:
            log.info("Builder image pulled successfully: %s", image)
            return True

        log.error("Failed to pull builder image %s: %s", image, result.stderr[:500])
        return False

    # ------------------------------------------------------------------
    # Build execution
    # ------------------------------------------------------------------

    def run_build(
        self,
        image: str,
        job_id: str,
        work_dir: Path,
        output_dir: Path,
        env: Dict[str, str],
        cmd: List[str],
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[bool, str]:
        """Run a build inside a dynamically-spawned Docker container.

        Args:
            image: Docker image to use (from devcontainer.json)
            job_id: Build job ID (for container naming)
            work_dir: Host path to workspace (contains cloned repos, scripts)
            output_dir: Host path to output directory (artifacts land here)
            env: Environment variables to pass to the build
            cmd: Command to execute inside the container
            log_callback: Optional callback for each line of output

        Returns:
            (success, log_output) tuple
        """
        container_name = f"concord-build-{job_id[:12]}"
        docker_cmd = self._build_docker_cmd(
            image=image,
            container_name=container_name,
            job_id=job_id,
            env=env,
            cmd=cmd,
        )

        log.info("Spawning builder container: %s (image=%s)", container_name, image)
        log.info("Docker command: %s", " ".join(docker_cmd))

        output_lines = []
        self._current_container = container_name

        try:
            process = subprocess.Popen(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # Stream output line-by-line
            log_batch = []
            batch_size = 10
            start_time = time.time()

            for line in iter(process.stdout.readline, ""):
                line = line.rstrip("\n")
                output_lines.append(line)

                # Batch log streaming
                log_batch.append(line)
                if len(log_batch) >= batch_size:
                    chunk = "\n".join(log_batch) + "\n"
                    if log_callback:
                        log_callback(chunk)
                    log_batch = []

                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > self.builder_timeout:
                    log.error("Build timeout after %ds — killing container %s",
                              int(elapsed), container_name)
                    self._kill_container(container_name)
                    process.kill()
                    return False, "\n".join(output_lines) + "\n[TIMEOUT]"

            # Flush remaining log lines
            if log_batch and log_callback:
                log_callback("\n".join(log_batch) + "\n")

            process.wait(timeout=30)
            success = process.returncode == 0

            duration = int(time.time() - start_time)
            log.info("Builder container %s exited with code %d after %ds",
                     container_name, process.returncode, duration)

            return success, "\n".join(output_lines)

        except subprocess.TimeoutExpired:
            log.error("Build process timed out — killing container %s", container_name)
            self._kill_container(container_name)
            return False, "\n".join(output_lines) + "\n[TIMEOUT]"

        except Exception as e:
            log.error("Build execution error: %s", e)
            self._kill_container(container_name)
            return False, "\n".join(output_lines) + f"\n[ERROR: {e}]"

        finally:
            self._current_container = None

    def _build_docker_cmd(
        self,
        image: str,
        container_name: str,
        job_id: str,
        env: Dict[str, str],
        cmd: List[str],
        container_env: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """Construct the docker run command with proper mounts and env vars."""
        docker_cmd = [
            "docker", "run", "--rm",
            "--name", container_name,
        ]

        # Network mode
        if self.builder_network:
            docker_cmd.extend(["--network", self.builder_network])

        # Volume mounts — named Docker volumes (dev) or hostPath bind mounts (K8s)
        workspace_host_path = os.environ.get("WORKSPACE_HOST_PATH", "")
        ccache_host_path = os.environ.get("CCACHE_HOST_PATH", "")

        if self.workspace_volume:
            # Development: use named Docker volumes
            docker_cmd.extend([
                "--mount", f"type=volume,source={self.workspace_volume},target=/workspace",
            ])
        elif workspace_host_path:
            # K8s: use host path bind mount (same path the build service sees)
            docker_cmd.extend([
                "-v", f"{workspace_host_path}:/workspace",
            ])

        if self.ccache_volume:
            docker_cmd.extend([
                "--mount", f"type=volume,source={self.ccache_volume},target=/ccache",
            ])
        elif ccache_host_path:
            docker_cmd.extend([
                "-v", f"{ccache_host_path}:/ccache",
            ])

        # NOTE: SDK is copied into the workspace volume by the orchestrator
        # (see loop.py). Bind mounts from container paths don't work in DinD
        # because the Docker daemon resolves paths on the HOST, not inside
        # the orchestrator container.

        # Working directory inside container
        docker_cmd.extend(["-w", f"/workspace/{job_id}"])

        # Environment variables — pass build-specific vars, NOT Zephyr paths
        # (Zephyr paths are baked into the builder image and vary per NCS version)
        for key, value in env.items():
            if key in ("ZEPHYR_BASE", "ZEPHYR_SDK_INSTALL_DIR", "ZEPHYR_TOOLCHAIN_VARIANT"):
                continue  # Let the image defaults apply
            docker_cmd.extend(["-e", f"{key}={value}"])

        # Merge containerEnv from devcontainer.json (lower priority than build env)
        if container_env:
            for key, value in container_env.items():
                if key not in env and key not in ("ZEPHYR_BASE", "ZEPHYR_SDK_INSTALL_DIR", "ZEPHYR_TOOLCHAIN_VARIANT"):
                    docker_cmd.extend(["-e", f"{key}={value}"])

        # Always set ccache env vars
        docker_cmd.extend([
            "-e", "CCACHE_DIR=/ccache",
            "-e", "CMAKE_C_COMPILER_LAUNCHER=ccache",
            "-e", "CMAKE_CXX_COMPILER_LAUNCHER=ccache",
        ])

        # Image and command
        docker_cmd.append(image)
        docker_cmd.extend(cmd)

        return docker_cmd

    def _kill_container(self, container_name: str):
        """Force-kill a running builder container."""
        try:
            subprocess.run(
                ["docker", "kill", container_name],
                capture_output=True, timeout=10,
            )
            log.info("Killed container %s", container_name)
        except Exception as e:
            log.warning("Failed to kill container %s: %s", container_name, e)

    def cleanup(self):
        """Cleanup any running builder container (called on shutdown)."""
        if self._current_container:
            log.info("Shutting down — cleaning up container %s", self._current_container)
            self._kill_container(self._current_container)
