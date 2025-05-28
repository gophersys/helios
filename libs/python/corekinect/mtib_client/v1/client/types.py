# Standard includes
from dataclasses import dataclass
from enum import IntEnum

# Protocol includes
from protocols.mtib.mtib_pb2 import (
    # Shared types
    Empty,
    # Health Check
    HealthCheckResponse,
    # GPIO types
    GpioDirection,
    GpioResistorConfig,
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
    GetMotionStatusRequest,
    GetMotionStatusResponse,
    MotionHomeResponse,
    MotionStopResponse,
    GcodeRequest,
    GcodeResponse,
    # Motion Profile types
    MotionProfile,
    MotionProfileRequest,
    MotionProfileResponse,
    ListMotionProfilesResponse,
    ExecuteProfileRequest,
    ExecuteProfileResponse,
    # Firmware types
    ProgrammerType,
    HostType,
    Programmer,
    ListProgrammersResponse,
    FwFileInfo,
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
    name: str = False
    version: str = False
    hardware: Hardware = None


class GpioDirection(IntEnum):
    UNDEFINED = 0
    INPUT = 1
    OUTPUT = 2


class GpioResistorConfig(IntEnum):
    UNDEFINED = 0
    NONE = 1
    PULL_UP = 2
    PULL_DOWN = 3


class MotionStatus(IntEnum):
    UNDEFINED = 0
    IDLE = 1
    MOVING = 2
    ERRORED = 3


@dataclass
class GetMotionStatusResponse:
    success: bool = False
    message: str = False
    status: MotionStatus = MotionStatus.UNDEFINED


@dataclass
class MotionHomeResponse:
    success: bool = False
    message: str = False


@dataclass
class MotionStopResponse:
    success: bool = False


@dataclass
class GcodeRequest:
    command: str = False


@dataclass
class GcodeResponse:
    success: bool = False
    message: str = False
    response: str = False


@dataclass
class MotionProfile:
    name: str = False
    description: str = False
    gcode_commands: list[str] = False


@dataclass
class MotionProfileRequest:
    profile: MotionProfile = None


@dataclass
class MotionProfileResponse:
    success: bool = False
    message: str = False


@dataclass
class ListMotionProfilesResponse:
    profiles: list[MotionProfile] = False


@dataclass
class ExecuteProfileRequest:
    profile_name: str = False


@dataclass
class ExecuteProfileResponse:
    success: bool = False
    message: str = False


@dataclass
class FluidConfigResponse:
    success: bool = False
    message: str = False
    yaml_content: str = False


@dataclass
class UpdateFluidConfigRequest:
    yaml_content: str = False


@dataclass
class UpdateFluidConfigResponse:
    success: bool = False
    message: str = False


# Firmware types
class ProgrammerType(IntEnum):
    UNDEFINED = 0
    JLINK = 1
    BLACKMAGIC = 2


class HostType(IntEnum):
    UNDEFINED = 0
    NRF9160 = 1
    NRF9160_MODEM = 2
    NRF52840 = 3
    NRF5340 = 4
    NRF9151 = 5


@dataclass
class Programmer:
    type: ProgrammerType = ProgrammerType.UNDEFINED
    host: HostType = HostType.UNDEFINED
