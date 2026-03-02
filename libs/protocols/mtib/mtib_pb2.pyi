from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GpioDirection(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    GPIO_DIRECTION_UNDEFINED: _ClassVar[GpioDirection]
    GPIO_DIRECTION_INPUT: _ClassVar[GpioDirection]
    GPIO_DIRECTION_OUTPUT: _ClassVar[GpioDirection]

class GpioResistorConfig(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    GPIO_RESISTOR_UNDEFINED: _ClassVar[GpioResistorConfig]
    GPIO_RESISTOR_PULL_UP: _ClassVar[GpioResistorConfig]
    GPIO_RESISTOR_PULL_DOWN: _ClassVar[GpioResistorConfig]
    GPIO_RESISTOR_NONE: _ClassVar[GpioResistorConfig]

class GpioEdge(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    GPIO_EDGE_RISING: _ClassVar[GpioEdge]
    GPIO_EDGE_FALLING: _ClassVar[GpioEdge]
    GPIO_EDGE_BOTH: _ClassVar[GpioEdge]

class PowerChannel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    POWER_CHANNEL_DUT: _ClassVar[PowerChannel]
    POWER_CHANNEL_CHARGER: _ClassVar[PowerChannel]

class MotionStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    MOTION_STATUS_UNDEFINED: _ClassVar[MotionStatus]
    MOTION_STATUS_IDLE: _ClassVar[MotionStatus]
    MOTION_STATUS_MOVING: _ClassVar[MotionStatus]
    MOTION_STATUS_ERRORED: _ClassVar[MotionStatus]

class ProgrammerType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PROGRAMMER_TYPE_UNDEFINED: _ClassVar[ProgrammerType]
    PROGRAMMER_TYPE_JLINK: _ClassVar[ProgrammerType]
    PROGRAMMER_TYPE_BLACKMAGIC: _ClassVar[ProgrammerType]

class HostType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    HOST_TYPE_UNDEFINED: _ClassVar[HostType]
    HOST_TYPE_NRF9160: _ClassVar[HostType]
    HOST_TYPE_NRF9160_MODEM: _ClassVar[HostType]
    HOST_TYPE_NRF52840: _ClassVar[HostType]
    HOST_TYPE_NRF5340: _ClassVar[HostType]
    HOST_TYPE_NRF9151: _ClassVar[HostType]
    HOST_TYPE_NRF9151_MODEM: _ClassVar[HostType]
GPIO_DIRECTION_UNDEFINED: GpioDirection
GPIO_DIRECTION_INPUT: GpioDirection
GPIO_DIRECTION_OUTPUT: GpioDirection
GPIO_RESISTOR_UNDEFINED: GpioResistorConfig
GPIO_RESISTOR_PULL_UP: GpioResistorConfig
GPIO_RESISTOR_PULL_DOWN: GpioResistorConfig
GPIO_RESISTOR_NONE: GpioResistorConfig
GPIO_EDGE_RISING: GpioEdge
GPIO_EDGE_FALLING: GpioEdge
GPIO_EDGE_BOTH: GpioEdge
POWER_CHANNEL_DUT: PowerChannel
POWER_CHANNEL_CHARGER: PowerChannel
MOTION_STATUS_UNDEFINED: MotionStatus
MOTION_STATUS_IDLE: MotionStatus
MOTION_STATUS_MOVING: MotionStatus
MOTION_STATUS_ERRORED: MotionStatus
PROGRAMMER_TYPE_UNDEFINED: ProgrammerType
PROGRAMMER_TYPE_JLINK: ProgrammerType
PROGRAMMER_TYPE_BLACKMAGIC: ProgrammerType
HOST_TYPE_UNDEFINED: HostType
HOST_TYPE_NRF9160: HostType
HOST_TYPE_NRF9160_MODEM: HostType
HOST_TYPE_NRF52840: HostType
HOST_TYPE_NRF5340: HostType
HOST_TYPE_NRF9151: HostType
HOST_TYPE_NRF9151_MODEM: HostType

class Empty(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HealthCheckResponse(_message.Message):
    __slots__ = ("ready", "errors", "hw_revision", "capabilities")
    READY_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    HW_REVISION_FIELD_NUMBER: _ClassVar[int]
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    ready: bool
    errors: _containers.RepeatedScalarFieldContainer[str]
    hw_revision: str
    capabilities: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, ready: bool = ..., errors: _Optional[_Iterable[str]] = ..., hw_revision: _Optional[str] = ..., capabilities: _Optional[_Iterable[str]] = ...) -> None: ...

class GpioConfigRequest(_message.Message):
    __slots__ = ("gpio", "direction", "resistor")
    GPIO_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    RESISTOR_FIELD_NUMBER: _ClassVar[int]
    gpio: int
    direction: GpioDirection
    resistor: GpioResistorConfig
    def __init__(self, gpio: _Optional[int] = ..., direction: _Optional[_Union[GpioDirection, str]] = ..., resistor: _Optional[_Union[GpioResistorConfig, str]] = ...) -> None: ...

class GpioConfigResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...

class GpioWriteRequest(_message.Message):
    __slots__ = ("gpio", "state")
    GPIO_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    gpio: int
    state: bool
    def __init__(self, gpio: _Optional[int] = ..., state: bool = ...) -> None: ...

class GpioWriteResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...

class GpioReadRequest(_message.Message):
    __slots__ = ("gpio",)
    GPIO_FIELD_NUMBER: _ClassVar[int]
    gpio: int
    def __init__(self, gpio: _Optional[int] = ...) -> None: ...

class GpioReadResponse(_message.Message):
    __slots__ = ("success", "message", "state")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    state: bool
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., state: bool = ...) -> None: ...

class GpioWatchRequest(_message.Message):
    __slots__ = ("gpio", "edge")
    GPIO_FIELD_NUMBER: _ClassVar[int]
    EDGE_FIELD_NUMBER: _ClassVar[int]
    gpio: int
    edge: GpioEdge
    def __init__(self, gpio: _Optional[int] = ..., edge: _Optional[_Union[GpioEdge, str]] = ...) -> None: ...

class GpioWatchEvent(_message.Message):
    __slots__ = ("gpio", "state", "timestamp_ms")
    GPIO_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_MS_FIELD_NUMBER: _ClassVar[int]
    gpio: int
    state: bool
    timestamp_ms: int
    def __init__(self, gpio: _Optional[int] = ..., state: bool = ..., timestamp_ms: _Optional[int] = ...) -> None: ...

class AdcReadRequest(_message.Message):
    __slots__ = ("channel",)
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    channel: int
    def __init__(self, channel: _Optional[int] = ...) -> None: ...

class AdcReadResponse(_message.Message):
    __slots__ = ("success", "message", "voltage_v")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    VOLTAGE_V_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    voltage_v: float
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., voltage_v: _Optional[float] = ...) -> None: ...

class AdcReadAllResponse(_message.Message):
    __slots__ = ("success", "message", "voltages_v")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    VOLTAGES_V_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    voltages_v: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., voltages_v: _Optional[_Iterable[float]] = ...) -> None: ...

