"""Build service configuration."""

import os
import socket
from dataclasses import dataclass


@dataclass
class BuildServiceConfig:
    """Configuration loaded from environment variables."""
    environment: str
    api_url: str
    api_key: str
    worker_id: str
    poll_interval: int
    workspace_dir: str
    db_url: str
    service_port: int
    metrics_enabled: bool

    # Docker build runner — spawns builds in dynamic product-specific containers
    builder_mode: str            # "docker" (dynamic containers) or "local" (legacy in-process)
    docker_socket: str           # Path to Docker socket
    builder_timeout: int         # Max build time in seconds
    default_builder_image: str   # Fallback if devcontainer.json missing
    workspace_volume: str        # Docker volume name for build workspace
    ccache_volume: str           # Docker volume name for ccache
    builder_network: str         # Docker network for builder containers

    # SSH key for git operations
    ssh_key_path: str
    bitbucket_ssh_key: str       # Base64-encoded (decoded to ssh_key_path at startup)

    # Signing keys per release track (base64-encoded private keys)
    bench_signing_key: str
    engineering_signing_key: str
    production_signing_key: str

    @classmethod
    def from_env(cls) -> "BuildServiceConfig":
        return cls(
            environment=os.environ.get("ENVIRONMENT", "development"),
            api_url=os.environ.get("CONCORD_API_URL", "https://staging.concord.local"),
            api_key=os.environ.get("CONCORD_API_KEY", ""),
            worker_id=os.environ.get("WORKER_ID", socket.gethostname()),
            poll_interval=int(os.environ.get("POLL_INTERVAL", "5")),
            workspace_dir=os.environ.get("WORKSPACE_DIR", "/tmp/builds"),
            db_url=os.environ.get("BUILD_SERVICE_DATABASE_URL", ""),
            service_port=int(os.environ.get("BUILD_SERVICE_PORT", "9002")),
            metrics_enabled=os.environ.get("METRICS_ENABLED", "true").lower() in ("true", "1", "yes"),
            # Docker build runner
            builder_mode=os.environ.get("BUILDER_MODE", "docker"),
            docker_socket=os.environ.get("DOCKER_SOCKET", "/var/run/docker.sock"),
            builder_timeout=int(os.environ.get("BUILDER_TIMEOUT", "1800")),
            default_builder_image=os.environ.get(
                "DEFAULT_BUILDER_IMAGE",
                "containers.ad.corekinect.com/ncs-fw-dev:2.7.0",
            ),
            workspace_volume=os.environ.get("WORKSPACE_VOLUME", ""),
            ccache_volume=os.environ.get("CCACHE_VOLUME", ""),
            builder_network=os.environ.get("BUILDER_NETWORK", "host"),
            # SSH
            ssh_key_path=os.environ.get("SSH_KEY_PATH", "/root/.ssh/id_rsa"),
            bitbucket_ssh_key=os.environ.get("BITBUCKET_SSH_KEY", ""),
            # Signing keys
            bench_signing_key=os.environ.get("BENCH_SIGNING_KEY", ""),
            engineering_signing_key=os.environ.get("ENGINEERING_SIGNING_KEY", ""),
            production_signing_key=os.environ.get("PRODUCTION_SIGNING_KEY", ""),
        )

    @property
    def service_name(self) -> str:
        return "build-service"

    def signing_key_for_track(self, track: str) -> str:
        """Get the base64-encoded signing key for a release track."""
        keys = {
            "bench": self.bench_signing_key,
            "engineering": self.engineering_signing_key,
            "production": self.production_signing_key,
        }
        return keys.get(track, self.bench_signing_key)
