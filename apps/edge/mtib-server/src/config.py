"""MTIB server configuration."""

from dataclasses import dataclass

from corekinect.utils import EnvConfig

from src.drivers.gpio import Pin


# Environment configuration (loaded from env vars)
class MtibEnvConfig(EnvConfig):
    HARDWARE_VERSION: str
    LOG_LEVEL: int
    LOG_PATH: str
    SERVER_PORT: int
    ASSETS_PATH: str
    METRICS_ENABLED: bool
    METRICS_BROKER_URL: str
    MOTION_ENABLED: bool


# Provider configuration
@dataclass
class MtibV1ProviderConfig:
    HARDWARE_VERSION: str
    ASSETS_DIR: str
    METRICS_ENABLED: bool
    METRICS_BROKER_URL: str
    MOTION_ENABLED: bool


# GPIO pin map (REV 1.2)
GPIO_PIN_MAP = {
    0: Pin.SODIMM_206,
    1: Pin.SODIMM_208,
    2: Pin.SODIMM_210,
    3: Pin.SODIMM_212,
    4: Pin.SODIMM_34,
    5: Pin.SODIMM_30,
    6: Pin.SODIMM_32,
    7: Pin.SODIMM_15,
    8: Pin.SODIMM_16,
}

FLUIDNC_SERIAL_PORT = "/dev/ttyUSB0"
FLUIDNC_RESET_PIN = Pin.SODIMM_36