class AdcStreamRequest(_message.Message):
    __slots__ = ("channels", "interval_ms")
    CHANNELS_FIELD_NUMBER: _ClassVar[int]
    INTERVAL_MS_FIELD_NUMBER: _ClassVar[int]
    channels: _containers.RepeatedScalarFieldContainer[int]
    interval_ms: int
    def __init__(self, channels: _Optional[_Iterable[int]] = ..., interval_ms: _Optional[int] = ...) -> None: ...

class AdcStreamSample(_message.Message):
    __slots__ = ("timestamp_ms", "channel", "voltage_v")
    TIMESTAMP_MS_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    VOLTAGE_V_FIELD_NUMBER: _ClassVar[int]
    timestamp_ms: int
    channel: int
    voltage_v: float
    def __init__(self, timestamp_ms: _Optional[int] = ..., channel: _Optional[int] = ..., voltage_v: _Optional[float] = ...) -> None: ...

class AdcStreamResponse(_message.Message):
    __slots__ = ("samples",)
    SAMPLES_FIELD_NUMBER: _ClassVar[int]
    samples: _containers.RepeatedCompositeFieldContainer[AdcStreamSample]
    def __init__(self, samples: _Optional[_Iterable[_Union[AdcStreamSample, _Mapping]]] = ...) -> None: ...

class PowerResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...

