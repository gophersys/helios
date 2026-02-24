from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Architecture(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ARCH_UNKNOWN: _ClassVar[Architecture]
    ARCH_ARM_CORTEX_M0: _ClassVar[Architecture]
    ARCH_ARM_CORTEX_M0_PLUS: _ClassVar[Architecture]
    ARCH_ARM_CORTEX_M3: _ClassVar[Architecture]
    ARCH_ARM_CORTEX_M4: _ClassVar[Architecture]
    ARCH_ARM_CORTEX_M7: _ClassVar[Architecture]
    ARCH_ARM_CORTEX_M33: _ClassVar[Architecture]
    ARCH_ARM_CORTEX_M55: _ClassVar[Architecture]
    ARCH_ARM_CORTEX_A53: _ClassVar[Architecture]
    ARCH_RISCV_32: _ClassVar[Architecture]
    ARCH_RISCV_64: _ClassVar[Architecture]
    ARCH_XTENSA_LX6: _ClassVar[Architecture]
    ARCH_XTENSA_LX7: _ClassVar[Architecture]

class DebugProbeType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PROBE_UNKNOWN: _ClassVar[DebugProbeType]
    PROBE_JLINK: _ClassVar[DebugProbeType]
    PROBE_CMSIS_DAP: _ClassVar[DebugProbeType]
    PROBE_STLINK: _ClassVar[DebugProbeType]
    PROBE_BLACKMAGIC: _ClassVar[DebugProbeType]
    PROBE_OPENOCD: _ClassVar[DebugProbeType]

class DebugState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DEBUG_STATE_UNKNOWN: _ClassVar[DebugState]
    DEBUG_STATE_RUNNING: _ClassVar[DebugState]
    DEBUG_STATE_HALTED: _ClassVar[DebugState]
    DEBUG_STATE_RESET: _ClassVar[DebugState]
    DEBUG_STATE_SLEEPING: _ClassVar[DebugState]
    DEBUG_STATE_LOCKUP: _ClassVar[DebugState]

class BreakpointType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BP_HARDWARE: _ClassVar[BreakpointType]
    BP_SOFTWARE: _ClassVar[BreakpointType]

class WatchpointMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    WATCH_READ: _ClassVar[WatchpointMode]
    WATCH_WRITE: _ClassVar[WatchpointMode]
    WATCH_READ_WRITE: _ClassVar[WatchpointMode]

class Parity(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PARITY_NONE: _ClassVar[Parity]
    PARITY_ODD: _ClassVar[Parity]
    PARITY_EVEN: _ClassVar[Parity]

class StopBits(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STOP_BITS_1: _ClassVar[StopBits]
    STOP_BITS_1_5: _ClassVar[StopBits]
    STOP_BITS_2: _ClassVar[StopBits]

class FlowControl(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FLOW_NONE: _ClassVar[FlowControl]
    FLOW_RTS_CTS: _ClassVar[FlowControl]
    FLOW_XON_XOFF: _ClassVar[FlowControl]

class PowerChannel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    POWER_MAIN: _ClassVar[PowerChannel]
    POWER_VBAT: _ClassVar[PowerChannel]
    POWER_3V3: _ClassVar[PowerChannel]
    POWER_1V8: _ClassVar[PowerChannel]
    POWER_CUSTOM_1: _ClassVar[PowerChannel]
    POWER_CUSTOM_2: _ClassVar[PowerChannel]

class AnalyzerProvider(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PROVIDER_AUTO: _ClassVar[AnalyzerProvider]
    PROVIDER_SALEAE: _ClassVar[AnalyzerProvider]
    PROVIDER_SIGROK: _ClassVar[AnalyzerProvider]
    PROVIDER_SIMULATION: _ClassVar[AnalyzerProvider]

class Protocol(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PROTOCOL_I2C: _ClassVar[Protocol]
    PROTOCOL_SPI: _ClassVar[Protocol]
    PROTOCOL_UART: _ClassVar[Protocol]
    PROTOCOL_1WIRE: _ClassVar[Protocol]
    PROTOCOL_JTAG: _ClassVar[Protocol]
    PROTOCOL_SWD: _ClassVar[Protocol]
    PROTOCOL_CAN: _ClassVar[Protocol]
    PROTOCOL_LIN: _ClassVar[Protocol]
    PROTOCOL_I2S: _ClassVar[Protocol]
    PROTOCOL_PWM: _ClassVar[Protocol]

class GpioDirection(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    GPIO_INPUT: _ClassVar[GpioDirection]
    GPIO_OUTPUT: _ClassVar[GpioDirection]

class GpioPull(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    GPIO_PULL_NONE: _ClassVar[GpioPull]
    GPIO_PULL_UP: _ClassVar[GpioPull]
    GPIO_PULL_DOWN: _ClassVar[GpioPull]

class ZephyrLogLevel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    LOG_LEVEL_ERR: _ClassVar[ZephyrLogLevel]
    LOG_LEVEL_WRN: _ClassVar[ZephyrLogLevel]
    LOG_LEVEL_INF: _ClassVar[ZephyrLogLevel]
    LOG_LEVEL_DBG: _ClassVar[ZephyrLogLevel]
ARCH_UNKNOWN: Architecture
ARCH_ARM_CORTEX_M0: Architecture
ARCH_ARM_CORTEX_M0_PLUS: Architecture
ARCH_ARM_CORTEX_M3: Architecture
ARCH_ARM_CORTEX_M4: Architecture
ARCH_ARM_CORTEX_M7: Architecture
ARCH_ARM_CORTEX_M33: Architecture
ARCH_ARM_CORTEX_M55: Architecture
ARCH_ARM_CORTEX_A53: Architecture
ARCH_RISCV_32: Architecture
ARCH_RISCV_64: Architecture
ARCH_XTENSA_LX6: Architecture
ARCH_XTENSA_LX7: Architecture
PROBE_UNKNOWN: DebugProbeType
PROBE_JLINK: DebugProbeType
PROBE_CMSIS_DAP: DebugProbeType
PROBE_STLINK: DebugProbeType
PROBE_BLACKMAGIC: DebugProbeType
PROBE_OPENOCD: DebugProbeType
DEBUG_STATE_UNKNOWN: DebugState
DEBUG_STATE_RUNNING: DebugState
DEBUG_STATE_HALTED: DebugState
DEBUG_STATE_RESET: DebugState
DEBUG_STATE_SLEEPING: DebugState
DEBUG_STATE_LOCKUP: DebugState
BP_HARDWARE: BreakpointType
BP_SOFTWARE: BreakpointType
WATCH_READ: WatchpointMode
WATCH_WRITE: WatchpointMode
WATCH_READ_WRITE: WatchpointMode
PARITY_NONE: Parity
PARITY_ODD: Parity
PARITY_EVEN: Parity
STOP_BITS_1: StopBits
STOP_BITS_1_5: StopBits
STOP_BITS_2: StopBits
FLOW_NONE: FlowControl
FLOW_RTS_CTS: FlowControl
FLOW_XON_XOFF: FlowControl
POWER_MAIN: PowerChannel
POWER_VBAT: PowerChannel
POWER_3V3: PowerChannel
POWER_1V8: PowerChannel
POWER_CUSTOM_1: PowerChannel
POWER_CUSTOM_2: PowerChannel
PROVIDER_AUTO: AnalyzerProvider
PROVIDER_SALEAE: AnalyzerProvider
PROVIDER_SIGROK: AnalyzerProvider
PROVIDER_SIMULATION: AnalyzerProvider
PROTOCOL_I2C: Protocol
PROTOCOL_SPI: Protocol
PROTOCOL_UART: Protocol
PROTOCOL_1WIRE: Protocol
PROTOCOL_JTAG: Protocol
PROTOCOL_SWD: Protocol
PROTOCOL_CAN: Protocol
PROTOCOL_LIN: Protocol
PROTOCOL_I2S: Protocol
PROTOCOL_PWM: Protocol
GPIO_INPUT: GpioDirection
GPIO_OUTPUT: GpioDirection
GPIO_PULL_NONE: GpioPull
GPIO_PULL_UP: GpioPull
GPIO_PULL_DOWN: GpioPull
LOG_LEVEL_ERR: ZephyrLogLevel
LOG_LEVEL_WRN: ZephyrLogLevel
LOG_LEVEL_INF: ZephyrLogLevel
LOG_LEVEL_DBG: ZephyrLogLevel

class Empty(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class Timestamp(_message.Message):
    __slots__ = ("seconds", "nanos")
    SECONDS_FIELD_NUMBER: _ClassVar[int]
    NANOS_FIELD_NUMBER: _ClassVar[int]
    seconds: int
    nanos: int
    def __init__(self, seconds: _Optional[int] = ..., nanos: _Optional[int] = ...) -> None: ...

class Error(_message.Message):
    __slots__ = ("code", "message", "details")
    class DetailsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    code: int
    message: str
    details: _containers.ScalarMap[str, str]
    def __init__(self, code: _Optional[int] = ..., message: _Optional[str] = ..., details: _Optional[_Mapping[str, str]] = ...) -> None: ...

class Response(_message.Message):
    __slots__ = ("success", "message", "error")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    error: Error
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., error: _Optional[_Union[Error, _Mapping]] = ...) -> None: ...

class TargetDevice(_message.Message):
    __slots__ = ("id", "name", "arch", "chip", "board", "has_debug", "has_uart", "has_rtt", "has_swo", "flash_size_kb", "ram_size_kb")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    ARCH_FIELD_NUMBER: _ClassVar[int]
    CHIP_FIELD_NUMBER: _ClassVar[int]
    BOARD_FIELD_NUMBER: _ClassVar[int]
    HAS_DEBUG_FIELD_NUMBER: _ClassVar[int]
    HAS_UART_FIELD_NUMBER: _ClassVar[int]
    HAS_RTT_FIELD_NUMBER: _ClassVar[int]
    HAS_SWO_FIELD_NUMBER: _ClassVar[int]
    FLASH_SIZE_KB_FIELD_NUMBER: _ClassVar[int]
    RAM_SIZE_KB_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    arch: Architecture
    chip: str
    board: str
    has_debug: bool
    has_uart: bool
    has_rtt: bool
    has_swo: bool
    flash_size_kb: int
    ram_size_kb: int
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., arch: _Optional[_Union[Architecture, str]] = ..., chip: _Optional[str] = ..., board: _Optional[str] = ..., has_debug: bool = ..., has_uart: bool = ..., has_rtt: bool = ..., has_swo: bool = ..., flash_size_kb: _Optional[int] = ..., ram_size_kb: _Optional[int] = ...) -> None: ...

class ListTargetsResponse(_message.Message):
    __slots__ = ("success", "message", "targets")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TARGETS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    targets: _containers.RepeatedCompositeFieldContainer[TargetDevice]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., targets: _Optional[_Iterable[_Union[TargetDevice, _Mapping]]] = ...) -> None: ...

class DebugProbe(_message.Message):
    __slots__ = ("id", "type", "serial", "firmware_version", "supported_targets")
    ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    SERIAL_FIELD_NUMBER: _ClassVar[int]
    FIRMWARE_VERSION_FIELD_NUMBER: _ClassVar[int]
    SUPPORTED_TARGETS_FIELD_NUMBER: _ClassVar[int]
    id: str
    type: DebugProbeType
    serial: str
    firmware_version: str
    supported_targets: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, id: _Optional[str] = ..., type: _Optional[_Union[DebugProbeType, str]] = ..., serial: _Optional[str] = ..., firmware_version: _Optional[str] = ..., supported_targets: _Optional[_Iterable[str]] = ...) -> None: ...

class ListProbesResponse(_message.Message):
    __slots__ = ("success", "message", "probes")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    PROBES_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    probes: _containers.RepeatedCompositeFieldContainer[DebugProbe]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., probes: _Optional[_Iterable[_Union[DebugProbe, _Mapping]]] = ...) -> None: ...

class DebugConnectRequest(_message.Message):
    __slots__ = ("target_id", "probe_id", "speed_khz", "halt_on_connect")
    TARGET_ID_FIELD_NUMBER: _ClassVar[int]
    PROBE_ID_FIELD_NUMBER: _ClassVar[int]
    SPEED_KHZ_FIELD_NUMBER: _ClassVar[int]
    HALT_ON_CONNECT_FIELD_NUMBER: _ClassVar[int]
    target_id: str
    probe_id: str
    speed_khz: int
    halt_on_connect: bool
    def __init__(self, target_id: _Optional[str] = ..., probe_id: _Optional[str] = ..., speed_khz: _Optional[int] = ..., halt_on_connect: bool = ...) -> None: ...

class DebugConnectResponse(_message.Message):
    __slots__ = ("success", "message", "session_id", "state")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    session_id: str
    state: DebugState
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., session_id: _Optional[str] = ..., state: _Optional[_Union[DebugState, str]] = ...) -> None: ...

class DebugDisconnectRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class DebugStatusRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class DebugStatusResponse(_message.Message):
    __slots__ = ("success", "message", "state", "pc", "halt_reason")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    PC_FIELD_NUMBER: _ClassVar[int]
    HALT_REASON_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    state: DebugState
    pc: int
    halt_reason: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., state: _Optional[_Union[DebugState, str]] = ..., pc: _Optional[int] = ..., halt_reason: _Optional[str] = ...) -> None: ...

class DebugHaltRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class DebugResumeRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class DebugStepRequest(_message.Message):
    __slots__ = ("session_id", "step_over")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    STEP_OVER_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    step_over: bool
    def __init__(self, session_id: _Optional[str] = ..., step_over: bool = ...) -> None: ...

class DebugResetRequest(_message.Message):
    __slots__ = ("session_id", "halt_after_reset", "type")
    class ResetType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        RESET_NORMAL: _ClassVar[DebugResetRequest.ResetType]
        RESET_HARD: _ClassVar[DebugResetRequest.ResetType]
        RESET_CORE: _ClassVar[DebugResetRequest.ResetType]
        RESET_SYSTEM: _ClassVar[DebugResetRequest.ResetType]
    RESET_NORMAL: DebugResetRequest.ResetType
    RESET_HARD: DebugResetRequest.ResetType
    RESET_CORE: DebugResetRequest.ResetType
    RESET_SYSTEM: DebugResetRequest.ResetType
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    HALT_AFTER_RESET_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    halt_after_reset: bool
    type: DebugResetRequest.ResetType
    def __init__(self, session_id: _Optional[str] = ..., halt_after_reset: bool = ..., type: _Optional[_Union[DebugResetRequest.ResetType, str]] = ...) -> None: ...

class RegisterValue(_message.Message):
    __slots__ = ("name", "value", "size_bits")
    NAME_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    SIZE_BITS_FIELD_NUMBER: _ClassVar[int]
    name: str
    value: int
    size_bits: int
    def __init__(self, name: _Optional[str] = ..., value: _Optional[int] = ..., size_bits: _Optional[int] = ...) -> None: ...

class ReadRegistersRequest(_message.Message):
    __slots__ = ("session_id", "names")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    NAMES_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    names: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, session_id: _Optional[str] = ..., names: _Optional[_Iterable[str]] = ...) -> None: ...

class ReadRegistersResponse(_message.Message):
    __slots__ = ("success", "message", "registers")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    REGISTERS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    registers: _containers.RepeatedCompositeFieldContainer[RegisterValue]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., registers: _Optional[_Iterable[_Union[RegisterValue, _Mapping]]] = ...) -> None: ...

