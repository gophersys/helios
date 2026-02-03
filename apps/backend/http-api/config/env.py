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

    # V1 Database
    DB_STORAGE_PATH: str
    DB_STORAGE_LIMIT_GB: int

    # V1 Registry
    SUPPORTED_REGISTRIES: List[str]

    # Auth (Google OAuth)
    GOOGLE_CLIENT_ID: str = ""
    JWT_SECRET_KEY: str = "concord-dev-jwt-secret-change-in-production"

    # Core Cloud/Ops
    COREOPS_SERVER_URL: str

    # Assets
    ASSETS_FOLDER: str

    # Storage (MinIO/S3)
    STORAGE_URL: str
    STORAGE_ACCESS_KEY: str
    STORAGE_SECRET_ACCESS_KEY: str
    STORAGE_FIRMWARE_BUCKET_NAME: str


env_config = ProxyConfig(namespace=None, auto_load_env=True)