class PowerEnableRequest(_message.Message):
    __slots__ = ("channel", "voltage_v")
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    VOLTAGE_V_FIELD_NUMBER: _ClassVar[int]
    channel: PowerChannel
    voltage_v: float
    def __init__(self, channel: _Optional[_Union[PowerChannel, str]] = ..., voltage_v: _Optional[float] = ...) -> None: ...

class PowerDisableRequest(_message.Message):
    __slots__ = ("channel",)
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    channel: PowerChannel
    def __init__(self, channel: _Optional[_Union[PowerChannel, str]] = ...) -> None: ...

class PowerReadRequest(_message.Message):
    __slots__ = ("channel",)
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    channel: PowerChannel
    def __init__(self, channel: _Optional[_Union[PowerChannel, str]] = ...) -> None: ...

class PowerReadResponse(_message.Message):
    __slots__ = ("success", "message", "enabled", "voltage_v", "current_ma", "power_mw")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    VOLTAGE_V_FIELD_NUMBER: _ClassVar[int]
    CURRENT_MA_FIELD_NUMBER: _ClassVar[int]
    POWER_MW_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    enabled: bool
    voltage_v: float
    current_ma: float
    power_mw: float
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., enabled: bool = ..., voltage_v: _Optional[float] = ..., current_ma: _Optional[float] = ..., power_mw: _Optional[float] = ...) -> None: ...

class PowerMeasureRequest(_message.Message):
    __slots__ = ("channel", "duration_s")
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    DURATION_S_FIELD_NUMBER: _ClassVar[int]
    channel: PowerChannel
    duration_s: float
    def __init__(self, channel: _Optional[_Union[PowerChannel, str]] = ..., duration_s: _Optional[float] = ...) -> None: ...

class PowerMeasureResponse(_message.Message):
    __slots__ = ("success", "message", "duration_s", "average_ma", "min_ma", "max_ma", "average_mv", "sample_count")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DURATION_S_FIELD_NUMBER: _ClassVar[int]
    AVERAGE_MA_FIELD_NUMBER: _ClassVar[int]
    MIN_MA_FIELD_NUMBER: _ClassVar[int]
    MAX_MA_FIELD_NUMBER: _ClassVar[int]
    AVERAGE_MV_FIELD_NUMBER: _ClassVar[int]
    SAMPLE_COUNT_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    duration_s: float
    average_ma: float
    min_ma: float
    max_ma: float
    average_mv: float
    sample_count: int
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., duration_s: _Optional[float] = ..., average_ma: _Optional[float] = ..., min_ma: _Optional[float] = ..., max_ma: _Optional[float] = ..., average_mv: _Optional[float] = ..., sample_count: _Optional[int] = ...) -> None: ...

class PowerSample(_message.Message):
    __slots__ = ("timestamp_ms", "voltage_mv", "current_ma")
    TIMESTAMP_MS_FIELD_NUMBER: _ClassVar[int]
    VOLTAGE_MV_FIELD_NUMBER: _ClassVar[int]
    CURRENT_MA_FIELD_NUMBER: _ClassVar[int]
    timestamp_ms: int
    voltage_mv: float
    current_ma: float
    def __init__(self, timestamp_ms: _Optional[int] = ..., voltage_mv: _Optional[float] = ..., current_ma: _Optional[float] = ...) -> None: ...

class PowerStreamRequest(_message.Message):
    __slots__ = ("channel",)
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    channel: PowerChannel
    def __init__(self, channel: _Optional[_Union[PowerChannel, str]] = ...) -> None: ...

class PowerStreamResponse(_message.Message):
    __slots__ = ("samples",)
    SAMPLES_FIELD_NUMBER: _ClassVar[int]
    samples: _containers.RepeatedCompositeFieldContainer[PowerSample]
    def __init__(self, samples: _Optional[_Iterable[_Union[PowerSample, _Mapping]]] = ...) -> None: ...

class AltimeterReadResponse(_message.Message):
    __slots__ = ("success", "message", "temperature_f", "pressure_hg", "altitude_ft")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TEMPERATURE_F_FIELD_NUMBER: _ClassVar[int]
    PRESSURE_HG_FIELD_NUMBER: _ClassVar[int]
    ALTITUDE_FT_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    temperature_f: float
    pressure_hg: float
    altitude_ft: float
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., temperature_f: _Optional[float] = ..., pressure_hg: _Optional[float] = ..., altitude_ft: _Optional[float] = ...) -> None: ...