class WriteRegisterRequest(_message.Message):
    __slots__ = ("session_id", "name", "value")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    name: str
    value: int
    def __init__(self, session_id: _Optional[str] = ..., name: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...

class ReadMemoryRequest(_message.Message):
    __slots__ = ("session_id", "address", "size", "width")
    class AccessWidth(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ACCESS_8: _ClassVar[ReadMemoryRequest.AccessWidth]
        ACCESS_16: _ClassVar[ReadMemoryRequest.AccessWidth]
        ACCESS_32: _ClassVar[ReadMemoryRequest.AccessWidth]
    ACCESS_8: ReadMemoryRequest.AccessWidth
    ACCESS_16: ReadMemoryRequest.AccessWidth
    ACCESS_32: ReadMemoryRequest.AccessWidth
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    WIDTH_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    address: int
    size: int
    width: ReadMemoryRequest.AccessWidth
    def __init__(self, session_id: _Optional[str] = ..., address: _Optional[int] = ..., size: _Optional[int] = ..., width: _Optional[_Union[ReadMemoryRequest.AccessWidth, str]] = ...) -> None: ...

class ReadMemoryResponse(_message.Message):
    __slots__ = ("success", "message", "data")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    data: bytes
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., data: _Optional[bytes] = ...) -> None: ...

class WriteMemoryRequest(_message.Message):
    __slots__ = ("session_id", "address", "data", "width")
    class AccessWidth(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ACCESS_8: _ClassVar[WriteMemoryRequest.AccessWidth]
        ACCESS_16: _ClassVar[WriteMemoryRequest.AccessWidth]
        ACCESS_32: _ClassVar[WriteMemoryRequest.AccessWidth]
    ACCESS_8: WriteMemoryRequest.AccessWidth
    ACCESS_16: WriteMemoryRequest.AccessWidth
    ACCESS_32: WriteMemoryRequest.AccessWidth
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    WIDTH_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    address: int
    data: bytes
    width: WriteMemoryRequest.AccessWidth
    def __init__(self, session_id: _Optional[str] = ..., address: _Optional[int] = ..., data: _Optional[bytes] = ..., width: _Optional[_Union[WriteMemoryRequest.AccessWidth, str]] = ...) -> None: ...

class SetBreakpointRequest(_message.Message):
    __slots__ = ("session_id", "address", "type")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    address: int
    type: BreakpointType
    def __init__(self, session_id: _Optional[str] = ..., address: _Optional[int] = ..., type: _Optional[_Union[BreakpointType, str]] = ...) -> None: ...

class SetBreakpointResponse(_message.Message):
    __slots__ = ("success", "message", "breakpoint_id")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    BREAKPOINT_ID_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    breakpoint_id: int
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., breakpoint_id: _Optional[int] = ...) -> None: ...

class ClearBreakpointRequest(_message.Message):
    __slots__ = ("session_id", "breakpoint_id")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    BREAKPOINT_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    breakpoint_id: int
    def __init__(self, session_id: _Optional[str] = ..., breakpoint_id: _Optional[int] = ...) -> None: ...

class SetWatchpointRequest(_message.Message):
    __slots__ = ("session_id", "address", "size", "mode")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    address: int
    size: int
    mode: WatchpointMode
    def __init__(self, session_id: _Optional[str] = ..., address: _Optional[int] = ..., size: _Optional[int] = ..., mode: _Optional[_Union[WatchpointMode, str]] = ...) -> None: ...

class SetWatchpointResponse(_message.Message):
    __slots__ = ("success", "message", "watchpoint_id")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    WATCHPOINT_ID_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    watchpoint_id: int
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., watchpoint_id: _Optional[int] = ...) -> None: ...

class StackFrame(_message.Message):
    __slots__ = ("level", "pc", "sp", "function", "file", "line")
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    PC_FIELD_NUMBER: _ClassVar[int]
    SP_FIELD_NUMBER: _ClassVar[int]
    FUNCTION_FIELD_NUMBER: _ClassVar[int]
    FILE_FIELD_NUMBER: _ClassVar[int]
    LINE_FIELD_NUMBER: _ClassVar[int]
    level: int
    pc: int
    sp: int
    function: str
    file: str
    line: int
    def __init__(self, level: _Optional[int] = ..., pc: _Optional[int] = ..., sp: _Optional[int] = ..., function: _Optional[str] = ..., file: _Optional[str] = ..., line: _Optional[int] = ...) -> None: ...

class BacktraceRequest(_message.Message):
    __slots__ = ("session_id", "max_frames")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    MAX_FRAMES_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    max_frames: int
    def __init__(self, session_id: _Optional[str] = ..., max_frames: _Optional[int] = ...) -> None: ...

class BacktraceResponse(_message.Message):
    __slots__ = ("success", "message", "frames")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    FRAMES_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    frames: _containers.RepeatedCompositeFieldContainer[StackFrame]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., frames: _Optional[_Iterable[_Union[StackFrame, _Mapping]]] = ...) -> None: ...

class FlashInfoRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class FlashRegion(_message.Message):
    __slots__ = ("start", "size", "sector_size", "writable")
    START_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    SECTOR_SIZE_FIELD_NUMBER: _ClassVar[int]
    WRITABLE_FIELD_NUMBER: _ClassVar[int]
    start: int
    size: int
    sector_size: int
    writable: bool
    def __init__(self, start: _Optional[int] = ..., size: _Optional[int] = ..., sector_size: _Optional[int] = ..., writable: bool = ...) -> None: ...

class FlashInfoResponse(_message.Message):
    __slots__ = ("success", "message", "regions")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    REGIONS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    regions: _containers.RepeatedCompositeFieldContainer[FlashRegion]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., regions: _Optional[_Iterable[_Union[FlashRegion, _Mapping]]] = ...) -> None: ...

class FlashEraseRequest(_message.Message):
    __slots__ = ("session_id", "target_id", "probe_id", "address", "size")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_ID_FIELD_NUMBER: _ClassVar[int]
    PROBE_ID_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    target_id: str
    probe_id: str
    address: int
    size: int
    def __init__(self, session_id: _Optional[str] = ..., target_id: _Optional[str] = ..., probe_id: _Optional[str] = ..., address: _Optional[int] = ..., size: _Optional[int] = ...) -> None: ...

