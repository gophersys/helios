"""Build service configuration."""

import os
import socket
from dataclasses import dataclass


@dataclass
class BuildServiceConfig:
    """Configuration loaded from environment variables."""
    api_url: str
    api_key: str
    worker_id: str
    poll_interval: int
    workspace_dir: str
    ncs_version: str | None
    db_url: str
    service_port: int
    metrics_enabled: bool

    # SSH key for git operations (base64-encoded)
    bitbucket_ssh_key: str

    # Signing keys per release track (base64-encoded private keys)
    # The build script receives the key path as SIGNING_KEY_PATH env var
    bench_signing_key: str      # Bench/dev signing key (may be in repo)
    engineering_signing_key: str # Engineering signing key (secret)
    production_signing_key: str  # Production signing key (secret)

    @classmethod
    def from_env(cls) -> "BuildServiceConfig":
        return cls(
            api_url=os.environ.get("CONCORD_API_URL", "https://staging.concord.local"),
            api_key=os.environ.get("CONCORD_API_KEY", ""),
            worker_id=os.environ.get("WORKER_ID", socket.gethostname()),
            poll_interval=int(os.environ.get("POLL_INTERVAL", "5")),
            workspace_dir=os.environ.get("WORKSPACE_DIR", "/tmp/builds"),
            ncs_version=os.environ.get("NCS_VERSION"),
            db_url=os.environ.get("BUILD_SERVICE_DATABASE_URL", ""),
            service_port=int(os.environ.get("BUILD_SERVICE_PORT", "9002")),
            metrics_enabled=os.environ.get("METRICS_ENABLED", "true").lower() in ("true", "1", "yes"),
            bitbucket_ssh_key=os.environ.get("BITBUCKET_SSH_KEY", ""),
            bench_signing_key=os.environ.get("BENCH_SIGNING_KEY", ""),
            engineering_signing_key=os.environ.get("ENGINEERING_SIGNING_KEY", ""),
            production_signing_key=os.environ.get("PRODUCTION_SIGNING_KEY", ""),
        )

    def signing_key_for_track(self, track: str) -> str:
        """Get the base64-encoded signing key for a release track."""
        keys = {
            "bench": self.bench_signing_key,
            "engineering": self.engineering_signing_key,
            "production": self.production_signing_key,
        }
        return keys.get(track, self.bench_signing_key)