class AccelReadResponse(_message.Message):
    __slots__ = ("success", "message", "x_g", "y_g", "z_g")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    X_G_FIELD_NUMBER: _ClassVar[int]
    Y_G_FIELD_NUMBER: _ClassVar[int]
    Z_G_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    x_g: float
    y_g: float
    z_g: float
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., x_g: _Optional[float] = ..., y_g: _Optional[float] = ..., z_g: _Optional[float] = ...) -> None: ...

class MotionStartRequest(_message.Message):
    __slots__ = ("dwell_seconds", "accel_mm_s2", "speed_mm_s", "duration_seconds", "distance_mm")
    DWELL_SECONDS_FIELD_NUMBER: _ClassVar[int]
    ACCEL_MM_S2_FIELD_NUMBER: _ClassVar[int]
    SPEED_MM_S_FIELD_NUMBER: _ClassVar[int]
    DURATION_SECONDS_FIELD_NUMBER: _ClassVar[int]
    DISTANCE_MM_FIELD_NUMBER: _ClassVar[int]
    dwell_seconds: float
    accel_mm_s2: float
    speed_mm_s: float
    duration_seconds: float
    distance_mm: float
    def __init__(self, dwell_seconds: _Optional[float] = ..., accel_mm_s2: _Optional[float] = ..., speed_mm_s: _Optional[float] = ..., duration_seconds: _Optional[float] = ..., distance_mm: _Optional[float] = ...) -> None: ...

class MotionStartResponse(_message.Message):
    __slots__ = ("success", "message", "status", "time_elapsed_seconds", "distance_covered_mm", "distance_remaining_mm", "time_remaining_seconds", "target_duration_seconds", "target_distance_mm")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TIME_ELAPSED_SECONDS_FIELD_NUMBER: _ClassVar[int]
    DISTANCE_COVERED_MM_FIELD_NUMBER: _ClassVar[int]
    DISTANCE_REMAINING_MM_FIELD_NUMBER: _ClassVar[int]
    TIME_REMAINING_SECONDS_FIELD_NUMBER: _ClassVar[int]
    TARGET_DURATION_SECONDS_FIELD_NUMBER: _ClassVar[int]
    TARGET_DISTANCE_MM_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    status: MotionStatus
    time_elapsed_seconds: int
    distance_covered_mm: float
    distance_remaining_mm: float
    time_remaining_seconds: int
    target_duration_seconds: int
    target_distance_mm: int
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., status: _Optional[_Union[MotionStatus, str]] = ..., time_elapsed_seconds: _Optional[int] = ..., distance_covered_mm: _Optional[float] = ..., distance_remaining_mm: _Optional[float] = ..., time_remaining_seconds: _Optional[int] = ..., target_duration_seconds: _Optional[int] = ..., target_distance_mm: _Optional[int] = ...) -> None: ...

class MotionHomeResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...

class MotionStopResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...

class GetMotionStatusResponse(_message.Message):
    __slots__ = ("success", "message", "status", "time_elapsed_seconds", "distance_covered_mm", "distance_remaining_mm", "time_remaining_seconds", "target_duration_seconds", "target_distance_mm")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TIME_ELAPSED_SECONDS_FIELD_NUMBER: _ClassVar[int]
    DISTANCE_COVERED_MM_FIELD_NUMBER: _ClassVar[int]
    DISTANCE_REMAINING_MM_FIELD_NUMBER: _ClassVar[int]
    TIME_REMAINING_SECONDS_FIELD_NUMBER: _ClassVar[int]
    TARGET_DURATION_SECONDS_FIELD_NUMBER: _ClassVar[int]
    TARGET_DISTANCE_MM_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    status: MotionStatus
    time_elapsed_seconds: int
    distance_covered_mm: float
    distance_remaining_mm: float
    time_remaining_seconds: int
    target_duration_seconds: int
    target_distance_mm: int
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., status: _Optional[_Union[MotionStatus, str]] = ..., time_elapsed_seconds: _Optional[int] = ..., distance_covered_mm: _Optional[float] = ..., distance_remaining_mm: _Optional[float] = ..., time_remaining_seconds: _Optional[int] = ..., target_duration_seconds: _Optional[int] = ..., target_distance_mm: _Optional[int] = ...) -> None: ...