class FlashWriteRequest(_message.Message):
    __slots__ = ("session_id", "address", "data", "verify")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    VERIFY_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    address: int
    data: bytes
    verify: bool
    def __init__(self, session_id: _Optional[str] = ..., address: _Optional[int] = ..., data: _Optional[bytes] = ..., verify: bool = ...) -> None: ...

class FlashWriteResponse(_message.Message):
    __slots__ = ("success", "message", "bytes_written", "time_ms")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    BYTES_WRITTEN_FIELD_NUMBER: _ClassVar[int]
    TIME_MS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    bytes_written: int
    time_ms: int
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., bytes_written: _Optional[int] = ..., time_ms: _Optional[int] = ...) -> None: ...

class FlashProgramRequest(_message.Message):
    __slots__ = ("session_id", "target_id", "probe_id", "filename", "erase_before", "verify_after", "reset_after")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_ID_FIELD_NUMBER: _ClassVar[int]
    PROBE_ID_FIELD_NUMBER: _ClassVar[int]
    FILENAME_FIELD_NUMBER: _ClassVar[int]
    ERASE_BEFORE_FIELD_NUMBER: _ClassVar[int]
    VERIFY_AFTER_FIELD_NUMBER: _ClassVar[int]
    RESET_AFTER_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    target_id: str
    probe_id: str
    filename: str
    erase_before: bool
    verify_after: bool
    reset_after: bool
    def __init__(self, session_id: _Optional[str] = ..., target_id: _Optional[str] = ..., probe_id: _Optional[str] = ..., filename: _Optional[str] = ..., erase_before: bool = ..., verify_after: bool = ..., reset_after: bool = ...) -> None: ...

class FlashProgramResponse(_message.Message):
    __slots__ = ("success", "message", "bytes_programmed", "time_ms")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    BYTES_PROGRAMMED_FIELD_NUMBER: _ClassVar[int]
    TIME_MS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    bytes_programmed: int
    time_ms: int
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., bytes_programmed: _Optional[int] = ..., time_ms: _Optional[int] = ...) -> None: ...

class RttStartRequest(_message.Message):
    __slots__ = ("session_id", "control_block_address")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    CONTROL_BLOCK_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    control_block_address: int
    def __init__(self, session_id: _Optional[str] = ..., control_block_address: _Optional[int] = ...) -> None: ...

class RttStartResponse(_message.Message):
    __slots__ = ("success", "message", "num_up_channels", "num_down_channels")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    NUM_UP_CHANNELS_FIELD_NUMBER: _ClassVar[int]
    NUM_DOWN_CHANNELS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    num_up_channels: int
    num_down_channels: int
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., num_up_channels: _Optional[int] = ..., num_down_channels: _Optional[int] = ...) -> None: ...

class RttStopRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class RttStreamRequest(_message.Message):
    __slots__ = ("session_id", "channel", "data")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    channel: int
    data: bytes
    def __init__(self, session_id: _Optional[str] = ..., channel: _Optional[int] = ..., data: _Optional[bytes] = ...) -> None: ...

class RttStreamResponse(_message.Message):
    __slots__ = ("success", "message", "channel", "data", "timestamp")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    channel: int
    data: bytes
    timestamp: Timestamp
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., channel: _Optional[int] = ..., data: _Optional[bytes] = ..., timestamp: _Optional[_Union[Timestamp, _Mapping]] = ...) -> None: ...

class SwoStartRequest(_message.Message):
    __slots__ = ("session_id", "cpu_freq_hz", "swo_freq_hz", "port_mask")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    CPU_FREQ_HZ_FIELD_NUMBER: _ClassVar[int]
    SWO_FREQ_HZ_FIELD_NUMBER: _ClassVar[int]
    PORT_MASK_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    cpu_freq_hz: int
    swo_freq_hz: int
    port_mask: int
    def __init__(self, session_id: _Optional[str] = ..., cpu_freq_hz: _Optional[int] = ..., swo_freq_hz: _Optional[int] = ..., port_mask: _Optional[int] = ...) -> None: ...

class SwoStreamResponse(_message.Message):
    __slots__ = ("port", "data", "timestamp")
    PORT_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    port: int
    data: bytes
    timestamp: Timestamp
    def __init__(self, port: _Optional[int] = ..., data: _Optional[bytes] = ..., timestamp: _Optional[_Union[Timestamp, _Mapping]] = ...) -> None: ...

class UartConfig(_message.Message):
    __slots__ = ("baud", "data_bits", "parity", "stop_bits", "flow_control")
    BAUD_FIELD_NUMBER: _ClassVar[int]
    DATA_BITS_FIELD_NUMBER: _ClassVar[int]
    PARITY_FIELD_NUMBER: _ClassVar[int]
    STOP_BITS_FIELD_NUMBER: _ClassVar[int]
    FLOW_CONTROL_FIELD_NUMBER: _ClassVar[int]
    baud: int
    data_bits: int
    parity: Parity
    stop_bits: StopBits
    flow_control: FlowControl
    def __init__(self, baud: _Optional[int] = ..., data_bits: _Optional[int] = ..., parity: _Optional[_Union[Parity, str]] = ..., stop_bits: _Optional[_Union[StopBits, str]] = ..., flow_control: _Optional[_Union[FlowControl, str]] = ...) -> None: ...

class UartOpenRequest(_message.Message):
    __slots__ = ("target_id", "port_name", "config")
    TARGET_ID_FIELD_NUMBER: _ClassVar[int]
    PORT_NAME_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    target_id: str
    port_name: str
    config: UartConfig
    def __init__(self, target_id: _Optional[str] = ..., port_name: _Optional[str] = ..., config: _Optional[_Union[UartConfig, _Mapping]] = ...) -> None: ...

class UartOpenResponse(_message.Message):
    __slots__ = ("success", "message", "stream_id")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    STREAM_ID_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    stream_id: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., stream_id: _Optional[str] = ...) -> None: ...

class UartCloseRequest(_message.Message):
    __slots__ = ("stream_id",)
    STREAM_ID_FIELD_NUMBER: _ClassVar[int]
    stream_id: str
    def __init__(self, stream_id: _Optional[str] = ...) -> None: ...

class UartStreamRequest(_message.Message):
    __slots__ = ("stream_id", "data")
    STREAM_ID_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    stream_id: str
    data: bytes
    def __init__(self, stream_id: _Optional[str] = ..., data: _Optional[bytes] = ...) -> None: ...

class UartStreamResponse(_message.Message):
    __slots__ = ("success", "message", "data", "timestamp")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    data: bytes
    timestamp: Timestamp
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., data: _Optional[bytes] = ..., timestamp: _Optional[_Union[Timestamp, _Mapping]] = ...) -> None: ...

class PowerConfig(_message.Message):
    __slots__ = ("channel", "voltage_v", "current_limit_ma", "sample_rate_hz")
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    VOLTAGE_V_FIELD_NUMBER: _ClassVar[int]
    CURRENT_LIMIT_MA_FIELD_NUMBER: _ClassVar[int]
    SAMPLE_RATE_HZ_FIELD_NUMBER: _ClassVar[int]
    channel: PowerChannel
    voltage_v: float
    current_limit_ma: float
    sample_rate_hz: int
    def __init__(self, channel: _Optional[_Union[PowerChannel, str]] = ..., voltage_v: _Optional[float] = ..., current_limit_ma: _Optional[float] = ..., sample_rate_hz: _Optional[int] = ...) -> None: ...

class PowerEnableRequest(_message.Message):
    __slots__ = ("config",)
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    config: PowerConfig
    def __init__(self, config: _Optional[_Union[PowerConfig, _Mapping]] = ...) -> None: ...

class PowerDisableRequest(_message.Message):
    __slots__ = ("channel",)
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    channel: PowerChannel
    def __init__(self, channel: _Optional[_Union[PowerChannel, str]] = ...) -> None: ...

class PowerStatusRequest(_message.Message):
    __slots__ = ("channel",)
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    channel: PowerChannel
    def __init__(self, channel: _Optional[_Union[PowerChannel, str]] = ...) -> None: ...

class PowerStatusResponse(_message.Message):
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

class PowerSample(_message.Message):
    __slots__ = ("timestamp", "current_ua", "voltage_mv")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    CURRENT_UA_FIELD_NUMBER: _ClassVar[int]
    VOLTAGE_MV_FIELD_NUMBER: _ClassVar[int]
    timestamp: Timestamp
    current_ua: float
    voltage_mv: float
    def __init__(self, timestamp: _Optional[_Union[Timestamp, _Mapping]] = ..., current_ua: _Optional[float] = ..., voltage_mv: _Optional[float] = ...) -> None: ...

class PowerStreamRequest(_message.Message):
    __slots__ = ("channel", "sample_rate_hz")
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    SAMPLE_RATE_HZ_FIELD_NUMBER: _ClassVar[int]
    channel: PowerChannel
    sample_rate_hz: int
    def __init__(self, channel: _Optional[_Union[PowerChannel, str]] = ..., sample_rate_hz: _Optional[int] = ...) -> None: ...

class PowerStreamResponse(_message.Message):
    __slots__ = ("success", "message", "samples")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SAMPLES_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    samples: _containers.RepeatedCompositeFieldContainer[PowerSample]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., samples: _Optional[_Iterable[_Union[PowerSample, _Mapping]]] = ...) -> None: ...

class PowerMeasureRequest(_message.Message):
    __slots__ = ("channel", "duration_s", "sample_rate_hz")
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    DURATION_S_FIELD_NUMBER: _ClassVar[int]
    SAMPLE_RATE_HZ_FIELD_NUMBER: _ClassVar[int]
    channel: PowerChannel
    duration_s: float
    sample_rate_hz: int
    def __init__(self, channel: _Optional[_Union[PowerChannel, str]] = ..., duration_s: _Optional[float] = ..., sample_rate_hz: _Optional[int] = ...) -> None: ...

class PowerMeasureResponse(_message.Message):
    __slots__ = ("success", "message", "duration_s", "average_ua", "min_ua", "max_ua", "energy_uj", "sample_count", "samples")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DURATION_S_FIELD_NUMBER: _ClassVar[int]
    AVERAGE_UA_FIELD_NUMBER: _ClassVar[int]
    MIN_UA_FIELD_NUMBER: _ClassVar[int]
    MAX_UA_FIELD_NUMBER: _ClassVar[int]
    ENERGY_UJ_FIELD_NUMBER: _ClassVar[int]
    SAMPLE_COUNT_FIELD_NUMBER: _ClassVar[int]
    SAMPLES_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    duration_s: float
    average_ua: float
    min_ua: float
    max_ua: float
    energy_uj: float
    sample_count: int
    samples: _containers.RepeatedCompositeFieldContainer[PowerSample]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., duration_s: _Optional[float] = ..., average_ua: _Optional[float] = ..., min_ua: _Optional[float] = ..., max_ua: _Optional[float] = ..., energy_uj: _Optional[float] = ..., sample_count: _Optional[int] = ..., samples: _Optional[_Iterable[_Union[PowerSample, _Mapping]]] = ...) -> None: ...

