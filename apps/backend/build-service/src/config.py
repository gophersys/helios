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
        return self.ENVIRONMENT

    @property
    def api_url(self) -> str:
        return self.CONCORD_API_URL

    @property
    def api_key(self) -> str:
        return self.CONCORD_API_KEY

    @property
    def worker_id(self) -> str:
        return self.WORKER_ID

    @property
    def poll_interval(self) -> int:
        return self.POLL_INTERVAL

    @property
    def workspace_dir(self) -> str:
        return self.WORKSPACE_DIR

    @property
    def service_port(self) -> int:
        return self.BUILD_SERVICE_PORT

    @property
    def metrics_enabled(self) -> bool:
        return self.METRICS_ENABLED

    @property
    def builder_mode(self) -> str:
        return self.BUILDER_MODE

    @property
    def docker_socket(self) -> str:
        return self.DOCKER_SOCKET

    @property
    def builder_timeout(self) -> int:
        return self.BUILDER_TIMEOUT

    @property
    def default_builder_image(self) -> str:
        return self.DEFAULT_BUILDER_IMAGE

    @property
    def workspace_volume(self) -> str:
        return self.WORKSPACE_VOLUME

    @property
    def ccache_volume(self) -> str:
        return self.CCACHE_VOLUME

    @property
    def builder_network(self) -> str:
        return self.BUILDER_NETWORK

    @property
    def ssh_key_path(self) -> str:
        return self.SSH_KEY_PATH

    @property
    def bitbucket_ssh_key(self) -> str:
        return self.BITBUCKET_SSH_KEY

    @property
    def bench_signing_key(self) -> str:
        return self.BENCH_SIGNING_KEY

    @property
    def engineering_signing_key(self) -> str:
        return self.ENGINEERING_SIGNING_KEY

    @property
    def production_signing_key(self) -> str:
        return self.PRODUCTION_SIGNING_KEY

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
