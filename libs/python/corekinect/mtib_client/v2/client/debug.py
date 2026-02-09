from typing import List, Optional, Tuple

from protocols.mtib_v2.mtib_v2_pb2 import (
    BacktraceRequest,
    ClearBreakpointRequest,
    DebugConnectRequest,
    DebugDisconnectRequest,
    DebugHaltRequest,
    DebugResetRequest,
    DebugResumeRequest,
    DebugStatusRequest,
    DebugStepRequest,
    ReadMemoryRequest,
    ReadRegistersRequest,
    SetBreakpointRequest,
    SetWatchpointRequest,
    WriteMemoryRequest,
    WriteRegisterRequest,
)

from ._base import BaseClient
from ..types.debug import DebugSession, DebugStatus, RegisterValue, StackFrame


class DebugMixin(BaseClient):
    """Debug probe operations: connect, halt, resume, registers, memory, breakpoints."""

    def debug_connect(
        self,
        target_id: str,
        probe_id: str = "",
        speed_khz: int = 0,
        halt_on_connect: bool = False,
    ) -> Tuple[Optional[str], Optional[DebugSession]]:
        """Connect to a target via debug probe.

        Args:
            target_id: Target device ID.
            probe_id: Debug probe ID. Empty for auto-select.
            speed_khz: Interface speed in kHz. 0 for auto.
            halt_on_connect: Whether to halt the target on connect.

        Returns:
            (error, DebugSession) tuple. error is None on success.
        """
        try:
            resp = self._call(
                "DebugConnect",
                DebugConnectRequest(
                    target_id=target_id,
                    probe_id=probe_id,
                    speed_khz=speed_khz,
                    halt_on_connect=halt_on_connect,
                ),
            )
            if not resp.success:
                return resp.message, None
            return None, DebugSession(session_id=resp.session_id, state=resp.state)
        except Exception as e:
            return f"debug_connect error: {e}", None

    def debug_disconnect(self, session_id: str) -> Optional[str]:
        """Disconnect from a debug session.

        Args:
            session_id: Active debug session ID.

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call("DebugDisconnect", DebugDisconnectRequest(session_id=session_id))
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"debug_disconnect error: {e}"

    def debug_status(self, session_id: str) -> Tuple[Optional[str], Optional[DebugStatus]]:
        """Get current debug status.

        Args:
            session_id: Active debug session ID.

        Returns:
            (error, DebugStatus) tuple. error is None on success.
        """
        try:
            resp = self._call("DebugStatus", DebugStatusRequest(session_id=session_id))
            if not resp.success:
                return resp.message, None
            return None, DebugStatus(state=resp.state, pc=resp.pc, halt_reason=resp.halt_reason)
        except Exception as e:
            return f"debug_status error: {e}", None

    def debug_halt(self, session_id: str) -> Optional[str]:
        """Halt the target CPU.

        Args:
            session_id: Active debug session ID.

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call("DebugHalt", DebugHaltRequest(session_id=session_id))
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"debug_halt error: {e}"

    def debug_resume(self, session_id: str) -> Optional[str]:
        """Resume target CPU execution.

        Args:
            session_id: Active debug session ID.

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call("DebugResume", DebugResumeRequest(session_id=session_id))
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"debug_resume error: {e}"

    def debug_step(self, session_id: str, step_over: bool = False) -> Optional[str]:
        """Single-step the target CPU.

        Args:
            session_id: Active debug session ID.
            step_over: If True, step over function calls.

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call(
                "DebugStep", DebugStepRequest(session_id=session_id, step_over=step_over)
            )
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"debug_step error: {e}"

    def debug_reset(
        self, session_id: str, halt_after_reset: bool = False, reset_type: int = 0
    ) -> Optional[str]:
        """Reset the target CPU.

        Args:
            session_id: Active debug session ID.
            halt_after_reset: Whether to halt immediately after reset.
            reset_type: Reset type (0=NORMAL, 1=HARD, 2=CORE, 3=SYSTEM).

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call(
                "DebugReset",
                DebugResetRequest(
                    session_id=session_id, halt_after_reset=halt_after_reset, type=reset_type
                ),
            )
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"debug_reset error: {e}"

    def read_registers(
        self, session_id: str, names: List[str] = None
    ) -> Tuple[Optional[str], List[RegisterValue]]:
        """Read CPU registers.

        Args:
            session_id: Active debug session ID.
            names: Register names to read. Empty/None for all core registers.

        Returns:
            (error, list[RegisterValue]) tuple. error is None on success.
        """
        try:
            resp = self._call(
                "ReadRegisters",
                ReadRegistersRequest(session_id=session_id, names=names or []),
            )
            if not resp.success:
                return resp.message, []
            regs = [
                RegisterValue(name=r.name, value=r.value, size_bits=r.size_bits)
                for r in resp.registers
            ]
            return None, regs
        except Exception as e:
            return f"read_registers error: {e}", []

    def write_register(self, session_id: str, name: str, value: int) -> Optional[str]:
        """Write a CPU register.

        Args:
            session_id: Active debug session ID.
            name: Register name.
            value: Value to write.

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call(
                "WriteRegister",
                WriteRegisterRequest(session_id=session_id, name=name, value=value),
            )
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"write_register error: {e}"

    def read_memory(
        self, session_id: str, address: int, size: int, width: int = 0
    ) -> Tuple[Optional[str], bytes]:
        """Read target memory.

        Args:
            session_id: Active debug session ID.
            address: Memory address to read from.
            size: Number of bytes to read.
            width: Access width (0=8-bit, 1=16-bit, 2=32-bit).

        Returns:
            (error, bytes) tuple. error is None on success.
        """
        try:
            resp = self._call(
                "ReadMemory",
                ReadMemoryRequest(session_id=session_id, address=address, size=size, width=width),
            )
            if not resp.success:
                return resp.message, b""
            return None, resp.data
        except Exception as e:
            return f"read_memory error: {e}", b""

    def write_memory(
        self, session_id: str, address: int, data: bytes, width: int = 0
    ) -> Optional[str]:
        """Write target memory.

        Args:
            session_id: Active debug session ID.
            address: Memory address to write to.
            data: Data to write.
            width: Access width (0=8-bit, 1=16-bit, 2=32-bit).

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call(
                "WriteMemory",
                WriteMemoryRequest(session_id=session_id, address=address, data=data, width=width),
            )
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"write_memory error: {e}"

    def set_breakpoint(
        self, session_id: str, address: int, bp_type: int = 0
    ) -> Tuple[Optional[str], Optional[int]]:
        """Set a breakpoint.

        Args:
            session_id: Active debug session ID.
            address: Address to set breakpoint at.
            bp_type: Breakpoint type (0=HARDWARE, 1=SOFTWARE).

        Returns:
            (error, breakpoint_id) tuple. error is None on success.
        """
        try:
            resp = self._call(
                "SetBreakpoint",
                SetBreakpointRequest(session_id=session_id, address=address, type=bp_type),
            )
            if not resp.success:
                return resp.message, None
            return None, resp.breakpoint_id
        except Exception as e:
            return f"set_breakpoint error: {e}", None

    def clear_breakpoint(self, session_id: str, breakpoint_id: int) -> Optional[str]:
        """Clear a breakpoint.

        Args:
            session_id: Active debug session ID.
            breakpoint_id: ID of breakpoint to clear.

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call(
                "ClearBreakpoint",
                ClearBreakpointRequest(session_id=session_id, breakpoint_id=breakpoint_id),
            )
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"clear_breakpoint error: {e}"

    def set_watchpoint(
        self, session_id: str, address: int, size: int, mode: int = 1
    ) -> Tuple[Optional[str], Optional[int]]:
        """Set a data watchpoint.

        Args:
            session_id: Active debug session ID.
            address: Memory address to watch.
            size: Size of watched region in bytes.
            mode: Watch mode (0=READ, 1=WRITE, 2=READ_WRITE).

        Returns:
            (error, watchpoint_id) tuple. error is None on success.
        """
        try:
            resp = self._call(
                "SetWatchpoint",
                SetWatchpointRequest(
                    session_id=session_id, address=address, size=size, mode=mode
                ),
            )
            if not resp.success:
                return resp.message, None
            return None, resp.watchpoint_id
        except Exception as e:
            return f"set_watchpoint error: {e}", None

    def backtrace(
        self, session_id: str, max_frames: int = 32
    ) -> Tuple[Optional[str], List[StackFrame]]:
        """Get a stack backtrace.

        Args:
            session_id: Active debug session ID.
            max_frames: Maximum number of frames to return.

        Returns:
            (error, list[StackFrame]) tuple. error is None on success.
        """
        try:
            resp = self._call(
                "Backtrace", BacktraceRequest(session_id=session_id, max_frames=max_frames)
            )
            if not resp.success:
                return resp.message, []
            frames = [
                StackFrame(
                    level=f.level,
                    pc=f.pc,
                    sp=f.sp,
                    function=f.function,
                    file=f.file,
                    line=f.line,
                )
                for f in resp.frames
            ]
            return None, frames
        except Exception as e:
            return f"backtrace error: {e}", []