class AnalyzerChannelConfig(_message.Message):
    __slots__ = ("channel", "label", "enabled")
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    channel: int
    label: str
    enabled: bool
    def __init__(self, channel: _Optional[int] = ..., label: _Optional[str] = ..., enabled: bool = ...) -> None: ...

class AnalyzerCaptureConfig(_message.Message):
    __slots__ = ("channels", "sample_rate_hz", "duration_s", "trigger_enabled", "trigger_channel", "trigger_edge", "pre_trigger_s", "timeout_s", "max_samples", "max_memory_mb", "circular_buffer", "auto_export_on_stop")
    class TriggerEdge(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        TRIGGER_RISING: _ClassVar[AnalyzerCaptureConfig.TriggerEdge]
        TRIGGER_FALLING: _ClassVar[AnalyzerCaptureConfig.TriggerEdge]
        TRIGGER_EITHER: _ClassVar[AnalyzerCaptureConfig.TriggerEdge]
    TRIGGER_RISING: AnalyzerCaptureConfig.TriggerEdge
    TRIGGER_FALLING: AnalyzerCaptureConfig.TriggerEdge
    TRIGGER_EITHER: AnalyzerCaptureConfig.TriggerEdge
    CHANNELS_FIELD_NUMBER: _ClassVar[int]
    SAMPLE_RATE_HZ_FIELD_NUMBER: _ClassVar[int]
    DURATION_S_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_ENABLED_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_EDGE_FIELD_NUMBER: _ClassVar[int]
    PRE_TRIGGER_S_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_S_FIELD_NUMBER: _ClassVar[int]
    MAX_SAMPLES_FIELD_NUMBER: _ClassVar[int]
    MAX_MEMORY_MB_FIELD_NUMBER: _ClassVar[int]
    CIRCULAR_BUFFER_FIELD_NUMBER: _ClassVar[int]
    AUTO_EXPORT_ON_STOP_FIELD_NUMBER: _ClassVar[int]
    channels: _containers.RepeatedCompositeFieldContainer[AnalyzerChannelConfig]
    sample_rate_hz: int
    duration_s: float
    trigger_enabled: bool
    trigger_channel: int
    trigger_edge: AnalyzerCaptureConfig.TriggerEdge
    pre_trigger_s: float
    timeout_s: float
    max_samples: int
    max_memory_mb: int
    circular_buffer: bool
    auto_export_on_stop: bool
    def __init__(self, channels: _Optional[_Iterable[_Union[AnalyzerChannelConfig, _Mapping]]] = ..., sample_rate_hz: _Optional[int] = ..., duration_s: _Optional[float] = ..., trigger_enabled: bool = ..., trigger_channel: _Optional[int] = ..., trigger_edge: _Optional[_Union[AnalyzerCaptureConfig.TriggerEdge, str]] = ..., pre_trigger_s: _Optional[float] = ..., timeout_s: _Optional[float] = ..., max_samples: _Optional[int] = ..., max_memory_mb: _Optional[int] = ..., circular_buffer: bool = ..., auto_export_on_stop: bool = ...) -> None: ...

class AnalyzerCaptureStartRequest(_message.Message):
    __slots__ = ("config", "prefer_provider")
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    PREFER_PROVIDER_FIELD_NUMBER: _ClassVar[int]
    config: AnalyzerCaptureConfig
    prefer_provider: AnalyzerProvider
    def __init__(self, config: _Optional[_Union[AnalyzerCaptureConfig, _Mapping]] = ..., prefer_provider: _Optional[_Union[AnalyzerProvider, str]] = ...) -> None: ...

class AnalyzerCaptureStartResponse(_message.Message):
    __slots__ = ("success", "message", "capture_id", "provider_used")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    CAPTURE_ID_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_USED_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    capture_id: str
    provider_used: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., capture_id: _Optional[str] = ..., provider_used: _Optional[str] = ...) -> None: ...

class AnalyzerCaptureStatusRequest(_message.Message):
    __slots__ = ("capture_id",)
    CAPTURE_ID_FIELD_NUMBER: _ClassVar[int]
    capture_id: str
    def __init__(self, capture_id: _Optional[str] = ...) -> None: ...

class AnalyzerCaptureStatusResponse(_message.Message):
    __slots__ = ("success", "message", "status", "progress", "samples_captured", "samples_dropped", "memory_usage_mb")
    class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATUS_WAITING_TRIGGER: _ClassVar[AnalyzerCaptureStatusResponse.Status]
        STATUS_CAPTURING: _ClassVar[AnalyzerCaptureStatusResponse.Status]
        STATUS_COMPLETE: _ClassVar[AnalyzerCaptureStatusResponse.Status]
        STATUS_ERROR: _ClassVar[AnalyzerCaptureStatusResponse.Status]
    STATUS_WAITING_TRIGGER: AnalyzerCaptureStatusResponse.Status
    STATUS_CAPTURING: AnalyzerCaptureStatusResponse.Status
    STATUS_COMPLETE: AnalyzerCaptureStatusResponse.Status
    STATUS_ERROR: AnalyzerCaptureStatusResponse.Status
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_FIELD_NUMBER: _ClassVar[int]
    SAMPLES_CAPTURED_FIELD_NUMBER: _ClassVar[int]
    SAMPLES_DROPPED_FIELD_NUMBER: _ClassVar[int]
    MEMORY_USAGE_MB_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    status: AnalyzerCaptureStatusResponse.Status
    progress: float
    samples_captured: int
    samples_dropped: int
    memory_usage_mb: float
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., status: _Optional[_Union[AnalyzerCaptureStatusResponse.Status, str]] = ..., progress: _Optional[float] = ..., samples_captured: _Optional[int] = ..., samples_dropped: _Optional[int] = ..., memory_usage_mb: _Optional[float] = ...) -> None: ...

class AnalyzerCaptureStopRequest(_message.Message):
    __slots__ = ("capture_id",)
    CAPTURE_ID_FIELD_NUMBER: _ClassVar[int]
    capture_id: str
    def __init__(self, capture_id: _Optional[str] = ...) -> None: ...

class AnalyzerStreamRequest(_message.Message):
    __slots__ = ("capture_id", "max_samples_per_chunk", "interval_s")
    CAPTURE_ID_FIELD_NUMBER: _ClassVar[int]
    MAX_SAMPLES_PER_CHUNK_FIELD_NUMBER: _ClassVar[int]
    INTERVAL_S_FIELD_NUMBER: _ClassVar[int]
    capture_id: str
    max_samples_per_chunk: int
    interval_s: float
    def __init__(self, capture_id: _Optional[str] = ..., max_samples_per_chunk: _Optional[int] = ..., interval_s: _Optional[float] = ...) -> None: ...

class AnalyzerSample(_message.Message):
    __slots__ = ("timestamp_ns", "digital_values")
    TIMESTAMP_NS_FIELD_NUMBER: _ClassVar[int]
    DIGITAL_VALUES_FIELD_NUMBER: _ClassVar[int]
    timestamp_ns: int
    digital_values: _containers.RepeatedScalarFieldContainer[bool]
    def __init__(self, timestamp_ns: _Optional[int] = ..., digital_values: _Optional[_Iterable[bool]] = ...) -> None: ...

class AnalyzerStreamResponse(_message.Message):
    __slots__ = ("success", "message", "samples", "capture_complete", "total_samples", "samples_dropped")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SAMPLES_FIELD_NUMBER: _ClassVar[int]
    CAPTURE_COMPLETE_FIELD_NUMBER: _ClassVar[int]
    TOTAL_SAMPLES_FIELD_NUMBER: _ClassVar[int]
    SAMPLES_DROPPED_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    samples: _containers.RepeatedCompositeFieldContainer[AnalyzerSample]
    capture_complete: bool
    total_samples: int
    samples_dropped: int
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., samples: _Optional[_Iterable[_Union[AnalyzerSample, _Mapping]]] = ..., capture_complete: bool = ..., total_samples: _Optional[int] = ..., samples_dropped: _Optional[int] = ...) -> None: ...

class ListAnalyzerProvidersRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class AnalyzerProviderInfo(_message.Message):
    __slots__ = ("name", "display_name", "available", "max_sample_rate_hz", "max_channels", "supported_protocols", "supports_streaming", "supports_triggers", "hardware_detected", "supported_export_formats")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_FIELD_NUMBER: _ClassVar[int]
    MAX_SAMPLE_RATE_HZ_FIELD_NUMBER: _ClassVar[int]
    MAX_CHANNELS_FIELD_NUMBER: _ClassVar[int]
    SUPPORTED_PROTOCOLS_FIELD_NUMBER: _ClassVar[int]
    SUPPORTS_STREAMING_FIELD_NUMBER: _ClassVar[int]
    SUPPORTS_TRIGGERS_FIELD_NUMBER: _ClassVar[int]
    HARDWARE_DETECTED_FIELD_NUMBER: _ClassVar[int]
    SUPPORTED_EXPORT_FORMATS_FIELD_NUMBER: _ClassVar[int]
    name: str
    display_name: str
    available: bool
    max_sample_rate_hz: int
    max_channels: int
    supported_protocols: _containers.RepeatedScalarFieldContainer[str]
    supports_streaming: bool
    supports_triggers: bool
    hardware_detected: str
    supported_export_formats: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, name: _Optional[str] = ..., display_name: _Optional[str] = ..., available: bool = ..., max_sample_rate_hz: _Optional[int] = ..., max_channels: _Optional[int] = ..., supported_protocols: _Optional[_Iterable[str]] = ..., supports_streaming: bool = ..., supports_triggers: bool = ..., hardware_detected: _Optional[str] = ..., supported_export_formats: _Optional[_Iterable[str]] = ...) -> None: ...

class ListAnalyzerProvidersResponse(_message.Message):
    __slots__ = ("success", "message", "providers")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    PROVIDERS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    providers: _containers.RepeatedCompositeFieldContainer[AnalyzerProviderInfo]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., providers: _Optional[_Iterable[_Union[AnalyzerProviderInfo, _Mapping]]] = ...) -> None: ...

