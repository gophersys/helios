"""Build service configuration."""

import socket

from corekinect.utils import EnvConfig


class BuildServiceConfig(EnvConfig):
    """Configuration loaded from environment variables.

    All fields match env var names exactly (case-insensitive).
    """

    ENVIRONMENT: str = "development"
    CONCORD_API_URL: str = "https://staging.concord.local"
    CONCORD_API_KEY: str = ""
    WORKER_ID: str = socket.gethostname()
    POLL_INTERVAL: int = 60
    WORKSPACE_DIR: str = "/tmp/builds"
    BUILD_SERVICE_PORT: int = 9002
    METRICS_ENABLED: bool = True

    # Docker build runner — spawns builds in dynamic product-specific containers
    BUILDER_MODE: str = "docker"
    DOCKER_SOCKET: str = "/var/run/docker.sock"
    BUILDER_TIMEOUT: int = 1800
    DEFAULT_BUILDER_IMAGE: str = "containers.ad.corekinect.com/ncs-fw-dev:2.7.0"
    WORKSPACE_VOLUME: str = ""
    CCACHE_VOLUME: str = ""
    BUILDER_NETWORK: str = "host"

    # SSH key for git operations
    SSH_KEY_PATH: str = "/root/.ssh/id_rsa"
    BITBUCKET_SSH_KEY: str = ""  # Base64-encoded, decoded to SSH_KEY_PATH at startup

    # Signing keys per release track (base64-encoded private keys)
    BENCH_SIGNING_KEY: str = ""
    ENGINEERING_SIGNING_KEY: str = ""
    PRODUCTION_SIGNING_KEY: str = ""

    # Lowercase property aliases used throughout the codebase
    @property
    def environment(self) -> str:
        """Deployment environment name (e.g., ``development``, ``staging``)."""
        return self.ENVIRONMENT

    @property
    def api_url(self) -> str:
        """Base URL of the Concord HTTP API."""
        return self.CONCORD_API_URL

    @property
    def api_key(self) -> str:
        """API key used to authenticate with the Concord HTTP API."""
        return self.CONCORD_API_KEY

    @property
    def worker_id(self) -> str:
        """Unique identifier for this worker instance (defaults to hostname)."""
        return self.WORKER_ID

    @property
    def poll_interval(self) -> int:
        """Seconds between polling cycles when the job queue is empty."""
        return self.POLL_INTERVAL

    @property
    def workspace_dir(self) -> str:
        """Root directory for temporary build workspaces."""
        return self.WORKSPACE_DIR

    @property
    def service_port(self) -> int:
        """TCP port the Flask API server listens on."""
        return self.BUILD_SERVICE_PORT

    @property
    def metrics_enabled(self) -> bool:
        """Whether the Prometheus metrics endpoint is active."""
        return self.METRICS_ENABLED

    @property
    def builder_mode(self) -> str:
        """Build execution mode: ``docker`` (default) or ``local``."""
        return self.BUILDER_MODE

    @property
    def docker_socket(self) -> str:
        """Path to the Docker daemon socket used for spawning build containers."""
        return self.DOCKER_SOCKET

    @property
    def builder_timeout(self) -> int:
        """Maximum seconds a single build container may run before being killed."""
        return self.BUILDER_TIMEOUT

    @property
    def default_builder_image(self) -> str:
        """Fallback Docker image used when a repo has no devcontainer.json."""
        return self.DEFAULT_BUILDER_IMAGE

    @property
    def workspace_volume(self) -> str:
        """Named Docker volume mounted at ``/workspace`` inside build containers."""
        return self.WORKSPACE_VOLUME

    @property
    def ccache_volume(self) -> str:
        """Named Docker volume mounted as the ccache directory in build containers."""
        return self.CCACHE_VOLUME

    @property
    def builder_network(self) -> str:
        """Docker network mode for build containers (e.g., ``host``)."""
        return self.BUILDER_NETWORK

    @property
    def ssh_key_path(self) -> str:
        """Filesystem path to the SSH private key used for git clone operations."""
        return self.SSH_KEY_PATH

    @property
    def bitbucket_ssh_key(self) -> str:
        """Base64-encoded SSH private key decoded to ``ssh_key_path`` at startup."""
        return self.BITBUCKET_SSH_KEY

    @property
    def bench_signing_key(self) -> str:
        """Base64-encoded MCUboot signing key for bench-track builds."""
        return self.BENCH_SIGNING_KEY

    @property
    def engineering_signing_key(self) -> str:
        """Base64-encoded MCUboot signing key for engineering-track builds."""
        return self.ENGINEERING_SIGNING_KEY

    @property
    def production_signing_key(self) -> str:
        """Base64-encoded MCUboot signing key for production-track builds."""
        return self.PRODUCTION_SIGNING_KEY

    @property
    def service_name(self) -> str:
        """Canonical service name used in logging and banners."""
        return "build-service"

    def signing_key_for_track(self, track: str) -> str:
        """Get the base64-encoded signing key for a release track."""
        keys = {
            "bench": self.bench_signing_key,
            "engineering": self.engineering_signing_key,
            "production": self.production_signing_key,
        }
        return keys.get(track, self.bench_signing_key)
