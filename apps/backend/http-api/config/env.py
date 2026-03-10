from typing import List

from corekinect.utils import EnvConfig


# -------------------------------------------------
#                                        Env Config
# -------------------------------------------------
class ProxyConfig(EnvConfig):
    ENVIRONMENT: str
    DELETE_ALL_KEY: str

    # Logging
    LOG_LEVEL: int
    LOG_PATH: str

    # Server
    SERVER_PORT: int

    # CORS — comma-separated list of allowed origins
    CORS_ORIGINS: str = "http://localhost:4200"

    # V1 Database
    DB_STORAGE_PATH: str
    DB_STORAGE_LIMIT_GB: int

    # V1 Registry
    SUPPORTED_REGISTRIES: List[str]

    # Auth
    AUTH_ENABLED: bool = True
    GOOGLE_CLIENT_ID: str = ""
    # WARNING: The default JWT secret is for development only.
    # In production, set JWT_SECRET_KEY to a strong, unique value.
    JWT_SECRET_KEY: str = "concord-dev-jwt-secret-change-in-production"

    # Core Cloud auth server (email/password login)
    AUTH_SERVER_URL: str = ""
    AUTH_SERVER_API_KEY: str = ""

    # Core Cloud/Ops
    COREOPS_SERVER_URL: str

    # Assets
    ASSETS_FOLDER: str

    # Storage (MinIO/S3)
    STORAGE_URL: str
    STORAGE_ACCESS_KEY: str
    STORAGE_SECRET_ACCESS_KEY: str
    STORAGE_BUCKET_NAME: str

    # InfluxDB
    INFLUXDB_URL: str
    INFLUXDB_TOKEN: str
    INFLUXDB_ORG: str
    INFLUXDB_BUCKET_TELEMETRY: str
    INFLUXDB_BUCKET_METRICS: str

    # Validation — MTIB gRPC port
    MTIB_PORT: int = 50053
    # Validation — K8s namespace for validation jobs (privileged namespace for hardware access)
    VALIDATION_NAMESPACE: str = "validation"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._validate()

    def _validate(self):
        # Fail fast: never allow the default dev JWT secret in production
        if (
            self.ENVIRONMENT == "production"
            and self.JWT_SECRET_KEY == "concord-dev-jwt-secret-change-in-production"
        ):
            raise RuntimeError(
                "JWT_SECRET_KEY must be changed from the default value in production. "
                "Set the JWT_SECRET_KEY environment variable to a strong, unique secret."
            )


env_config = ProxyConfig(namespace=None, auto_load_env=True)