class AnalyzerExportRequest(_message.Message):
    __slots__ = ("capture_id", "format", "output_path")
    class ExportFormat(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        FORMAT_CSV: _ClassVar[AnalyzerExportRequest.ExportFormat]
        FORMAT_VCD: _ClassVar[AnalyzerExportRequest.ExportFormat]
        FORMAT_NATIVE_SALEAE: _ClassVar[AnalyzerExportRequest.ExportFormat]
        FORMAT_NATIVE_SIGROK: _ClassVar[AnalyzerExportRequest.ExportFormat]
    FORMAT_CSV: AnalyzerExportRequest.ExportFormat
    FORMAT_VCD: AnalyzerExportRequest.ExportFormat
    FORMAT_NATIVE_SALEAE: AnalyzerExportRequest.ExportFormat
    FORMAT_NATIVE_SIGROK: AnalyzerExportRequest.ExportFormat
    CAPTURE_ID_FIELD_NUMBER: _ClassVar[int]
    FORMAT_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_PATH_FIELD_NUMBER: _ClassVar[int]
    capture_id: str
    format: AnalyzerExportRequest.ExportFormat
    output_path: str
    def __init__(self, capture_id: _Optional[str] = ..., format: _Optional[_Union[AnalyzerExportRequest.ExportFormat, str]] = ..., output_path: _Optional[str] = ...) -> None: ...

class AnalyzerExportResponse(_message.Message):
    __slots__ = ("success", "message", "file_path", "file_size_bytes")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    FILE_PATH_FIELD_NUMBER: _ClassVar[int]
    FILE_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    file_path: str
    file_size_bytes: int
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., file_path: _Optional[str] = ..., file_size_bytes: _Optional[int] = ...) -> None: ...

class AnalyzerCleanupRequest(_message.Message):
    __slots__ = ("capture_id",)
    CAPTURE_ID_FIELD_NUMBER: _ClassVar[int]
    capture_id: str
    def __init__(self, capture_id: _Optional[str] = ...) -> None: ...

class AnalyzerCleanupResponse(_message.Message):
    __slots__ = ("success", "message", "cleaned_capture_ids", "memory_freed_mb")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    CLEANED_CAPTURE_IDS_FIELD_NUMBER: _ClassVar[int]
    MEMORY_FREED_MB_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    cleaned_capture_ids: _containers.RepeatedScalarFieldContainer[str]
    memory_freed_mb: int
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., cleaned_capture_ids: _Optional[_Iterable[str]] = ..., memory_freed_mb: _Optional[int] = ...) -> None: ...

class I2cDecoderConfig(_message.Message):
    __slots__ = ("sda_channel", "scl_channel")
    SDA_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    SCL_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    sda_channel: int
    scl_channel: int
    def __init__(self, sda_channel: _Optional[int] = ..., scl_channel: _Optional[int] = ...) -> None: ...

class SpiDecoderConfig(_message.Message):
    __slots__ = ("clk_channel", "mosi_channel", "miso_channel", "cs_channel", "cpol", "cpha", "bits_per_word", "msb_first")
    CLK_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    MOSI_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    MISO_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    CS_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    CPOL_FIELD_NUMBER: _ClassVar[int]
    CPHA_FIELD_NUMBER: _ClassVar[int]
    BITS_PER_WORD_FIELD_NUMBER: _ClassVar[int]
    MSB_FIRST_FIELD_NUMBER: _ClassVar[int]
    clk_channel: int
    mosi_channel: int
    miso_channel: int
    cs_channel: int
    cpol: bool
    cpha: bool
    bits_per_word: int
    msb_first: bool
    def __init__(self, clk_channel: _Optional[int] = ..., mosi_channel: _Optional[int] = ..., miso_channel: _Optional[int] = ..., cs_channel: _Optional[int] = ..., cpol: bool = ..., cpha: bool = ..., bits_per_word: _Optional[int] = ..., msb_first: bool = ...) -> None: ...

class UartDecoderConfig(_message.Message):
    __slots__ = ("rx_channel", "tx_channel", "baud", "data_bits", "parity")
    RX_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    TX_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    BAUD_FIELD_NUMBER: _ClassVar[int]
    DATA_BITS_FIELD_NUMBER: _ClassVar[int]
    PARITY_FIELD_NUMBER: _ClassVar[int]
    rx_channel: int
    tx_channel: int
    baud: int
    data_bits: int
    parity: Parity
    def __init__(self, rx_channel: _Optional[int] = ..., tx_channel: _Optional[int] = ..., baud: _Optional[int] = ..., data_bits: _Optional[int] = ..., parity: _Optional[_Union[Parity, str]] = ...) -> None: ...

class AddDecoderRequest(_message.Message):
    __slots__ = ("capture_id", "decoder_name", "protocol", "i2c", "spi", "uart")
    CAPTURE_ID_FIELD_NUMBER: _ClassVar[int]
    DECODER_NAME_FIELD_NUMBER: _ClassVar[int]
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    I2C_FIELD_NUMBER: _ClassVar[int]
    SPI_FIELD_NUMBER: _ClassVar[int]
    UART_FIELD_NUMBER: _ClassVar[int]
    capture_id: str
    decoder_name: str
    protocol: Protocol
    i2c: I2cDecoderConfig
    spi: SpiDecoderConfig
    uart: UartDecoderConfig
    def __init__(self, capture_id: _Optional[str] = ..., decoder_name: _Optional[str] = ..., protocol: _Optional[_Union[Protocol, str]] = ..., i2c: _Optional[_Union[I2cDecoderConfig, _Mapping]] = ..., spi: _Optional[_Union[SpiDecoderConfig, _Mapping]] = ..., uart: _Optional[_Union[UartDecoderConfig, _Mapping]] = ...) -> None: ...

class AddDecoderResponse(_message.Message):
    __slots__ = ("success", "message", "decoder_id")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DECODER_ID_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    decoder_id: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., decoder_id: _Optional[str] = ...) -> None: ...

class I2cTransaction(_message.Message):
    __slots__ = ("timestamp", "address", "read", "data", "ack")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    READ_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    ACK_FIELD_NUMBER: _ClassVar[int]
    timestamp: Timestamp
    address: int
    read: bool
    data: bytes
    ack: bool
    def __init__(self, timestamp: _Optional[_Union[Timestamp, _Mapping]] = ..., address: _Optional[int] = ..., read: bool = ..., data: _Optional[bytes] = ..., ack: bool = ...) -> None: ...

class SpiTransaction(_message.Message):
    __slots__ = ("timestamp", "mosi_data", "miso_data")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    MOSI_DATA_FIELD_NUMBER: _ClassVar[int]
    MISO_DATA_FIELD_NUMBER: _ClassVar[int]
    timestamp: Timestamp
    mosi_data: bytes
    miso_data: bytes
    def __init__(self, timestamp: _Optional[_Union[Timestamp, _Mapping]] = ..., mosi_data: _Optional[bytes] = ..., miso_data: _Optional[bytes] = ...) -> None: ...

class UartFrameDecoded(_message.Message):
    __slots__ = ("timestamp", "is_tx", "data", "parity_error", "framing_error")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    IS_TX_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    PARITY_ERROR_FIELD_NUMBER: _ClassVar[int]
    FRAMING_ERROR_FIELD_NUMBER: _ClassVar[int]
    timestamp: Timestamp
    is_tx: bool
    data: bytes
    parity_error: bool
    framing_error: bool
    def __init__(self, timestamp: _Optional[_Union[Timestamp, _Mapping]] = ..., is_tx: bool = ..., data: _Optional[bytes] = ..., parity_error: bool = ..., framing_error: bool = ...) -> None: ...

class CanFrameDecoded(_message.Message):
    __slots__ = ("timestamp", "id", "extended_id", "rtr", "data")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    EXTENDED_ID_FIELD_NUMBER: _ClassVar[int]
    RTR_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    timestamp: Timestamp
    id: int
    extended_id: bool
    rtr: bool
    data: bytes
    def __init__(self, timestamp: _Optional[_Union[Timestamp, _Mapping]] = ..., id: _Optional[int] = ..., extended_id: bool = ..., rtr: bool = ..., data: _Optional[bytes] = ...) -> None: ...

class DecodedData(_message.Message):
    __slots__ = ("decoder_id", "i2c", "spi", "uart", "can")
    DECODER_ID_FIELD_NUMBER: _ClassVar[int]
    I2C_FIELD_NUMBER: _ClassVar[int]
    SPI_FIELD_NUMBER: _ClassVar[int]
    UART_FIELD_NUMBER: _ClassVar[int]
    CAN_FIELD_NUMBER: _ClassVar[int]
    decoder_id: str
    i2c: I2cTransaction
    spi: SpiTransaction
    uart: UartFrameDecoded
    can: CanFrameDecoded
    def __init__(self, decoder_id: _Optional[str] = ..., i2c: _Optional[_Union[I2cTransaction, _Mapping]] = ..., spi: _Optional[_Union[SpiTransaction, _Mapping]] = ..., uart: _Optional[_Union[UartFrameDecoded, _Mapping]] = ..., can: _Optional[_Union[CanFrameDecoded, _Mapping]] = ...) -> None: ...

class GetDecodedDataRequest(_message.Message):
    __slots__ = ("capture_id", "decoder_id")
    CAPTURE_ID_FIELD_NUMBER: _ClassVar[int]
    DECODER_ID_FIELD_NUMBER: _ClassVar[int]
    capture_id: str
    decoder_id: str
    def __init__(self, capture_id: _Optional[str] = ..., decoder_id: _Optional[str] = ...) -> None: ...

class GetDecodedDataResponse(_message.Message):
    __slots__ = ("success", "message", "data")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    data: _containers.RepeatedCompositeFieldContainer[DecodedData]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., data: _Optional[_Iterable[_Union[DecodedData, _Mapping]]] = ...) -> None: ...

class GpioConfigRequest(_message.Message):
    __slots__ = ("pin", "direction", "pull", "open_drain")
    PIN_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    PULL_FIELD_NUMBER: _ClassVar[int]
    OPEN_DRAIN_FIELD_NUMBER: _ClassVar[int]
    pin: int
    direction: GpioDirection
    pull: GpioPull
    open_drain: bool
    def __init__(self, pin: _Optional[int] = ..., direction: _Optional[_Union[GpioDirection, str]] = ..., pull: _Optional[_Union[GpioPull, str]] = ..., open_drain: bool = ...) -> None: ...

class GpioWriteRequest(_message.Message):
    __slots__ = ("pin", "value")
    PIN_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    pin: int
    value: bool
    def __init__(self, pin: _Optional[int] = ..., value: bool = ...) -> None: ...

class GpioReadRequest(_message.Message):
    __slots__ = ("pin",)
    PIN_FIELD_NUMBER: _ClassVar[int]
    pin: int
    def __init__(self, pin: _Optional[int] = ...) -> None: ...

class GpioReadResponse(_message.Message):
    __slots__ = ("success", "message", "value")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    value: bool
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., value: bool = ...) -> None: ...

