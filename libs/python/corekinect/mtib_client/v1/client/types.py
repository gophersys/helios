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
    # Power types
    DutPowerRequest,
    DutPowerResponse,
    DutPowerReadResponse,
    # Sensor types
    AltimeterReadResponse,
    AccelReadResponse,
    # FluidNC types
    FluidNcConfigResponse,
    UpdateFluidNcConfigRequest,
    UpdateFluidNcConfigResponse,
    # Motion types
    MotionStatus,
    MotionPosition,
    GetMotionStatusResponse,
    MotionStartResponse,
    MotionHomeResponse,
    MotionStopResponse,
    GcodeRequest,
    GcodeResponse,
    # Motion Profile types
    MotionProfileRequest,
    MotionProfileResponse,
    ListMotionProfilesResponse,
    ExecuteProfileRequest,
    ExecuteProfileResponse,
    DeleteProfileRequest,
    DeleteProfileResponse,
    SetDefaultProfileRequest,
    SetDefaultProfileResponse,
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
    # UART types
    UartStreamRequest,
    UartStreamResponse,
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
class DutPowerResponse:
    success: bool = False
    message: str = ""


@dataclass
class DutPowerReadResponse:
    success: bool = False
    message: str = ""
    current_a: float = 0.0
    voltage_v: float = 0.0
    power_w: float = 0.0


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
    position: MotionPosition = MotionPosition.UNDEFINED


@dataclass
class MotionHomeResponse:
    success: bool = False
    message: str = ""


@dataclass
class MotionStopResponse:
    success: bool = False
    message: str = ""


@dataclass
class MotionProfile:
    name: str = ""
    description: str = ""
    gcode_commands: List[str] = None


@dataclass
class MotionProfileRequest:
    profile: MotionProfile = None


@dataclass
class MotionProfileResponse:
    success: bool = False
    message: str = ""


@dataclass
class ListMotionProfilesResponse:
    profiles: List[MotionProfile] = None


@dataclass
class ExecuteProfileRequest:
    profile_name: str = ""


@dataclass
class ExecuteProfileResponse:
    success: bool = False
    message: str = ""


@dataclass
class FluidNcConfigResponse:
    success: bool = False
    message: str = ""
    config_yaml: str = ""


@dataclass
class UpdateFluidNcConfigRequest:
    config_yaml: str = ""


@dataclass
class UpdateFluidNcConfigResponse:
    success: bool = False
    message: str = ""


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