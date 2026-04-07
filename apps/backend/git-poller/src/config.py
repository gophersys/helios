"""Git poller configuration — loaded from environment variables."""

from corekinect.utils import EnvConfig


class GitPollerConfig(EnvConfig):
    """Config loaded from environment variables.

    All fields match env var names exactly (case-insensitive).
    """

    ENVIRONMENT: str = "development"
    CONCORD_API_URL: str = "http://localhost:9001"
    CONCORD_API_KEY: str = ""
    POLL_INTERVAL: int = 5
    PRODUCT_CACHE_TTL: int = 60
    SERVICE_PORT: int = 9003
    SSH_KEY_PATH: str = "/root/.ssh/id_rsa"
    BITBUCKET_SSH_KEY: str = ""          # base64-encoded, written to SSH_KEY_PATH
    BITBUCKET_WORKSPACE: str = "corekinect"
    BITBUCKET_API_TOKEN: str = ""        # for Bitbucket REST API
    BITBUCKET_EMAIL: str = ""            # for Bitbucket REST API Basic auth
    # Note: poller state is persisted via the Concord API (PollCache model),
    # not a local file. CONCORD_API_URL + CONCORD_API_KEY are used for state I/O.

    # Lowercase property aliases used throughout the codebase
    @property
    def environment(self) -> str:
        return self.ENVIRONMENT

    @property
    def concord_api_url(self) -> str:
        return self.CONCORD_API_URL

    @property
    def concord_api_key(self) -> str:
        return self.CONCORD_API_KEY

    @property
    def poll_interval(self) -> int:
        return self.POLL_INTERVAL

    @property
    def product_cache_ttl(self) -> int:
        return self.PRODUCT_CACHE_TTL

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
    def bitbucket_workspace(self) -> str:
        return self.BITBUCKET_WORKSPACE

    @property
    def bitbucket_api_token(self) -> str:
        return self.BITBUCKET_API_TOKEN

    @property
    def bitbucket_email(self) -> str:
        return self.BITBUCKET_EMAIL