class GpioWatchRequest(_message.Message):
    __slots__ = ("pin", "edge")
    class Edge(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        EDGE_RISING: _ClassVar[GpioWatchRequest.Edge]
        EDGE_FALLING: _ClassVar[GpioWatchRequest.Edge]
        EDGE_BOTH: _ClassVar[GpioWatchRequest.Edge]
    EDGE_RISING: GpioWatchRequest.Edge
    EDGE_FALLING: GpioWatchRequest.Edge
    EDGE_BOTH: GpioWatchRequest.Edge
    PIN_FIELD_NUMBER: _ClassVar[int]
    EDGE_FIELD_NUMBER: _ClassVar[int]
    pin: int
    edge: GpioWatchRequest.Edge
    def __init__(self, pin: _Optional[int] = ..., edge: _Optional[_Union[GpioWatchRequest.Edge, str]] = ...) -> None: ...

class GpioEventResponse(_message.Message):
    __slots__ = ("pin", "value", "timestamp")
    PIN_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    pin: int
    value: bool
    timestamp: Timestamp
    def __init__(self, pin: _Optional[int] = ..., value: bool = ..., timestamp: _Optional[_Union[Timestamp, _Mapping]] = ...) -> None: ...

class I2cConfig(_message.Message):
    __slots__ = ("bus", "speed_hz")
    BUS_FIELD_NUMBER: _ClassVar[int]
    SPEED_HZ_FIELD_NUMBER: _ClassVar[int]
    bus: int
    speed_hz: int
    def __init__(self, bus: _Optional[int] = ..., speed_hz: _Optional[int] = ...) -> None: ...

class I2cTransferRequest(_message.Message):
    __slots__ = ("bus", "address", "write_data", "read_size", "repeated_start")
    BUS_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    WRITE_DATA_FIELD_NUMBER: _ClassVar[int]
    READ_SIZE_FIELD_NUMBER: _ClassVar[int]
    REPEATED_START_FIELD_NUMBER: _ClassVar[int]
    bus: int
    address: int
    write_data: bytes
    read_size: int
    repeated_start: bool
    def __init__(self, bus: _Optional[int] = ..., address: _Optional[int] = ..., write_data: _Optional[bytes] = ..., read_size: _Optional[int] = ..., repeated_start: bool = ...) -> None: ...

class I2cTransferResponse(_message.Message):
    __slots__ = ("success", "message", "read_data", "nak")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    READ_DATA_FIELD_NUMBER: _ClassVar[int]
    NAK_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    read_data: bytes
    nak: bool
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., read_data: _Optional[bytes] = ..., nak: bool = ...) -> None: ...

class I2cScanRequest(_message.Message):
    __slots__ = ("bus",)
    BUS_FIELD_NUMBER: _ClassVar[int]
    bus: int
    def __init__(self, bus: _Optional[int] = ...) -> None: ...

class I2cScanResponse(_message.Message):
    __slots__ = ("success", "message", "addresses")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ADDRESSES_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    addresses: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., addresses: _Optional[_Iterable[int]] = ...) -> None: ...

class SpiConfig(_message.Message):
    __slots__ = ("bus", "speed_hz", "cpol", "cpha", "bits_per_word", "msb_first", "cs_pin")
    BUS_FIELD_NUMBER: _ClassVar[int]
    SPEED_HZ_FIELD_NUMBER: _ClassVar[int]
    CPOL_FIELD_NUMBER: _ClassVar[int]
    CPHA_FIELD_NUMBER: _ClassVar[int]
    BITS_PER_WORD_FIELD_NUMBER: _ClassVar[int]
    MSB_FIRST_FIELD_NUMBER: _ClassVar[int]
    CS_PIN_FIELD_NUMBER: _ClassVar[int]
    bus: int
    speed_hz: int
    cpol: bool
    cpha: bool
    bits_per_word: int
    msb_first: bool
    cs_pin: int
    def __init__(self, bus: _Optional[int] = ..., speed_hz: _Optional[int] = ..., cpol: bool = ..., cpha: bool = ..., bits_per_word: _Optional[int] = ..., msb_first: bool = ..., cs_pin: _Optional[int] = ...) -> None: ...

class SpiTransferRequest(_message.Message):
    __slots__ = ("bus", "tx_data", "rx_size", "keep_cs_active")
    BUS_FIELD_NUMBER: _ClassVar[int]
    TX_DATA_FIELD_NUMBER: _ClassVar[int]
    RX_SIZE_FIELD_NUMBER: _ClassVar[int]
    KEEP_CS_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    bus: int
    tx_data: bytes
    rx_size: int
    keep_cs_active: bool
    def __init__(self, bus: _Optional[int] = ..., tx_data: _Optional[bytes] = ..., rx_size: _Optional[int] = ..., keep_cs_active: bool = ...) -> None: ...

class SpiTransferResponse(_message.Message):
    __slots__ = ("success", "message", "rx_data")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    RX_DATA_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    rx_data: bytes
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., rx_data: _Optional[bytes] = ...) -> None: ...

class CanConfig(_message.Message):
    __slots__ = ("bus", "bitrate", "fd_enabled", "fd_data_bitrate")
    BUS_FIELD_NUMBER: _ClassVar[int]
    BITRATE_FIELD_NUMBER: _ClassVar[int]
    FD_ENABLED_FIELD_NUMBER: _ClassVar[int]
    FD_DATA_BITRATE_FIELD_NUMBER: _ClassVar[int]
    bus: int
    bitrate: int
    fd_enabled: bool
    fd_data_bitrate: int
    def __init__(self, bus: _Optional[int] = ..., bitrate: _Optional[int] = ..., fd_enabled: bool = ..., fd_data_bitrate: _Optional[int] = ...) -> None: ...

class CanFrame(_message.Message):
    __slots__ = ("id", "extended_id", "fd", "brs", "data", "timestamp")
    ID_FIELD_NUMBER: _ClassVar[int]
    EXTENDED_ID_FIELD_NUMBER: _ClassVar[int]
    FD_FIELD_NUMBER: _ClassVar[int]
    BRS_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    id: int
    extended_id: bool
    fd: bool
    brs: bool
    data: bytes
    timestamp: Timestamp
    def __init__(self, id: _Optional[int] = ..., extended_id: bool = ..., fd: bool = ..., brs: bool = ..., data: _Optional[bytes] = ..., timestamp: _Optional[_Union[Timestamp, _Mapping]] = ...) -> None: ...

class CanSendRequest(_message.Message):
    __slots__ = ("bus", "frame")
    BUS_FIELD_NUMBER: _ClassVar[int]
    FRAME_FIELD_NUMBER: _ClassVar[int]
    bus: int
    frame: CanFrame
    def __init__(self, bus: _Optional[int] = ..., frame: _Optional[_Union[CanFrame, _Mapping]] = ...) -> None: ...

class CanReceiveResponse(_message.Message):
    __slots__ = ("success", "message", "frame")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    FRAME_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    frame: CanFrame
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., frame: _Optional[_Union[CanFrame, _Mapping]] = ...) -> None: ...

class CanFilterConfig(_message.Message):
    __slots__ = ("id", "mask", "extended")
    ID_FIELD_NUMBER: _ClassVar[int]
    MASK_FIELD_NUMBER: _ClassVar[int]
    EXTENDED_FIELD_NUMBER: _ClassVar[int]
    id: int
    mask: int
    extended: bool
    def __init__(self, id: _Optional[int] = ..., mask: _Optional[int] = ..., extended: bool = ...) -> None: ...

class CanSetFilterRequest(_message.Message):
    __slots__ = ("bus", "filters")
    BUS_FIELD_NUMBER: _ClassVar[int]
    FILTERS_FIELD_NUMBER: _ClassVar[int]
    bus: int
    filters: _containers.RepeatedCompositeFieldContainer[CanFilterConfig]
    def __init__(self, bus: _Optional[int] = ..., filters: _Optional[_Iterable[_Union[CanFilterConfig, _Mapping]]] = ...) -> None: ...

class BleDevice(_message.Message):
    __slots__ = ("address", "name", "rssi", "advertising_data", "connectable")
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    RSSI_FIELD_NUMBER: _ClassVar[int]
    ADVERTISING_DATA_FIELD_NUMBER: _ClassVar[int]
    CONNECTABLE_FIELD_NUMBER: _ClassVar[int]
    address: str
    name: str
    rssi: int
    advertising_data: bytes
    connectable: bool
    def __init__(self, address: _Optional[str] = ..., name: _Optional[str] = ..., rssi: _Optional[int] = ..., advertising_data: _Optional[bytes] = ..., connectable: bool = ...) -> None: ...

class BleScanRequest(_message.Message):
    __slots__ = ("duration_s", "active")
    DURATION_S_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_FIELD_NUMBER: _ClassVar[int]
    duration_s: float
    active: bool
    def __init__(self, duration_s: _Optional[float] = ..., active: bool = ...) -> None: ...

class BleScanResponse(_message.Message):
    __slots__ = ("success", "message", "devices")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DEVICES_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    devices: _containers.RepeatedCompositeFieldContainer[BleDevice]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., devices: _Optional[_Iterable[_Union[BleDevice, _Mapping]]] = ...) -> None: ...

class BleConnectRequest(_message.Message):
    __slots__ = ("address",)
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    address: str
    def __init__(self, address: _Optional[str] = ...) -> None: ...

class BleConnectResponse(_message.Message):
    __slots__ = ("success", "message", "connection_id")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    CONNECTION_ID_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    connection_id: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., connection_id: _Optional[str] = ...) -> None: ...

class BleDisconnectRequest(_message.Message):
    __slots__ = ("connection_id",)
    CONNECTION_ID_FIELD_NUMBER: _ClassVar[int]
    connection_id: str
    def __init__(self, connection_id: _Optional[str] = ...) -> None: ...

class BleService(_message.Message):
    __slots__ = ("uuid", "characteristics")
    UUID_FIELD_NUMBER: _ClassVar[int]
    CHARACTERISTICS_FIELD_NUMBER: _ClassVar[int]
    uuid: str
    characteristics: _containers.RepeatedCompositeFieldContainer[BleCharacteristic]
    def __init__(self, uuid: _Optional[str] = ..., characteristics: _Optional[_Iterable[_Union[BleCharacteristic, _Mapping]]] = ...) -> None: ...

class BleCharacteristic(_message.Message):
    __slots__ = ("uuid", "properties", "handle")
    UUID_FIELD_NUMBER: _ClassVar[int]
    PROPERTIES_FIELD_NUMBER: _ClassVar[int]
    HANDLE_FIELD_NUMBER: _ClassVar[int]
    uuid: str
    properties: int
    handle: int
    def __init__(self, uuid: _Optional[str] = ..., properties: _Optional[int] = ..., handle: _Optional[int] = ...) -> None: ...

class BleDiscoverServicesRequest(_message.Message):
    __slots__ = ("connection_id",)
    CONNECTION_ID_FIELD_NUMBER: _ClassVar[int]
    connection_id: str
    def __init__(self, connection_id: _Optional[str] = ...) -> None: ...

