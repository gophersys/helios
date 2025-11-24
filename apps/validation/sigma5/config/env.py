from typing import List

from corekinect.utils import EnvConfig


# -------------------------------------------------
#                                        Env Config
# -------------------------------------------------
class Config(EnvConfig):
    ENVIRONMENT: str

    # Logging
    LOG_LEVEL: str
    LOG_PATH: str

    # Tests Enable Flags
    TEST_ENABLE_ELECTRICAL: bool
    TEST_ENABLE_APP_POST: bool
    TEST_ENABLE_COMM_POST: bool

    # Metadata
    PRODUCT: str
    FIRMWARE_BUCKET_FILE_PATH: str

    # Concord API
    CONCORD_API_URL: str

    # Storage (MinIO/S3)
    STORAGE_URL: str
    STORAGE_ACCESS_KEY: str
    STORAGE_SECRET_ACCESS_KEY: str

    # Logs
    LOKI_URL: str

    # MTIB
    MTIB_HOST: str
    MTIB_PORT: int


env_config = Config(namespace=None, auto_load_env=True)
