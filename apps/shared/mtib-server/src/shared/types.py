# Import all request/response types from the generated protobuf
from protocols.mtib.mtib_pb2 import (
    # Shared types
    Empty,
    # Health Check
    HealthCheckResponse,
    # GPIO types
    GpioDirection,
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
    ProgrammerType,
    HostType,
    Programmer,
    FwFileInfo,
    ListProgrammersResponse,
    ListFwFilesResponse,
    UploadFwFileRequest,
    UploadFwFileResponse,
    DeleteFwFileRequest,
    DeleteFwFileResponse,
    FlashFwFileRequest,
    FlashFwFileResponse,
    EnableAppProtectRequest,
    EnableAppProtectResponse,
    # UART types
    UartStreamRequest,
    UartStreamResponse,
)

# Import gRPC service types
from protocols.mtib.mtib_pb2_grpc import (
    MtibV1Servicer,
    MtibV1Stub,
)
