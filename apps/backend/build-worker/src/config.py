"""Build worker configuration."""

import os
import socket
from dataclasses import dataclass


@dataclass
class BuildConfig:
    """Configuration loaded from environment variables."""
    api_url: str
    api_key: str
    worker_id: str
    poll_interval: int
    workspace_dir: str
    ssh_key_path: str
    ncs_version: str | None  # Filter for specific NCS version (e.g., "2.7.0")

    @classmethod
    def from_env(cls) -> "BuildConfig":
        return cls(
            api_url=os.environ.get("CONCORD_API_URL", "https://staging.concord.local"),
            api_key=os.environ.get("CONCORD_API_KEY", ""),
            worker_id=os.environ.get("WORKER_ID", socket.gethostname()),
            poll_interval=int(os.environ.get("POLL_INTERVAL", "5")),
            workspace_dir=os.environ.get("WORKSPACE_DIR", "/tmp/builds"),
            ssh_key_path=os.environ.get("SSH_KEY_PATH", "/root/.ssh/id_rsa"),
            ncs_version=os.environ.get("NCS_VERSION"),
        )
