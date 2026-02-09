from dataclasses import dataclass, field
from typing import List


@dataclass
class DebugSession:
    """An active debug session.

    Args:
        session_id: Unique session identifier for subsequent debug operations.
        state: Current debug state enum value.
    """

    session_id: str
    state: int


@dataclass
class DebugStatus:
    """Current debug probe status.

    Args:
        state: Current debug state enum value.
        pc: Program counter value (if halted).
        halt_reason: Reason for halt (breakpoint, watchpoint, etc.).
    """

    state: int
    pc: int = 0
    halt_reason: str = ""


@dataclass
class RegisterValue:
    """A CPU register value.

    Args:
        name: Register name (e.g. 'R0', 'SP', 'PC').
        value: Register value.
        size_bits: Register width in bits.
    """

    name: str
    value: int
    size_bits: int = 32


@dataclass
class StackFrame:
    """A stack frame from a backtrace.

    Args:
        level: Frame depth (0 = current).
        pc: Program counter at this frame.
        sp: Stack pointer at this frame.
        function: Symbol name if available.
        file: Source file path if available.
        line: Source line number if available.
    """

    level: int
    pc: int
    sp: int
    function: str = ""
    file: str = ""
    line: int = 0