class BleDiscoverServicesResponse(_message.Message):
    __slots__ = ("success", "message", "services")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SERVICES_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    services: _containers.RepeatedCompositeFieldContainer[BleService]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., services: _Optional[_Iterable[_Union[BleService, _Mapping]]] = ...) -> None: ...

class BleReadRequest(_message.Message):
    __slots__ = ("connection_id", "handle")
    CONNECTION_ID_FIELD_NUMBER: _ClassVar[int]
    HANDLE_FIELD_NUMBER: _ClassVar[int]
    connection_id: str
    handle: int
    def __init__(self, connection_id: _Optional[str] = ..., handle: _Optional[int] = ...) -> None: ...

class BleReadResponse(_message.Message):
    __slots__ = ("success", "message", "data")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    data: bytes
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., data: _Optional[bytes] = ...) -> None: ...

class BleWriteRequest(_message.Message):
    __slots__ = ("connection_id", "handle", "data", "with_response")
    CONNECTION_ID_FIELD_NUMBER: _ClassVar[int]
    HANDLE_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    WITH_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    connection_id: str
    handle: int
    data: bytes
    with_response: bool
    def __init__(self, connection_id: _Optional[str] = ..., handle: _Optional[int] = ..., data: _Optional[bytes] = ..., with_response: bool = ...) -> None: ...

class BleNotificationResponse(_message.Message):
    __slots__ = ("connection_id", "handle", "data", "timestamp")
    CONNECTION_ID_FIELD_NUMBER: _ClassVar[int]
    HANDLE_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    connection_id: str
    handle: int
    data: bytes
    timestamp: Timestamp
    def __init__(self, connection_id: _Optional[str] = ..., handle: _Optional[int] = ..., data: _Optional[bytes] = ..., timestamp: _Optional[_Union[Timestamp, _Mapping]] = ...) -> None: ...

class ZephyrShellRequest(_message.Message):
    __slots__ = ("session_id", "command", "timeout_s")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    COMMAND_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_S_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    command: str
    timeout_s: float
    def __init__(self, session_id: _Optional[str] = ..., command: _Optional[str] = ..., timeout_s: _Optional[float] = ...) -> None: ...

class ZephyrShellResponse(_message.Message):
    __slots__ = ("success", "message", "output", "return_code")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_FIELD_NUMBER: _ClassVar[int]
    RETURN_CODE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    output: str
    return_code: int
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., output: _Optional[str] = ..., return_code: _Optional[int] = ...) -> None: ...

class ZephyrLogEntry(_message.Message):
    __slots__ = ("timestamp", "level", "module", "message", "file", "line")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    MODULE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    FILE_FIELD_NUMBER: _ClassVar[int]
    LINE_FIELD_NUMBER: _ClassVar[int]
    timestamp: Timestamp
    level: ZephyrLogLevel
    module: str
    message: str
    file: str
    line: int
    def __init__(self, timestamp: _Optional[_Union[Timestamp, _Mapping]] = ..., level: _Optional[_Union[ZephyrLogLevel, str]] = ..., module: _Optional[str] = ..., message: _Optional[str] = ..., file: _Optional[str] = ..., line: _Optional[int] = ...) -> None: ...

class ZephyrLogStreamRequest(_message.Message):
    __slots__ = ("session_id", "min_level", "modules")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    MIN_LEVEL_FIELD_NUMBER: _ClassVar[int]
    MODULES_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    min_level: ZephyrLogLevel
    modules: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, session_id: _Optional[str] = ..., min_level: _Optional[_Union[ZephyrLogLevel, str]] = ..., modules: _Optional[_Iterable[str]] = ...) -> None: ...

class ZephyrLogStreamResponse(_message.Message):
    __slots__ = ("entries",)
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    entries: _containers.RepeatedCompositeFieldContainer[ZephyrLogEntry]
    def __init__(self, entries: _Optional[_Iterable[_Union[ZephyrLogEntry, _Mapping]]] = ...) -> None: ...

class ZephyrDevicetreeRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class ZephyrDevicetreeNode(_message.Message):
    __slots__ = ("path", "compatible", "label", "status", "properties", "children")
    class PropertiesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    PATH_FIELD_NUMBER: _ClassVar[int]
    COMPATIBLE_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PROPERTIES_FIELD_NUMBER: _ClassVar[int]
    CHILDREN_FIELD_NUMBER: _ClassVar[int]
    path: str
    compatible: str
    label: str
    status: str
    properties: _containers.ScalarMap[str, str]
    children: _containers.RepeatedCompositeFieldContainer[ZephyrDevicetreeNode]
    def __init__(self, path: _Optional[str] = ..., compatible: _Optional[str] = ..., label: _Optional[str] = ..., status: _Optional[str] = ..., properties: _Optional[_Mapping[str, str]] = ..., children: _Optional[_Iterable[_Union[ZephyrDevicetreeNode, _Mapping]]] = ...) -> None: ...

class ZephyrDevicetreeResponse(_message.Message):
    __slots__ = ("success", "message", "root")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ROOT_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    root: ZephyrDevicetreeNode
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., root: _Optional[_Union[ZephyrDevicetreeNode, _Mapping]] = ...) -> None: ...

class ZephyrThread(_message.Message):
    __slots__ = ("id", "name", "state", "priority", "stack_size", "stack_used", "cycles")
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATE_READY: _ClassVar[ZephyrThread.State]
        STATE_RUNNING: _ClassVar[ZephyrThread.State]
        STATE_PENDING: _ClassVar[ZephyrThread.State]
        STATE_SUSPENDED: _ClassVar[ZephyrThread.State]
        STATE_DEAD: _ClassVar[ZephyrThread.State]
    STATE_READY: ZephyrThread.State
    STATE_RUNNING: ZephyrThread.State
    STATE_PENDING: ZephyrThread.State
    STATE_SUSPENDED: ZephyrThread.State
    STATE_DEAD: ZephyrThread.State
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    STACK_SIZE_FIELD_NUMBER: _ClassVar[int]
    STACK_USED_FIELD_NUMBER: _ClassVar[int]
    CYCLES_FIELD_NUMBER: _ClassVar[int]
    id: int
    name: str
    state: ZephyrThread.State
    priority: int
    stack_size: int
    stack_used: int
    cycles: int
    def __init__(self, id: _Optional[int] = ..., name: _Optional[str] = ..., state: _Optional[_Union[ZephyrThread.State, str]] = ..., priority: _Optional[int] = ..., stack_size: _Optional[int] = ..., stack_used: _Optional[int] = ..., cycles: _Optional[int] = ...) -> None: ...

class ZephyrThreadsRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class ZephyrThreadsResponse(_message.Message):
    __slots__ = ("success", "message", "threads")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    THREADS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    threads: _containers.RepeatedCompositeFieldContainer[ZephyrThread]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., threads: _Optional[_Iterable[_Union[ZephyrThread, _Mapping]]] = ...) -> None: ...

class TestResult(_message.Message):
    __slots__ = ("name", "status", "duration_s", "message", "log")
    class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATUS_PASS: _ClassVar[TestResult.Status]
        STATUS_FAIL: _ClassVar[TestResult.Status]
        STATUS_SKIP: _ClassVar[TestResult.Status]
        STATUS_ERROR: _ClassVar[TestResult.Status]
    STATUS_PASS: TestResult.Status
    STATUS_FAIL: TestResult.Status
    STATUS_SKIP: TestResult.Status
    STATUS_ERROR: TestResult.Status
    NAME_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    DURATION_S_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    LOG_FIELD_NUMBER: _ClassVar[int]
    name: str
    status: TestResult.Status
    duration_s: float
    message: str
    log: str
    def __init__(self, name: _Optional[str] = ..., status: _Optional[_Union[TestResult.Status, str]] = ..., duration_s: _Optional[float] = ..., message: _Optional[str] = ..., log: _Optional[str] = ...) -> None: ...

class TwisterRunRequest(_message.Message):
    __slots__ = ("target_id", "test_path", "extra_args", "timeout_s")
    TARGET_ID_FIELD_NUMBER: _ClassVar[int]
    TEST_PATH_FIELD_NUMBER: _ClassVar[int]
    EXTRA_ARGS_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_S_FIELD_NUMBER: _ClassVar[int]
    target_id: str
    test_path: str
    extra_args: _containers.RepeatedScalarFieldContainer[str]
    timeout_s: float
    def __init__(self, target_id: _Optional[str] = ..., test_path: _Optional[str] = ..., extra_args: _Optional[_Iterable[str]] = ..., timeout_s: _Optional[float] = ...) -> None: ...

class TwisterRunResponse(_message.Message):
    __slots__ = ("success", "message", "results", "full_log")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    FULL_LOG_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    results: _containers.RepeatedCompositeFieldContainer[TestResult]
    full_log: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., results: _Optional[_Iterable[_Union[TestResult, _Mapping]]] = ..., full_log: _Optional[str] = ...) -> None: ...

class FileInfo(_message.Message):
    __slots__ = ("name", "size", "sha256", "modified")
    NAME_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    SHA256_FIELD_NUMBER: _ClassVar[int]
    MODIFIED_FIELD_NUMBER: _ClassVar[int]
    name: str
    size: int
    sha256: str
    modified: Timestamp
    def __init__(self, name: _Optional[str] = ..., size: _Optional[int] = ..., sha256: _Optional[str] = ..., modified: _Optional[_Union[Timestamp, _Mapping]] = ...) -> None: ...

class ListFilesRequest(_message.Message):
    __slots__ = ("directory",)
    DIRECTORY_FIELD_NUMBER: _ClassVar[int]
    directory: str
    def __init__(self, directory: _Optional[str] = ...) -> None: ...

class ListFilesResponse(_message.Message):
    __slots__ = ("success", "message", "files")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    FILES_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    files: _containers.RepeatedCompositeFieldContainer[FileInfo]
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., files: _Optional[_Iterable[_Union[FileInfo, _Mapping]]] = ...) -> None: ...

class UploadFileRequest(_message.Message):
    __slots__ = ("filename", "chunk", "final_chunk")
    FILENAME_FIELD_NUMBER: _ClassVar[int]
    CHUNK_FIELD_NUMBER: _ClassVar[int]
    FINAL_CHUNK_FIELD_NUMBER: _ClassVar[int]
    filename: str
    chunk: bytes
    final_chunk: bool
    def __init__(self, filename: _Optional[str] = ..., chunk: _Optional[bytes] = ..., final_chunk: bool = ...) -> None: ...

class UploadFileResponse(_message.Message):
    __slots__ = ("success", "message", "sha256")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SHA256_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    sha256: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., sha256: _Optional[str] = ...) -> None: ...

class DownloadFileRequest(_message.Message):
    __slots__ = ("filename", "offset", "size")
    FILENAME_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    filename: str
    offset: int
    size: int
    def __init__(self, filename: _Optional[str] = ..., offset: _Optional[int] = ..., size: _Optional[int] = ...) -> None: ...