class Programmer(_message.Message):
    __slots__ = ("type", "host")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    HOST_FIELD_NUMBER: _ClassVar[int]
    type: ProgrammerType
    host: HostType
    def __init__(self, type: _Optional[_Union[ProgrammerType, str]] = ..., host: _Optional[_Union[HostType, str]] = ...) -> None: ...

class ListProgrammersResponse(_message.Message):
    __slots__ = ("success", "message", "programmers")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    PROGRAMMERS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    programmers: _containers.RepeatedCompositeFieldContainer[Programmer]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., programmers: _Optional[_Iterable[_Union[Programmer, _Mapping]]] = ...) -> None: ...

class FwFileInfo(_message.Message):
    __slots__ = ("name", "target", "size_b", "sha256_digest")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TARGET_FIELD_NUMBER: _ClassVar[int]
    SIZE_B_FIELD_NUMBER: _ClassVar[int]
    SHA256_DIGEST_FIELD_NUMBER: _ClassVar[int]
    name: str
    target: HostType
    size_b: int
    sha256_digest: str
    def __init__(self, name: _Optional[str] = ..., target: _Optional[_Union[HostType, str]] = ..., size_b: _Optional[int] = ..., sha256_digest: _Optional[str] = ...) -> None: ...

class ListFwFilesResponse(_message.Message):
    __slots__ = ("success", "message", "files")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    FILES_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    files: _containers.RepeatedCompositeFieldContainer[FwFileInfo]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., files: _Optional[_Iterable[_Union[FwFileInfo, _Mapping]]] = ...) -> None: ...

class UploadFwFileRequest(_message.Message):
    __slots__ = ("name", "target", "content")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TARGET_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    name: str
    target: HostType
    content: bytes
    def __init__(self, name: _Optional[str] = ..., target: _Optional[_Union[HostType, str]] = ..., content: _Optional[bytes] = ...) -> None: ...

class UploadFwFileResponse(_message.Message):
    __slots__ = ("success", "message", "sha256_digest")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SHA256_DIGEST_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    sha256_digest: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., sha256_digest: _Optional[str] = ...) -> None: ...

class DeleteFwFileRequest(_message.Message):
    __slots__ = ("file_info",)
    FILE_INFO_FIELD_NUMBER: _ClassVar[int]
    file_info: FwFileInfo
    def __init__(self, file_info: _Optional[_Union[FwFileInfo, _Mapping]] = ...) -> None: ...

class DeleteFwFileResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...

class FlashFwFileRequest(_message.Message):
    __slots__ = ("file_info", "sector_erase", "recover")
    FILE_INFO_FIELD_NUMBER: _ClassVar[int]
    SECTOR_ERASE_FIELD_NUMBER: _ClassVar[int]
    RECOVER_FIELD_NUMBER: _ClassVar[int]
    file_info: FwFileInfo
    sector_erase: bool
    recover: bool
    def __init__(self, file_info: _Optional[_Union[FwFileInfo, _Mapping]] = ..., sector_erase: bool = ..., recover: bool = ...) -> None: ...

class FlashFwFileResponse(_message.Message):
    __slots__ = ("success", "message", "time_ms")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TIME_MS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    time_ms: int
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., time_ms: _Optional[int] = ...) -> None: ...

class EnableAppProtectRequest(_message.Message):
    __slots__ = ("target",)
    TARGET_FIELD_NUMBER: _ClassVar[int]
    target: HostType
    def __init__(self, target: _Optional[_Union[HostType, str]] = ...) -> None: ...

class EnableAppProtectResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...

class EraseFlashRequest(_message.Message):
    __slots__ = ("target", "recover")
    TARGET_FIELD_NUMBER: _ClassVar[int]
    RECOVER_FIELD_NUMBER: _ClassVar[int]
    target: HostType
    recover: bool
    def __init__(self, target: _Optional[_Union[HostType, str]] = ..., recover: bool = ...) -> None: ...

class EraseFlashResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...

