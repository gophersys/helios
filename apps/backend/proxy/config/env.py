from corekinect.utils import EnvConfig
from typing import List


# -------------------------------------------------
#                                        Env Config
# -------------------------------------------------
class ProxyConfig(EnvConfig):
    DELETE_ALL_KEY: str
    LOG_LEVEL: int
    LOG_PATH: str
    SERVER_PORT: int
    DB_STORAGE_PATH: str
    DB_STORAGE_LIMIT_GB: int
    SUPPORTED_REGISTRIES: List[str]
    AUTH_ENABLED: bool
    AUTH_SERVER_URL: str
    AUTH_SERVER_API_KEY: str
    AUTH_SERVER_CREDENTIALS_USER: str
    AUTH_SERVER_CREDENTIALS_PASS: str
    MANU_SERVER_URL: str


env_config = ProxyConfig()
