# Corekinec includes
from corekinect.utils import EnvConfig


class ServerEnvConfig(EnvConfig):
    MOCK_SERVER: bool

    # Server
    RUNNER_GRPC_SERVER_PORT: int

    # Cipher
    CIPHER_SERIAL_PORT: str
    CIPHER_SERIAL_BAUD: int
    CIPHER_SERVER_RESET_ENABLED: bool
    CIPHER_SERVER_RESET_GPIO: bool

    # Target Info
    PLATFORM: str
    HW_VERSION: str

    # Features
    FEATURE_DUT_POWER_ENABLED: bool
    FEATURE_MOTION_ENABLED: bool
    FEATURE_SENSOR_ACCEL_ENABLED: bool
    FEATURE_SENSOR_ALT_ENABLED: bool
    FEATURE_FW_FLASH_ENABLED: bool
    FEATURE_JOULESCOPE: bool

    # JLink
    JLINK_USB_BUS_ENABLE_GPIO: bool
    JLINK_HOST_NRF9160_USB_BUS: str
    JLINK_HOST_NRF52840_USB_BUS: str
    JLINK_HOST_NRF5340_USB_BUS: str
