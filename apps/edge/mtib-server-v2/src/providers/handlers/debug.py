"""Debug probe handler for debug operations (connect, halt, step, breakpoints, memory, registers).

Integrates with ProbeManager for automatic probe-to-target resolution and
MUX switching when probe_id is "auto" or empty.
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Dict, Optional

from corekinect.utils import Logger
from src.shared.types import (
    BacktraceRequest,
    BacktraceResponse,
    ClearBreakpointRequest,
    DebugConnectRequest,
    DebugConnectResponse,
    DebugDisconnectRequest,
    DebugHaltRequest,
    DebugResumeRequest,
    DebugResetRequest,
    DebugState,
    DebugStatusRequest,
    DebugStatusResponse,
    DebugStepRequest,
    ReadMemoryRequest,
    ReadMemoryResponse,
    ReadRegistersRequest,
    ReadRegistersResponse,
    RegisterValue,
    Response,
    SetBreakpointRequest,
    SetBreakpointResponse,
    SetWatchpointRequest,
    SetWatchpointResponse,
    StackFrame,
    WriteMemoryRequest,
    WriteRegisterRequest,
)

if TYPE_CHECKING:
    from src.hardware import HardwareContext
    from .target import ProbeManager


class SessionState(Enum):
    """Internal session state machine."""
    DISCONNECTED = 0
    CONNECTED = 1
    HALTED = 2
    RUNNING = 3


@dataclass
class DebugSession:
    """Tracks state for an active debug connection."""
    session_id: str
    target_id: str
    probe_id: str
    state: SessionState = SessionState.CONNECTED
    speed_khz: int = 0
    breakpoints: Dict[int, int] = field(default_factory=dict)  # bp_id -> address
    watchpoints: Dict[int, int] = field(default_factory=dict)  # wp_id -> address
    _next_bp_id: int = 1
    _next_wp_id: int = 1

    def allocate_breakpoint_id(self) -> int:
        """Allocate a new breakpoint ID."""
        bp_id = self._next_bp_id
        self._next_bp_id += 1
        return bp_id

    def allocate_watchpoint_id(self) -> int:
        """Allocate a new watchpoint ID."""
        wp_id = self._next_wp_id
        self._next_wp_id += 1
        return wp_id


class DebugHandler:
    """Handles all debug probe RPCs (15 total).

    Uses ProbeManager (when available) for:
    - Auto-resolving probe_id="auto" to the correct probe serial
    - Setting J-Link MUX position based on probe→target mapping
    """

    def __init__(self, logger: Logger, hardware: "HardwareContext"):
        self.logger = logger
        self.hardware = hardware
        self._sessions: Dict[str, DebugSession] = {}
        self._probe_manager: Optional["ProbeManager"] = None

    def set_probe_manager(self, pm: "ProbeManager") -> None:
        """Set reference to ProbeManager for auto probe resolution."""
        self._probe_manager = pm

    def _get_session(self, session_id: str) -> Optional[DebugSession]:
        """Get a session by ID, or None if not found."""
        return self._sessions.get(session_id)

    def _require_session(self, session_id: str) -> tuple[Optional[DebugSession], Optional[Response]]:
        """Get session or return error response."""
        session = self._get_session(session_id)
        if session is None:
            return None, Response(success=False, message=f"No active session: {session_id}")
        return session, None

    def _state_to_proto(self, state: SessionState) -> int:
        """Convert internal state to proto DebugState."""
        mapping = {
            SessionState.DISCONNECTED: DebugState.DEBUG_STATE_UNKNOWN,
            SessionState.CONNECTED: DebugState.DEBUG_STATE_RUNNING,
            SessionState.RUNNING: DebugState.DEBUG_STATE_RUNNING,
            SessionState.HALTED: DebugState.DEBUG_STATE_HALTED,
        }
        return mapping.get(state, DebugState.DEBUG_STATE_UNKNOWN)

    def _resolve_probe(self, probe_id: str, target_id: str) -> tuple[str, Optional[str]]:
        """Resolve probe_id to an actual serial number.

        If probe_id is "auto" or empty and ProbeManager is available,
        auto-resolve to the correct probe for the target.  Also sets
        the J-Link MUX position.

        Returns:
            (resolved_probe_id, error_or_None)
        """
        if probe_id and probe_id != "auto":
            # Explicit probe — still set MUX if needed
            if self._probe_manager:
                mux_err = self._probe_manager.prepare_mux_for_target(target_id, probe_id)
                if mux_err:
                    self.logger.warning(f"MUX warning: {mux_err}")
            return probe_id, None

        # Auto-resolve via ProbeManager
        if self._probe_manager:
            serial, err = self._probe_manager.resolve_probe_for_target(target_id)
            if err:
                return "auto", err
            mux_err = self._probe_manager.prepare_mux_for_target(target_id, serial)
            if mux_err:
                self.logger.warning(f"MUX warning: {mux_err}")
            self.logger.info(f"Auto-resolved probe for {target_id}: {serial}")
            return serial, None

        # No ProbeManager — return "auto" and let downstream handle it
        return "auto", None

    def connect(self, request: DebugConnectRequest, context) -> DebugConnectResponse:
        """Connect to target via debug probe.

        Auto-resolves probe_id when set to "auto" or empty, using
        ProbeManager to find the correct probe and set the MUX.
        """
        try:
            session_id = str(uuid.uuid4())
            raw_probe_id = request.probe_id or "auto"

            # Resolve probe and set MUX
            probe_id, resolve_err = self._resolve_probe(raw_probe_id, request.target_id)
            if resolve_err:
                self.logger.warning(f"Probe resolution warning: {resolve_err}")
                # Non-fatal: continue with whatever we have

            session = DebugSession(
                session_id=session_id,
                target_id=request.target_id,
                probe_id=probe_id,
                speed_khz=request.speed_khz,
            )

            if request.halt_on_connect:
                session.state = SessionState.HALTED
            else:
                session.state = SessionState.RUNNING

            self._sessions[session_id] = session
            self.logger.info(
                f"Debug session created: {session_id[:12]}… → "
                f"{request.target_id} (probe={probe_id})"
            )

            return DebugConnectResponse(
                success=True,
                message="Connected",
                session_id=session_id,
                state=self._state_to_proto(session.state),
            )
        except Exception as e:
            return DebugConnectResponse(success=False, message=str(e), session_id="")

    def disconnect(self, request: DebugDisconnectRequest, context) -> Response:
        """Disconnect from target."""
        session = self._sessions.pop(request.session_id, None)
        if session is None:
            return Response(success=False, message=f"No active session: {request.session_id}")

        self.logger.info(f"Debug session closed: {request.session_id[:12]}…")
        return Response(success=True, message="Disconnected")

    def status(self, request: DebugStatusRequest, context) -> DebugStatusResponse:
        """Get current debug state."""
        session, err = self._require_session(request.session_id)
        if err:
            return DebugStatusResponse(success=False, message=err.message)

        # TODO: Read actual state from pyocd/pylink
        return DebugStatusResponse(
            success=True,
            message="",
            state=self._state_to_proto(session.state),
            pc=0,
            halt_reason="",
        )

    def halt(self, request: DebugHaltRequest, context) -> Response:
        """Halt target execution."""
        session, err = self._require_session(request.session_id)
        if err:
            return err

        # TODO: Actual halt via pyocd/pylink
        session.state = SessionState.HALTED
        return Response(success=True, message="Target halted")

    def resume(self, request: DebugResumeRequest, context) -> Response:
        """Resume target execution."""
        session, err = self._require_session(request.session_id)
        if err:
            return err

        # TODO: Actual resume via pyocd/pylink
        session.state = SessionState.RUNNING
        return Response(success=True, message="Target resumed")

    def step(self, request: DebugStepRequest, context) -> Response:
        """Single-step target execution."""
        session, err = self._require_session(request.session_id)
        if err:
            return err

        if session.state != SessionState.HALTED:
            return Response(success=False, message="Target must be halted to step")

        # TODO: Actual step via pyocd/pylink
        return Response(success=True, message="Step complete")

    def reset(self, request: DebugResetRequest, context) -> Response:
        """Reset target."""
        session, err = self._require_session(request.session_id)
        if err:
            return err

        # TODO: Actual reset via pyocd/pylink
        if request.halt_after_reset:
            session.state = SessionState.HALTED
        else:
            session.state = SessionState.RUNNING

        return Response(success=True, message="Target reset")

    def read_registers(self, request: ReadRegistersRequest, context) -> ReadRegistersResponse:
        """Read CPU registers."""
        session, err = self._require_session(request.session_id)
        if err:
            return ReadRegistersResponse(success=False, message=err.message)

        if session.state != SessionState.HALTED:
            return ReadRegistersResponse(success=False, message="Target must be halted to read registers")

        # TODO: Actual register read via pyocd/pylink
        # Return empty register list for now
        return ReadRegistersResponse(success=True, message="", registers=[])

    def write_register(self, request: WriteRegisterRequest, context) -> Response:
        """Write a CPU register."""
        session, err = self._require_session(request.session_id)
        if err:
            return err

        if session.state != SessionState.HALTED:
            return Response(success=False, message="Target must be halted to write registers")

        # TODO: Actual register write via pyocd/pylink
        return Response(success=True, message=f"Register {request.name} set to 0x{request.value:08X}")

    def read_memory(self, request: ReadMemoryRequest, context) -> ReadMemoryResponse:
        """Read target memory."""
        session, err = self._require_session(request.session_id)
        if err:
            return ReadMemoryResponse(success=False, message=err.message)

        if session.state != SessionState.HALTED:
            return ReadMemoryResponse(success=False, message="Target must be halted to read memory")

        # TODO: Actual memory read via pyocd/pylink
        return ReadMemoryResponse(success=True, message="", data=b"")

    def write_memory(self, request: WriteMemoryRequest, context) -> Response:
        """Write target memory."""
        session, err = self._require_session(request.session_id)
        if err:
            return err

        if session.state != SessionState.HALTED:
            return Response(success=False, message="Target must be halted to write memory")

        # TODO: Actual memory write via pyocd/pylink
        return Response(success=True, message=f"Wrote {len(request.data)} bytes to 0x{request.address:08X}")

    def set_breakpoint(self, request: SetBreakpointRequest, context) -> SetBreakpointResponse:
        """Set a breakpoint."""
        session, err = self._require_session(request.session_id)
        if err:
            return SetBreakpointResponse(success=False, message=err.message)

        bp_id = session.allocate_breakpoint_id()
        session.breakpoints[bp_id] = request.address

        # TODO: Actual breakpoint via pyocd/pylink
        self.logger.debug(f"Breakpoint {bp_id} set at 0x{request.address:08X}")
        return SetBreakpointResponse(success=True, message="", breakpoint_id=bp_id)

    def clear_breakpoint(self, request: ClearBreakpointRequest, context) -> Response:
        """Clear a breakpoint."""
        session, err = self._require_session(request.session_id)
        if err:
            return err

        if request.breakpoint_id not in session.breakpoints:
            return Response(success=False, message=f"Breakpoint {request.breakpoint_id} not found")

        del session.breakpoints[request.breakpoint_id]

        # TODO: Actual breakpoint removal via pyocd/pylink
        return Response(success=True, message="Breakpoint cleared")

    def set_watchpoint(self, request: SetWatchpointRequest, context) -> SetWatchpointResponse:
        """Set a watchpoint (data breakpoint)."""
        session, err = self._require_session(request.session_id)
        if err:
            return SetWatchpointResponse(success=False, message=err.message)

        wp_id = session.allocate_watchpoint_id()
        session.watchpoints[wp_id] = request.address

        # TODO: Actual watchpoint via pyocd/pylink
        return SetWatchpointResponse(success=True, message="", watchpoint_id=wp_id)

    def backtrace(self, request: BacktraceRequest, context) -> BacktraceResponse:
        """Get stack backtrace."""
        session, err = self._require_session(request.session_id)
        if err:
            return BacktraceResponse(success=False, message=err.message)

        if session.state != SessionState.HALTED:
            return BacktraceResponse(success=False, message="Target must be halted for backtrace")

        # TODO: Actual backtrace via pyocd/pylink
        return BacktraceResponse(success=True, message="", frames=[])
