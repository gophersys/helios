# Import all request/response types from the generated protobuf
from protocols.mtib.mtib_pb2 import (
    # Shared types
    Empty,
    Component,

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

# Import gRPC service types
from protocols.mtib.mtib_pb2_grpc import (
    MtibV1Servicer,
    MtibV1Stub,
)