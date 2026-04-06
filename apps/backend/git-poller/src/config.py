"""Git poller configuration."""

from typing import Optional

from corekinect.utils import EnvConfig


class GitPollerConfig(EnvConfig):
    """Config loaded from environment variables."""

    ENVIRONMENT: str = "development"
    CONCORD_API_URL: str = "http://localhost:9001"
    CONCORD_API_KEY: str = ""
    POLL_INTERVAL: int = 30
    SERVICE_PORT: int = 9003
    SSH_KEY_PATH: str = "/root/.ssh/keys/bitbucket"
    BITBUCKET_SSH_KEY: str = ""

    # Aliases for backward compat with main.py field access
    @property
    def api_url(self) -> str:
        return self.CONCORD_API_URL

    @property
    def api_key(self) -> str:
        return self.CONCORD_API_KEY

    @property
    def poll_interval(self) -> int:
        return self.POLL_INTERVAL

    @property
    def service_port(self) -> int:
        return self.SERVICE_PORT

    @property
    def ssh_key_path(self) -> str:
        return self.SSH_KEY_PATH

    @property
    def bitbucket_ssh_key(self) -> str:
        return self.BITBUCKET_SSH_KEY

    @property
    def environment(self) -> str:
        return self.ENVIRONMENT
