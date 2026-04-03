"""Git poller configuration."""

import os


class GitPollerConfig:
    """Config loaded from environment variables."""

    def __init__(self):
        self.api_url = os.environ.get("CONCORD_API_URL", "http://localhost:9001")
        self.api_key = os.environ.get("CONCORD_API_KEY", "")
        self.poll_interval = int(os.environ.get("POLL_INTERVAL", "30"))
        self.ssh_key_path = os.environ.get("SSH_KEY_PATH", "/root/.ssh/keys/bitbucket")
        self.bitbucket_ssh_key = os.environ.get("BITBUCKET_SSH_KEY", "")
        self.service_port = int(os.environ.get("SERVICE_PORT", "9003"))
        self.environment = os.environ.get("ENVIRONMENT", "development")
