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

    # Auth
    AUTH_ENABLED: bool
    AUTH_SERVER_URL: str
    AUTH_SERVER_API_KEY: str
    AUTH_SERVER_CREDENTIALS_USER: str
    AUTH_SERVER_CREDENTIALS_PASS: str

    # Core Cloud/Ops
    COREOPS_SERVER_URL: str


env_config = ProxyConfig(namespace=None, auto_load_env=True)
