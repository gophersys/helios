"""Tests for MTIB MCP server tools against the mock gRPC server.

Each test calls the MCP tool function directly (they are plain async functions)
and verifies the response structure and content.
"""

from __future__ import annotations

import json
import os

import pytest
import pytest_asyncio

# The MCP server tools use a module-level `client` singleton. We need to
# connect it to the mock server before the tools are called.
from mtib_mcp import server as mcp_server
from mtib_mcp.grpc_client import MtibClient


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _connect_mcp_client(mock_server):
    """Connect the MCP server's singleton client to the mock server."""
    _, port = mock_server
    os.environ["MTIB_HOST"] = "localhost"
    os.environ["MTIB_PORT"] = str(port)
    await mcp_server.client.connect()
    yield
    await mcp_server.client.close()


# =========================================================================
# 1. Discovery & Setup
# =========================================================================


@pytest.mark.asyncio
async def test_health_check():
    result = await mcp_server.mtib_health_check()
    data = json.loads(result)
    assert data["ready"] is True
    assert data["version"] == "2.0.0-mock"
    assert data["hostname"] == "mock-mtib"
    assert isinstance(data["cpu_usage_pct"], float)
    assert isinstance(data["capabilities"], dict)
    assert "debug" in data["capabilities"]


@pytest.mark.asyncio
async def test_list_targets():
    result = await mcp_server.mtib_list_targets()
    data = json.loads(result)
    assert len(data["targets"]) == 1
    target = data["targets"][0]
    assert target["id"] == "nrf52840_dk"
    assert target["chip"] == "nRF52840"
    assert target["has_debug"] is True
    assert target["flash_kb"] == 1024
    assert len(data["probes"]) == 1
    assert data["probes"][0]["type"] == "PROBE_JLINK"


# =========================================================================
# 2. Flash
# =========================================================================


@pytest.mark.asyncio
async def test_flash(tmp_path):
    # Create a dummy firmware file for the upload
    fw_path = tmp_path / "firmware.hex"
    fw_path.write_bytes(b"\x00" * 1024)

    result = await mcp_server.mtib_flash(
        target_id="nrf52840_dk",
        firmware_path=str(fw_path),
        verify=True,
        reset_after=True,
    )
    assert "65536 bytes" in result
    assert "1200 ms" in result


@pytest.mark.asyncio
async def test_reset():
    result = await mcp_server.mtib_reset(target_id="nrf52840_dk", reset_type="normal")
    assert "Reset (normal) complete" in result
    assert "running" in result


@pytest.mark.asyncio
async def test_reset_invalid_type():
    result = await mcp_server.mtib_reset(target_id="nrf52840_dk", reset_type="bogus")
    assert "Invalid reset_type" in result


# =========================================================================
# 3. Debug
# =========================================================================


@pytest.mark.asyncio
async def test_debug_connect():
    result = await mcp_server.mtib_debug_connect(target_id="nrf52840_dk")
    data = json.loads(result)
    assert "session_id" in data
    assert data["session_id"].startswith("mock-session-")
    assert data["state"] == "DEBUG_STATE_HALTED"

    # Disconnect
    disconnect_result = await mcp_server.mtib_debug_disconnect(data["session_id"])
    assert disconnect_result == "Disconnected"


@pytest.mark.asyncio
async def test_debug_status():
    connect = json.loads(await mcp_server.mtib_debug_connect(target_id="nrf52840_dk"))
    sid = connect["session_id"]

    result = await mcp_server.mtib_debug_status(session_id=sid, read_registers=True)
    data = json.loads(result)
    assert data["state"] == "DEBUG_STATE_HALTED"
    assert data["pc"] == "0x08001234"
    assert "registers" in data
    assert "PC" in data["registers"]

    await mcp_server.mtib_debug_disconnect(sid)


@pytest.mark.asyncio
async def test_debug_control():
    connect = json.loads(await mcp_server.mtib_debug_connect(target_id="nrf52840_dk"))
    sid = connect["session_id"]

    for action in ("halt", "resume", "step", "step_over"):
        result = await mcp_server.mtib_debug_control(session_id=sid, action=action)
        assert result == "OK"

    bad = await mcp_server.mtib_debug_control(session_id=sid, action="invalid")
    assert "Unknown action" in bad

    await mcp_server.mtib_debug_disconnect(sid)


@pytest.mark.asyncio
async def test_debug_backtrace():
    connect = json.loads(await mcp_server.mtib_debug_connect(target_id="nrf52840_dk"))
    sid = connect["session_id"]

    result = await mcp_server.mtib_debug_backtrace(session_id=sid)
    frames = json.loads(result)
    assert len(frames) == 2
    assert frames[0]["function"] == "main"
    assert frames[0]["pc"] == "0x08001234"

    await mcp_server.mtib_debug_disconnect(sid)


@pytest.mark.asyncio
async def test_debug_memory_read():
    connect = json.loads(await mcp_server.mtib_debug_connect(target_id="nrf52840_dk"))
    sid = connect["session_id"]

    result = await mcp_server.mtib_debug_memory(session_id=sid, address="0x20000000", size=32)
    assert "0x20000000:" in result

    await mcp_server.mtib_debug_disconnect(sid)


