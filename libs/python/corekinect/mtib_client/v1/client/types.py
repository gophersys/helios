# Standard includes
from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional

# Protocol includes
from protocols.mtib.mtib_pb2 import (
    # Shared types
    Empty,
    # Health Check
    HealthCheckResponse,
    # GPIO types
    GpioConfigRequest,
    GpioConfigResponse,
    GpioWriteRequest,
    GpioWriteResponse,
    GpioReadRequest,
    GpioReadResponse,
    # ADC types
    AdcReadRequest,
    AdcReadResponse,
    AdcReadAllResponse,
    # Sensor types
    AltimeterReadResponse,
    AccelReadResponse,
    # Motion types
    MotionStatus,
    GetMotionStatusResponse,
    MotionStartRequest,
    MotionStartResponse,
    MotionHomeResponse,
    MotionStopResponse,
    # Firmware types
    HostType,
    FwFileInfo,
    ListProgrammersResponse,
    ListFwFilesResponse,
    UploadFwFileRequest,
    UploadFwFileResponse,
    DeleteFwFileRequest,
    DeleteFwFileResponse,
    FlashFwFileRequest,
    FlashFwFileResponse,
    EraseFlashRequest,
    EraseFlashResponse,
    EnableAppProtectRequest,
    EnableAppProtectResponse,
    # UART types
    UartStreamRequest,
    UartStreamResponse,
    # Power types
    PowerChannel,
    PowerResponse as PowerResponseProto,
    PowerEnableRequest,
    PowerDisableRequest,
    PowerReadRequest,
    PowerReadResponse as PowerReadResponseProto,
    PowerMeasureRequest,
    PowerMeasureResponse as PowerMeasureResponseProto,
    PowerSample,
    PowerStreamRequest,
    PowerStreamResponse,
    # GPIO watch types
    GpioEdge,
    GpioWatchRequest,
    GpioWatchEvent,
    # ADC stream types
    AdcStreamRequest,
    AdcStreamSample,
    AdcStreamResponse,
    # Observability types
    GetSnapshotResponse as GetSnapshotResponseProto,
    SnapshotPower,
    SnapshotGpio,
    SnapshotAdc,
)


@dataclass
class Hardware:
    adc_count: int = 0
    gpio_count: int = 0
    j_link_count: int = 0


@dataclass
class MtibV1ServerInfo:
    name: str = ""
    version: str = ""
    hardware: Hardware = None


class PowerChannel(IntEnum):
    DUT = 0           # POWER_CHANNEL_DUT
    CHARGER = 1       # POWER_CHANNEL_CHARGER
    JOULESCOPE = 2    # POWER_CHANNEL_JOULESCOPE (optional USB power analyzer)


class GpioDirection(IntEnum):
    UNDEFINED = 0
    INPUT = 1
    OUTPUT = 2


class GpioResistorConfig(IntEnum):
    UNDEFINED = 0
    PULL_UP = 1
    PULL_DOWN = 2
    NONE = 3


class MotionStatus(IntEnum):
    UNDEFINED = 0
    IDLE = 1
    MOVING = 2
    ERRORED = 3


class MotionPosition(IntEnum):
    UNDEFINED = 0
    HOME = 1
    USER = 2


@dataclass
class HealthCheckResponse:
    ready: bool = False
    errors: List[str] = None


@dataclass
class GpioReadResponse:
    success: bool = False
    message: str = ""
    state: bool = False


@dataclass
class AdcReadResponse:
    success: bool = False
    message: str = ""
    voltage_v: float = 0.0


@dataclass
class AdcReadAllResponse:
    success: bool = False
    message: str = ""
    voltages_v: List[float] = None


@dataclass
class AltimeterReadResponse:
    success: bool = False
    message: str = ""
    temperature_f: float = 0.0
    pressure_hg: float = 0.0
    altitude_ft: float = 0.0


@dataclass
class AccelReadResponse:
    success: bool = False
    message: str = ""
    x_g: float = 0.0
    y_g: float = 0.0
    z_g: float = 0.0


@dataclass
class GetMotionStatusResponse:
    success: bool = False
    message: str = ""
    status: MotionStatus = MotionStatus.UNDEFINED


@dataclass
class MotionHomeResponse:
    success: bool = False
    message: str = ""


@dataclass
class MotionStopResponse:
    success: bool = False
    message: str = ""


@dataclass
class ProgrammerType(IntEnum):
    UNDEFINED = 0
    JLINK = 1
    BLACKMAGIC = 2


@dataclass
class Programmer:
    type: ProgrammerType = ProgrammerType.UNDEFINED
    host: HostType = HostType.HOST_TYPE_NRF9160_MODEM


@dataclass
class ListProgrammersResponse:
    success: bool = False
    message: str = ""
    programmers: List[Programmer] = None


@dataclass
class ListFwFilesResponse:
    success: bool = False
    message: str = ""
    files: List[FwFileInfo] = None


@dataclass
class UploadFwFileResponse:
    success: bool = False
    message: str = ""
    sha256_digest: str = ""


@dataclass
class DeleteFwFileResponse:
    success: bool = False
    message: str = ""


@dataclass
class FlashFwFileResponse:
    success: bool = False
    message: str = ""
    time_ms: int = 0


@dataclass
class HealthCheckExtendedResponse:
    ready: bool = False
    errors: List[str] = None
    hw_revision: str = ""
    capabilities: List[str] = None


@dataclass
class PowerReadResult:
    enabled: bool = False
    voltage_v: float = 0.0
    current_ma: float = 0.0
    power_mw: float = 0.0
    current_na: float = 0.0  # Nanoamp resolution (Joulescope only)


@dataclass
class PowerMeasureResult:
    duration_s: float = 0.0
    average_ma: float = 0.0
    min_ma: float = 0.0
    max_ma: float = 0.0
    average_mv: float = 0.0
    sample_count: int = 0
    average_na: float = 0.0  # Nanoamp resolution (Joulescope only)
    min_na: float = 0.0
    max_na: float = 0.0


@dataclass
class SnapshotResult:
    timestamp_ms: int = 0
    hw_revision: str = ""
    power: list = None
    gpio: list = None
    adc: list = None
