from typing import List

from corekinect.utils import EnvConfig


# -------------------------------------------------
#                                        Env Config
# -------------------------------------------------
class AppConfig(EnvConfig):
    ENVIRONMENT: str
    DELETE_ALL_KEY: str

    # Logging
    LOG_LEVEL: int
    LOG_PATH: str

    # Server
    SERVER_PORT: int

    # CORS — comma-separated list of allowed origins
    CORS_ORIGINS: str = "http://localhost:4200"

    # Auth — always enforced. API key or JWT required for all endpoints.
    # WARNING: The default JWT secret is for development only.
    # In production and staging, set JWT_SECRET_KEY to a strong, unique value (32+ chars).
    JWT_SECRET_KEY: str = "concord-dev-jwt-secret-change-in-production"

    # Core Cloud auth server (email/password login)
    AUTH_SERVER_URL: str = ""
    AUTH_SERVER_API_KEY: str = ""

    # Core Cloud/Ops
    COREOPS_PROXY_URL: str

    # Assets
    ASSETS_FOLDER: str

    # Storage (MinIO/S3)
    STORAGE_URL: str
    STORAGE_ACCESS_KEY: str
    STORAGE_SECRET_ACCESS_KEY: str
    STORAGE_BUCKET_NAME: str

    # Concord API host header for ingress routing (used in K8s validation jobs)
    CONCORD_API_HOST: str = "staging.concord.local"

    # Validation — MTIB gRPC port
    MTIB_PORT: int = 50053
    # Validation — K8s namespace for validation jobs (privileged namespace for hardware access)
    VALIDATION_NAMESPACE: str = "validation"

    # Bitbucket poller — polls repos for new commits to trigger builds
    BITBUCKET_POLLER_ENABLED: bool = True
    BITBUCKET_POLLER_INTERVAL_S: int = 300

    # Bitbucket — SSH private key (base64-encoded) for git operations
    BITBUCKET_SSH_KEY: str = ""
    # Bitbucket — API token for REST API (PR polling, repo operations)
    BITBUCKET_API_TOKEN: str = ""
    BITBUCKET_EMAIL: str = ""  # Email for Basic auth with API token
    BITBUCKET_WORKSPACE: str = "corekinect"

    # CkBoards — shared board definition repository
    CK_BOARDS_REPO_URL: str = "git@bitbucket.org:corekinect/ck_boards.git"
    CK_BOARDS_FETCH_INTERVAL: int = 60

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._validate()

    def _validate(self):
        _DEFAULT_SECRET = "concord-dev-jwt-secret-change-in-production"
        _is_deployed = self.ENVIRONMENT in ("production", "staging")

        # Fail fast: never allow the default dev JWT secret in production or staging
        if _is_deployed and self.JWT_SECRET_KEY == _DEFAULT_SECRET:
            raise RuntimeError(
                f"JWT_SECRET_KEY must be changed from the default value in {self.ENVIRONMENT}. "
                "Set the JWT_SECRET_KEY environment variable to a strong, unique secret."
            )

        # HS256 needs at least 256 bits (32 bytes) of key material
        if _is_deployed and len(self.JWT_SECRET_KEY) < 32:
            raise RuntimeError(
                f"JWT_SECRET_KEY is too short for {self.ENVIRONMENT} ({len(self.JWT_SECRET_KEY)} chars). "
                "HS256 requires a minimum of 32 characters. "
                "Set JWT_SECRET_KEY to a cryptographically random string of 32+ characters."
            )


env_config = AppConfig(namespace=None, auto_load_env=True)
