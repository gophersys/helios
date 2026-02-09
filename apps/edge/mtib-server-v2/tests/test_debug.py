"""Tests for DebugHandler."""

import pytest

from src.providers.handlers.debug import DebugHandler, SessionState
from src.shared.types import (
    ClearBreakpointRequest,
    DebugConnectRequest,
    DebugDisconnectRequest,
    DebugHaltRequest,
    DebugResumeRequest,
    DebugResetRequest,
    DebugState,
    DebugStatusRequest,
    DebugStepRequest,
    ReadRegistersRequest,
    SetBreakpointRequest,
    SetWatchpointRequest,
    WriteRegisterRequest,
)


@pytest.fixture
def debug_handler(logger, hardware):
    return DebugHandler(logger, hardware)


@pytest.fixture
def connected_session(debug_handler, context):
    """Create a handler with an active debug session."""
    response = debug_handler.connect(
        DebugConnectRequest(target_id="nrf52840", probe_id="", speed_khz=0, halt_on_connect=False),
        context,
    )
    return response.session_id


class TestDebugConnect:
    def test_connect_succeeds(self, debug_handler, context):
        response = debug_handler.connect(
            DebugConnectRequest(target_id="nrf52840"),
            context,
        )
        assert response.success is True
        assert len(response.session_id) > 0

    def test_connect_running_state(self, debug_handler, context):
        response = debug_handler.connect(
            DebugConnectRequest(target_id="nrf52840", halt_on_connect=False),
            context,
        )
        assert response.state == DebugState.DEBUG_STATE_RUNNING

    def test_connect_halted_on_request(self, debug_handler, context):
        response = debug_handler.connect(
            DebugConnectRequest(target_id="nrf52840", halt_on_connect=True),
            context,
        )
        assert response.state == DebugState.DEBUG_STATE_HALTED


class TestDebugDisconnect:
    def test_disconnect_succeeds(self, debug_handler, context, connected_session):
        response = debug_handler.disconnect(
            DebugDisconnectRequest(session_id=connected_session),
            context,
        )
        assert response.success is True

    def test_disconnect_unknown_session(self, debug_handler, context):
        response = debug_handler.disconnect(
            DebugDisconnectRequest(session_id="nonexistent"),
            context,
        )
        assert response.success is False


class TestDebugHaltResume:
    def test_halt_succeeds(self, debug_handler, context, connected_session):
        response = debug_handler.halt(
            DebugHaltRequest(session_id=connected_session),
            context,
        )
        assert response.success is True

    def test_resume_succeeds(self, debug_handler, context, connected_session):
        debug_handler.halt(DebugHaltRequest(session_id=connected_session), context)
        response = debug_handler.resume(
            DebugResumeRequest(session_id=connected_session),
            context,
        )
        assert response.success is True

    def test_step_requires_halted(self, debug_handler, context, connected_session):
        # Session starts in RUNNING state, stepping should fail
        response = debug_handler.step(
            DebugStepRequest(session_id=connected_session),
            context,
        )
        assert response.success is False

    def test_step_succeeds_when_halted(self, debug_handler, context, connected_session):
        debug_handler.halt(DebugHaltRequest(session_id=connected_session), context)
        response = debug_handler.step(
            DebugStepRequest(session_id=connected_session),
            context,
        )
        assert response.success is True


class TestDebugBreakpoints:
    def test_set_breakpoint(self, debug_handler, context, connected_session):
        response = debug_handler.set_breakpoint(
            SetBreakpointRequest(session_id=connected_session, address=0x08000000),
            context,
        )
        assert response.success is True
        assert response.breakpoint_id > 0

    def test_clear_breakpoint(self, debug_handler, context, connected_session):
        bp = debug_handler.set_breakpoint(
            SetBreakpointRequest(session_id=connected_session, address=0x08000000),
            context,
        )
        response = debug_handler.clear_breakpoint(
            ClearBreakpointRequest(session_id=connected_session, breakpoint_id=bp.breakpoint_id),
            context,
        )
        assert response.success is True

    def test_clear_nonexistent_breakpoint(self, debug_handler, context, connected_session):
        response = debug_handler.clear_breakpoint(
            ClearBreakpointRequest(session_id=connected_session, breakpoint_id=999),
            context,
        )
        assert response.success is False

    def test_set_watchpoint(self, debug_handler, context, connected_session):
        response = debug_handler.set_watchpoint(
            SetWatchpointRequest(session_id=connected_session, address=0x20000000, size=4),
            context,
        )
        assert response.success is True
        assert response.watchpoint_id > 0


class TestDebugRegisters:
    def test_read_registers_requires_halted(self, debug_handler, context, connected_session):
        response = debug_handler.read_registers(
            ReadRegistersRequest(session_id=connected_session),
            context,
        )
        assert response.success is False

    def test_read_registers_when_halted(self, debug_handler, context, connected_session):
        debug_handler.halt(DebugHaltRequest(session_id=connected_session), context)
        response = debug_handler.read_registers(
            ReadRegistersRequest(session_id=connected_session),
            context,
        )
        assert response.success is True

    def test_write_register_requires_halted(self, debug_handler, context, connected_session):
        response = debug_handler.write_register(
            WriteRegisterRequest(session_id=connected_session, name="r0", value=42),
            context,
        )
        assert response.success is False