@pytest.mark.asyncio
async def test_debug_memory_write():
    connect = json.loads(await mcp_server.mtib_debug_connect(target_id="nrf52840_dk"))
    sid = connect["session_id"]

    result = await mcp_server.mtib_debug_memory(
        session_id=sid, address="0x20000000", write_hex="deadbeef"
    )
    assert "Wrote 4 bytes" in result

    await mcp_server.mtib_debug_disconnect(sid)


@pytest.mark.asyncio
async def test_debug_breakpoint():
    connect = json.loads(await mcp_server.mtib_debug_connect(target_id="nrf52840_dk"))
    sid = connect["session_id"]

    set_result = await mcp_server.mtib_debug_breakpoint(
        session_id=sid, action="set", address="0x08001234"
    )
    data = json.loads(set_result)
    assert data["breakpoint_id"] == 1

    clear_result = await mcp_server.mtib_debug_breakpoint(
        session_id=sid, action="clear", breakpoint_id=1
    )
    assert clear_result == "Cleared"

    await mcp_server.mtib_debug_disconnect(sid)


# =========================================================================
# 4. Serial & Logs
# =========================================================================


@pytest.mark.asyncio
async def test_uart_lifecycle():
    # Open
    open_result = await mcp_server.mtib_uart_open(target_id="nrf52840_dk", port_name="uart0")
    data = json.loads(open_result)
    assert data["status"] == "buffering"
    stream_key = data["stream_key"]

    # Give the background task a moment to buffer data
    import asyncio
    await asyncio.sleep(0.5)

    # Read
    read_result = await mcp_server.mtib_uart_read(stream_key=stream_key, cursor=0)
    read_data = json.loads(read_result)
    assert read_data["stream_key"] == stream_key
    assert isinstance(read_data["cursor"], int)

    # Close
    close_result = await mcp_server.mtib_uart_close(stream_key=stream_key)
    assert stream_key in close_result


@pytest.mark.asyncio
async def test_zephyr_shell():
    connect = json.loads(await mcp_server.mtib_debug_connect(target_id="nrf52840_dk"))
    sid = connect["session_id"]

    result = await mcp_server.mtib_zephyr_shell(session_id=sid, command="kernel version")
    assert "mocked shell output" in result
    assert "kernel version" in result

    await mcp_server.mtib_debug_disconnect(sid)


# =========================================================================
# 5. Power & Measurement
# =========================================================================


@pytest.mark.asyncio
async def test_power_measure():
    result = await mcp_server.mtib_power_measure(channel="MAIN", duration_s=1.0)
    data = json.loads(result)
    assert data["average_uA"] == 1250.5
    assert data["min_uA"] == 980.0
    assert data["max_uA"] == 3200.0
    assert data["energy_uJ"] == 4125.3
    assert data["samples"] == 1000


@pytest.mark.asyncio
async def test_power_measure_invalid_channel():
    result = await mcp_server.mtib_power_measure(channel="INVALID")
    assert "Unknown channel" in result


@pytest.mark.asyncio
async def test_power_control_enable():
    result = await mcp_server.mtib_power_control(action="enable", channel="MAIN", voltage_v=3.3)
    assert "Power enabled" in result


@pytest.mark.asyncio
async def test_power_control_status():
    result = await mcp_server.mtib_power_control(action="status", channel="MAIN")
    data = json.loads(result)
    assert data["enabled"] is True
    assert data["voltage_V"] == 3.3
    assert data["current_mA"] == 10.0


@pytest.mark.asyncio
async def test_power_control_disable():
    result = await mcp_server.mtib_power_control(action="disable", channel="MAIN")
    assert "Power disabled" in result


# =========================================================================
# 6. Testing
# =========================================================================


@pytest.mark.asyncio
async def test_twister_run():
    result = await mcp_server.mtib_twister_run(target_id="nrf52840_dk", test_path="tests/kernel/threads")
    data = json.loads(result)
    assert "2 passed" in data["summary"]
    assert "1 skipped" in data["summary"]
    assert len(data["results"]) == 3


# =========================================================================
# 7. Bus I/O
# =========================================================================


@pytest.mark.asyncio
async def test_i2c_scan():
    result = await mcp_server.mtib_i2c_scan(bus=1)
    data = json.loads(result)
    assert data["bus"] == 1
    assert data["count"] == 6
    assert "0x19" in data["devices"]
    assert "0x48" in data["devices"]


@pytest.mark.asyncio
async def test_i2c_transfer_read():
    result = await mcp_server.mtib_i2c_transfer(bus=1, address="0x48", read_size=2)
    data = json.loads(result)
    assert data["nak"] is False
    assert "read_hex" in data


@pytest.mark.asyncio
async def test_i2c_transfer_write():
    result = await mcp_server.mtib_i2c_transfer(bus=1, address="0x48", write_hex="0100")
    data = json.loads(result)
    assert data["nak"] is False


@pytest.mark.asyncio
async def test_i2c_transfer_invalid_address():
    result = await mcp_server.mtib_i2c_transfer(bus=1, address="not_hex")
    assert "Invalid address" in result