class DownloadFileResponse(_message.Message):
    __slots__ = ("success", "message", "data", "eof")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    EOF_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    data: bytes
    eof: bool
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., data: _Optional[bytes] = ..., eof: bool = ...) -> None: ...

class DeleteFileRequest(_message.Message):
    __slots__ = ("filename",)
    FILENAME_FIELD_NUMBER: _ClassVar[int]
    filename: str
    def __init__(self, filename: _Optional[str] = ...) -> None: ...

class HealthCheckRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HealthCheckResponse(_message.Message):
    __slots__ = ("ready", "version", "errors", "capabilities")
    class CapabilitiesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    READY_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    ready: bool
    version: str
    errors: _containers.RepeatedScalarFieldContainer[str]
    capabilities: _containers.ScalarMap[str, str]
    def __init__(self, ready: bool = ..., version: _Optional[str] = ..., errors: _Optional[_Iterable[str]] = ..., capabilities: _Optional[_Mapping[str, str]] = ...) -> None: ...

class SystemInfoRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SystemInfoResponse(_message.Message):
    __slots__ = ("success", "message", "hostname", "os", "cpu_usage", "memory_usage", "disk_usage", "uptime")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    HOSTNAME_FIELD_NUMBER: _ClassVar[int]
    OS_FIELD_NUMBER: _ClassVar[int]
    CPU_USAGE_FIELD_NUMBER: _ClassVar[int]
    MEMORY_USAGE_FIELD_NUMBER: _ClassVar[int]
    DISK_USAGE_FIELD_NUMBER: _ClassVar[int]
    UPTIME_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    hostname: str
    os: str
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    uptime: Timestamp
    def __init__(self, success: bool = ..., message: _Optional[str] = ..., hostname: _Optional[str] = ..., os: _Optional[str] = ..., cpu_usage: _Optional[float] = ..., memory_usage: _Optional[float] = ..., disk_usage: _Optional[float] = ..., uptime: _Optional[_Union[Timestamp, _Mapping]] = ...) -> None: ...

class ObservabilityPowerReading(_message.Message):
    __slots__ = ("channel", "voltage_v", "current_ma", "power_mw", "enabled", "timestamp")
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    VOLTAGE_V_FIELD_NUMBER: _ClassVar[int]
    CURRENT_MA_FIELD_NUMBER: _ClassVar[int]
    POWER_MW_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    channel: PowerChannel
    voltage_v: float
    current_ma: float
    power_mw: float
    enabled: bool
    timestamp: Timestamp
    def __init__(self, channel: _Optional[_Union[PowerChannel, str]] = ..., voltage_v: _Optional[float] = ..., current_ma: _Optional[float] = ..., power_mw: _Optional[float] = ..., enabled: bool = ..., timestamp: _Optional[_Union[Timestamp, _Mapping]] = ...) -> None: ...

class ObservabilityGpioState(_message.Message):
    __slots__ = ("pin", "direction", "value", "configured", "last_changed")
    PIN_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    CONFIGURED_FIELD_NUMBER: _ClassVar[int]
    LAST_CHANGED_FIELD_NUMBER: _ClassVar[int]
    pin: int
    direction: GpioDirection
    value: bool
    configured: bool
    last_changed: Timestamp
    def __init__(self, pin: _Optional[int] = ..., direction: _Optional[_Union[GpioDirection, str]] = ..., value: bool = ..., configured: bool = ..., last_changed: _Optional[_Union[Timestamp, _Mapping]] = ...) -> None: ...

class ObservabilityUartStatus(_message.Message):
    __slots__ = ("port_name", "is_open", "baud_rate", "bytes_received", "bytes_sent", "client_count", "recent_lines")
    PORT_NAME_FIELD_NUMBER: _ClassVar[int]
    IS_OPEN_FIELD_NUMBER: _ClassVar[int]
    BAUD_RATE_FIELD_NUMBER: _ClassVar[int]
    BYTES_RECEIVED_FIELD_NUMBER: _ClassVar[int]
    BYTES_SENT_FIELD_NUMBER: _ClassVar[int]
    CLIENT_COUNT_FIELD_NUMBER: _ClassVar[int]
    RECENT_LINES_FIELD_NUMBER: _ClassVar[int]
    port_name: str
    is_open: bool
    baud_rate: int
    bytes_received: int
    bytes_sent: int
    client_count: int
    recent_lines: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, port_name: _Optional[str] = ..., is_open: bool = ..., baud_rate: _Optional[int] = ..., bytes_received: _Optional[int] = ..., bytes_sent: _Optional[int] = ..., client_count: _Optional[int] = ..., recent_lines: _Optional[_Iterable[str]] = ...) -> None: ...

class ObservabilitySystemMetrics(_message.Message):
    __slots__ = ("cpu_percent", "memory_percent", "disk_percent", "uptime_seconds", "hostname", "os_info", "hardware_revision", "server_version", "grpc_active_connections", "grpc_total_requests")
    CPU_PERCENT_FIELD_NUMBER: _ClassVar[int]
    MEMORY_PERCENT_FIELD_NUMBER: _ClassVar[int]
    DISK_PERCENT_FIELD_NUMBER: _ClassVar[int]
    UPTIME_SECONDS_FIELD_NUMBER: _ClassVar[int]
    HOSTNAME_FIELD_NUMBER: _ClassVar[int]
    OS_INFO_FIELD_NUMBER: _ClassVar[int]
    HARDWARE_REVISION_FIELD_NUMBER: _ClassVar[int]
    SERVER_VERSION_FIELD_NUMBER: _ClassVar[int]
    GRPC_ACTIVE_CONNECTIONS_FIELD_NUMBER: _ClassVar[int]
    GRPC_TOTAL_REQUESTS_FIELD_NUMBER: _ClassVar[int]
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    uptime_seconds: float
    hostname: str
    os_info: str
    hardware_revision: str
    server_version: str
    grpc_active_connections: int
    grpc_total_requests: int
    def __init__(self, cpu_percent: _Optional[float] = ..., memory_percent: _Optional[float] = ..., disk_percent: _Optional[float] = ..., uptime_seconds: _Optional[float] = ..., hostname: _Optional[str] = ..., os_info: _Optional[str] = ..., hardware_revision: _Optional[str] = ..., server_version: _Optional[str] = ..., grpc_active_connections: _Optional[int] = ..., grpc_total_requests: _Optional[int] = ...) -> None: ...

class ObservabilityClientInfo(_message.Message):
    __slots__ = ("client_id", "remote_addr", "connected_since", "active_rpcs")
    CLIENT_ID_FIELD_NUMBER: _ClassVar[int]
    REMOTE_ADDR_FIELD_NUMBER: _ClassVar[int]
    CONNECTED_SINCE_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_RPCS_FIELD_NUMBER: _ClassVar[int]
    client_id: str
    remote_addr: str
    connected_since: Timestamp
    active_rpcs: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, client_id: _Optional[str] = ..., remote_addr: _Optional[str] = ..., connected_since: _Optional[_Union[Timestamp, _Mapping]] = ..., active_rpcs: _Optional[_Iterable[str]] = ...) -> None: ...

class ObservabilityAdcReading(_message.Message):
    __slots__ = ("channel", "voltage_v", "raw_value")
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    VOLTAGE_V_FIELD_NUMBER: _ClassVar[int]
    RAW_VALUE_FIELD_NUMBER: _ClassVar[int]
    channel: int
    voltage_v: float
    raw_value: float
    def __init__(self, channel: _Optional[int] = ..., voltage_v: _Optional[float] = ..., raw_value: _Optional[float] = ...) -> None: ...

class ObservabilitySnapshot(_message.Message):
    __slots__ = ("timestamp", "power_readings", "gpio_states", "uart_ports", "system_metrics", "connected_clients", "adc_readings")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    POWER_READINGS_FIELD_NUMBER: _ClassVar[int]
    GPIO_STATES_FIELD_NUMBER: _ClassVar[int]
    UART_PORTS_FIELD_NUMBER: _ClassVar[int]
    SYSTEM_METRICS_FIELD_NUMBER: _ClassVar[int]
    CONNECTED_CLIENTS_FIELD_NUMBER: _ClassVar[int]
    ADC_READINGS_FIELD_NUMBER: _ClassVar[int]
    timestamp: Timestamp
    power_readings: _containers.RepeatedCompositeFieldContainer[ObservabilityPowerReading]
    gpio_states: _containers.RepeatedCompositeFieldContainer[ObservabilityGpioState]
    uart_ports: _containers.RepeatedCompositeFieldContainer[ObservabilityUartStatus]
    system_metrics: ObservabilitySystemMetrics
    connected_clients: _containers.RepeatedCompositeFieldContainer[ObservabilityClientInfo]
    adc_readings: _containers.RepeatedCompositeFieldContainer[ObservabilityAdcReading]
    def __init__(self, timestamp: _Optional[_Union[Timestamp, _Mapping]] = ..., power_readings: _Optional[_Iterable[_Union[ObservabilityPowerReading, _Mapping]]] = ..., gpio_states: _Optional[_Iterable[_Union[ObservabilityGpioState, _Mapping]]] = ..., uart_ports: _Optional[_Iterable[_Union[ObservabilityUartStatus, _Mapping]]] = ..., system_metrics: _Optional[_Union[ObservabilitySystemMetrics, _Mapping]] = ..., connected_clients: _Optional[_Iterable[_Union[ObservabilityClientInfo, _Mapping]]] = ..., adc_readings: _Optional[_Iterable[_Union[ObservabilityAdcReading, _Mapping]]] = ...) -> None: ...

class ObservabilityStreamRequest(_message.Message):
    __slots__ = ("interval_ms", "include_power", "include_gpio", "include_uart", "include_system", "include_clients", "include_uart_output")
    INTERVAL_MS_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_POWER_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_GPIO_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_UART_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_SYSTEM_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_CLIENTS_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_UART_OUTPUT_FIELD_NUMBER: _ClassVar[int]
    interval_ms: int
    include_power: bool
    include_gpio: bool
    include_uart: bool
    include_system: bool
    include_clients: bool
    include_uart_output: bool
    def __init__(self, interval_ms: _Optional[int] = ..., include_power: bool = ..., include_gpio: bool = ..., include_uart: bool = ..., include_system: bool = ..., include_clients: bool = ..., include_uart_output: bool = ...) -> None: ...

class ObservabilityStreamResponse(_message.Message):
    __slots__ = ("snapshot",)
    SNAPSHOT_FIELD_NUMBER: _ClassVar[int]
    snapshot: ObservabilitySnapshot
    def __init__(self, snapshot: _Optional[_Union[ObservabilitySnapshot, _Mapping]] = ...) -> None: ...
