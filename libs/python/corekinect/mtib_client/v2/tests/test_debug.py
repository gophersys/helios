"""Tests for debug probe operations."""

from corekinect.mtib_client.v2.types.debug import DebugSession, DebugStatus, RegisterValue, StackFrame


class TestDebugConnect:
    def test_debug_connect_returns_session(self, client):
        err, session = client.debug_connect(target_id="nrf52840_dk")
        assert err is None
        assert isinstance(session, DebugSession)
        assert session.session_id == "debug-session-001"

    def test_debug_connect_with_options(self, client):
        err, session = client.debug_connect(
            target_id="nrf52840_dk",
            probe_id="jlink-001",
            speed_khz=4000,
            halt_on_connect=True,
        )
        assert err is None
        assert session.session_id == "debug-session-001"


class TestDebugStatus:
    def test_debug_status_returns_state(self, client):
        err, status = client.debug_status(session_id="debug-session-001")
        assert err is None
        assert isinstance(status, DebugStatus)
        assert status.pc == 0x08000100
        assert status.halt_reason == "breakpoint"


class TestDebugDisconnect:
    def test_debug_disconnect(self, client):
        err = client.debug_disconnect(session_id="debug-session-001")
        assert err is None


class TestDebugControl:
    def test_debug_halt(self, client):
        err = client.debug_halt(session_id="debug-session-001")
        assert err is None

    def test_debug_resume(self, client):
        err = client.debug_resume(session_id="debug-session-001")
        assert err is None

    def test_debug_step(self, client):
        err = client.debug_step(session_id="debug-session-001")
        assert err is None

    def test_debug_reset(self, client):
        err = client.debug_reset(session_id="debug-session-001")
        assert err is None


class TestRegisters:
    def test_read_registers(self, client):
        err, regs = client.read_registers(session_id="debug-session-001")
        assert err is None
        assert len(regs) == 3
        assert isinstance(regs[0], RegisterValue)
        assert regs[0].name == "R0"
        assert regs[1].name == "PC"
        assert regs[1].value == 0x08000100

    def test_write_register(self, client):
        err = client.write_register(
            session_id="debug-session-001", name="R0", value=0x12345678
        )
        assert err is None


class TestMemory:
    def test_read_memory(self, client):
        err, data = client.read_memory(
            session_id="debug-session-001", address=0x20000000, size=16
        )
        assert err is None
        assert len(data) == 16

    def test_write_memory(self, client):
        err = client.write_memory(
            session_id="debug-session-001", address=0x20000000, data=b"\x01\x02\x03\x04"
        )
        assert err is None


class TestBreakpoints:
    def test_set_breakpoint(self, client):
        err, bp_id = client.set_breakpoint(
            session_id="debug-session-001", address=0x08000100
        )
        assert err is None
        assert bp_id == 1

    def test_clear_breakpoint(self, client):
        err = client.clear_breakpoint(session_id="debug-session-001", breakpoint_id=1)
        assert err is None

    def test_set_watchpoint(self, client):
        err, wp_id = client.set_watchpoint(
            session_id="debug-session-001", address=0x20000000, size=4
        )
        assert err is None
        assert wp_id == 1


class TestBacktrace:
    def test_backtrace(self, client):
        err, frames = client.backtrace(session_id="debug-session-001")
        assert err is None
        assert len(frames) == 1
        assert isinstance(frames[0], StackFrame)
        assert frames[0].function == "main"
        assert frames[0].file == "main.c"
        assert frames[0].line == 42