class SnapshotPower(_message.Message):
    __slots__ = ("channel", "enabled", "voltage_v", "current_ma")
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    VOLTAGE_V_FIELD_NUMBER: _ClassVar[int]
    CURRENT_MA_FIELD_NUMBER: _ClassVar[int]
    channel: PowerChannel
    enabled: bool
    voltage_v: float
    current_ma: float
    def __init__(self, channel: _Optional[_Union[PowerChannel, str]] = ..., enabled: bool = ..., voltage_v: _Optional[float] = ..., current_ma: _Optional[float] = ...) -> None: ...

class SnapshotGpio(_message.Message):
    __slots__ = ("gpio", "state")
    GPIO_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    gpio: int
    state: bool
    def __init__(self, gpio: _Optional[int] = ..., state: bool = ...) -> None: ...

class SnapshotAdc(_message.Message):
    __slots__ = ("channel", "voltage_v")
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    VOLTAGE_V_FIELD_NUMBER: _ClassVar[int]
    channel: int
    voltage_v: float
    def __init__(self, channel: _Optional[int] = ..., voltage_v: _Optional[float] = ...) -> None: ...

class GetSnapshotResponse(_message.Message):
    __slots__ = ("success", "message", "timestamp_ms", "hw_revision", "power", "gpio", "adc")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_MS_FIELD_NUMBER: _ClassVar[int]
    HW_REVISION_FIELD_NUMBER: _ClassVar[int]
    POWER_FIELD_NUMBER: _ClassVar[int]
    GPIO_FIELD_NUMBER: _ClassVar[int]
    ADC_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    timestamp_ms: int
    hw_revision: str
    power: _containers.RepeatedCompositeFieldContainer[SnapshotPower]
    gpio: _containers.RepeatedCompositeFieldContainer[SnapshotGpio]
    adc: _containers.RepeatedCompositeFieldContainer[SnapshotAdc]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., timestamp_ms: _Optional[int] = ..., hw_revision: _Optional[str] = ..., power: _Optional[_Iterable[_Union[SnapshotPower, _Mapping]]] = ..., gpio: _Optional[_Iterable[_Union[SnapshotGpio, _Mapping]]] = ..., adc: _Optional[_Iterable[_Union[SnapshotAdc, _Mapping]]] = ...) -> None: ...

class UartStreamRequest(_message.Message):
    __slots__ = ("target", "data")
    TARGET_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    target: HostType
    data: bytes
    def __init__(self, target: _Optional[_Union[HostType, str]] = ..., data: _Optional[bytes] = ...) -> None: ...

class UartStreamResponse(_message.Message):
    __slots__ = ("success", "message", "target", "data")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TARGET_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    target: HostType
    data: bytes
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., target: _Optional[_Union[HostType, str]] = ..., data: _Optional[bytes] = ...) -> None: ...

class NfcPollRequest(_message.Message):
    __slots__ = ("timeout_ms",)
    TIMEOUT_MS_FIELD_NUMBER: _ClassVar[int]
    timeout_ms: int
    def __init__(self, timeout_ms: _Optional[int] = ...) -> None: ...

class NfcPollResponse(_message.Message):
    __slots__ = ("success", "message", "tag_present", "uid")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TAG_PRESENT_FIELD_NUMBER: _ClassVar[int]
    UID_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    tag_present: bool
    uid: bytes
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., tag_present: bool = ..., uid: _Optional[bytes] = ...) -> None: ...

class NfcReadNdefRequest(_message.Message):
    __slots__ = ("timeout_ms",)
    TIMEOUT_MS_FIELD_NUMBER: _ClassVar[int]
    timeout_ms: int
    def __init__(self, timeout_ms: _Optional[int] = ...) -> None: ...

class NdefRecord(_message.Message):
    __slots__ = ("tnf", "type", "payload")
    TNF_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    tnf: int
    type: bytes
    payload: bytes
    def __init__(self, tnf: _Optional[int] = ..., type: _Optional[bytes] = ..., payload: _Optional[bytes] = ...) -> None: ...

class NfcReadNdefResponse(_message.Message):
    __slots__ = ("success", "message", "records")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    RECORDS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    records: _containers.RepeatedCompositeFieldContainer[NdefRecord]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., records: _Optional[_Iterable[_Union[NdefRecord, _Mapping]]] = ...) -> None: ...
