# Standard includes
from dataclasses import dataclass
from enum import IntEnum

# Protocol includes
from protocols.mtib.mtib_pb2 import (
    Empty,
    GetRunnerInfoResponse,
    GpioConfigRequest,
    GpioWriteRequest,
    GpioReadRequest,
    # Motion
    MotionStatus,
    GetMotionStatusResponse,
    MotionHomeResponse,
    GcodeRequest,
    GcodeResponse,
    MotionProfileRequest,
    MotionProfileResponse,
    ListMotionProfilesResponse,
    ExecuteProfileRequest,
    ExecuteProfileResponse,
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
