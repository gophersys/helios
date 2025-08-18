from corekinect.utils import EnvConfig


class AlphaEnvConfig(EnvConfig):
    LOG_LEVEL: int
    LOG_PATH: str

    # MTIB server
    MTIB_SERVER_HOST: str
    MTIB_SERVER_PORT: int

    # Concord proxy server
    PROXY_SERVER_URL: str

    # Assets directory
    ASSETS_DIR: str

    # Firmware file names
    MODEM_FW_FILE: str
    COMMS_COPROC_FW_FILE: str
    APP_PROC_FW_FILE: str
