"""MTIB V2 MCP Server — exposes embedded test bench operations as MCP tools."""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import grpc.aio
from mcp.server.fastmcp import FastMCP

from .grpc_client import MtibClient
from .proto import mtib_v2_pb2 as pb

# ---------------------------------------------------------------------------
# Lifespan — single shared gRPC client
# ---------------------------------------------------------------------------

client = MtibClient()


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    await client.connect()
    try:
        yield {"client": client}
    finally:
        await client.close()


mcp = FastMCP(
    "mtib",
    instructions="MTIB V2 embedded test bench — flash, debug, measure, and test Zephyr targets",
    lifespan=lifespan,
)


def _grpc_error(e: grpc.aio.AioRpcError) -> str:
    return f"gRPC error: {e.code().name} — {e.details()}"


# =========================================================================
# 1. Discovery & Setup
# =========================================================================


@mcp.tool()
async def mtib_health_check() -> str:
    """Check MTIB connectivity, firmware version, and capabilities."""
    try:
        health = await client.stub.HealthCheck(pb.HealthCheckRequest())
        info = await client.stub.SystemInfo(pb.SystemInfoRequest())
        caps = dict(health.capabilities) if health.capabilities else {}
        return json.dumps(
            {
                "ready": health.ready,
                "version": health.version,
                "errors": list(health.errors),
                "capabilities": caps,
                "hostname": info.hostname,
                "os": info.os,
                "cpu_usage_pct": round(info.cpu_usage, 1),
                "memory_usage_pct": round(info.memory_usage, 1),
                "disk_usage_pct": round(info.disk_usage, 1),
            },
            indent=2,
        )
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


@mcp.tool()
async def mtib_list_targets() -> str:
    """List available target devices and debug probes on the test bench."""
    try:
        targets_resp = await client.stub.ListTargets(pb.Empty())
        probes_resp = await client.stub.ListProbes(pb.Empty())

        targets = []
        for t in targets_resp.targets:
            targets.append(
                {
                    "id": t.id,
                    "name": t.name,
                    "arch": pb.Architecture.Name(t.arch),
                    "chip": t.chip,
                    "board": t.board,
                    "has_debug": t.has_debug,
                    "has_uart": t.has_uart,
                    "flash_kb": t.flash_size_kb,
                    "ram_kb": t.ram_size_kb,
                }
            )

        probes = []
        for p in probes_resp.probes:
            probes.append(
                {
                    "id": p.id,
                    "type": pb.DebugProbeType.Name(p.type),
                    "serial": p.serial,
                    "firmware": p.firmware_version,
                    "supported_targets": list(p.supported_targets),
                }
            )

        return json.dumps({"targets": targets, "probes": probes}, indent=2)
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


# =========================================================================
# 2. Build & Flash
# =========================================================================


@mcp.tool()
async def mtib_flash(
    target_id: str,
    firmware_path: str,
    verify: bool = True,
    reset_after: bool = True,
) -> str:
    """Flash firmware (.hex/.bin/.elf) to a target device.

    Uploads the file, connects the debug probe, programs flash, and
    optionally verifies and resets the target.
    """
    try:
        # Upload firmware to MTIB server
        sha = await client.upload_file(firmware_path)

        # Connect debug probe
        conn = await client.stub.DebugConnect(
            pb.DebugConnectRequest(target_id=target_id)
        )
        if not conn.success:
            return f"Failed to connect debug probe: {conn.message}"

        session_id = conn.session_id
        try:
            resp = await client.stub.FlashProgram(
                pb.FlashProgramRequest(
                    session_id=session_id,
                    filename=os.path.basename(firmware_path),
                    erase_before=True,
                    verify_after=verify,
                    reset_after=reset_after,
                )
            )
            if not resp.success:
                return f"Flash failed: {resp.message}"
            return (
                f"Flashed {resp.bytes_programmed} bytes in {resp.time_ms} ms "
                f"(sha256={sha[:16]}..., verify={verify}, reset={reset_after})"
            )
        finally:
            await client.stub.DebugDisconnect(
                pb.DebugDisconnectRequest(session_id=session_id)
            )
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


@mcp.tool()
async def mtib_reset(
    target_id: str,
    reset_type: str = "normal",
    halt_after: bool = False,
) -> str:
    """Reset a target device.

    reset_type: "normal", "hard", "core", or "system"
    """
    type_map = {
        "normal": pb.DebugResetRequest.RESET_NORMAL,
        "hard": pb.DebugResetRequest.RESET_HARD,
        "core": pb.DebugResetRequest.RESET_CORE,
        "system": pb.DebugResetRequest.RESET_SYSTEM,
    }
    if reset_type not in type_map:
        return f"Invalid reset_type '{reset_type}'. Use: {', '.join(type_map)}"
    try:
        conn = await client.stub.DebugConnect(
            pb.DebugConnectRequest(target_id=target_id)
        )
        if not conn.success:
            return f"Failed to connect: {conn.message}"
        try:
            resp = await client.stub.DebugReset(
                pb.DebugResetRequest(
                    session_id=conn.session_id,
                    halt_after_reset=halt_after,
                    type=type_map[reset_type],
                )
            )
            state = "halted" if halt_after else "running"
            if resp.success:
                return f"Reset ({reset_type}) complete — target is {state}"
            return f"Reset failed: {resp.message}"
        finally:
            if not halt_after:
                await client.stub.DebugDisconnect(
                    pb.DebugDisconnectRequest(session_id=conn.session_id)
                )
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


# =========================================================================
# 3. Debug
# =========================================================================


@mcp.tool()
async def mtib_debug_connect(
    target_id: str,
    probe_id: str = "",
    speed_khz: int = 0,
    halt: bool = True,
) -> str:
    """Connect a debug probe to a target. Returns a session_id for subsequent debug operations.

    The session_id must be passed to other mtib_debug_* tools.
    Call mtib_debug_disconnect when done.
    """
    try:
        resp = await client.stub.DebugConnect(
            pb.DebugConnectRequest(
                target_id=target_id,
                probe_id=probe_id,
                speed_khz=speed_khz,
                halt_on_connect=halt,
            )
        )
        if not resp.success:
            return f"Connect failed: {resp.message}"
        return json.dumps(
            {
                "session_id": resp.session_id,
                "state": pb.DebugState.Name(resp.state),
            }
        )
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


@mcp.tool()
async def mtib_debug_disconnect(session_id: str) -> str:
    """Disconnect a debug session. Always call this when done debugging."""
    try:
        resp = await client.stub.DebugDisconnect(
            pb.DebugDisconnectRequest(session_id=session_id)
        )
        return "Disconnected" if resp.success else f"Disconnect failed: {resp.message}"
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


@mcp.tool()
async def mtib_debug_status(session_id: str, read_registers: bool = True) -> str:
    """Get debug state: halt reason, PC, and optionally all core registers."""
    try:
        status = await client.stub.DebugStatus(
            pb.DebugStatusRequest(session_id=session_id)
        )
        result: dict = {
            "state": pb.DebugState.Name(status.state),
            "pc": f"0x{status.pc:08x}",
            "halt_reason": status.halt_reason,
        }
        if read_registers:
            regs = await client.stub.ReadRegisters(
                pb.ReadRegistersRequest(session_id=session_id)
            )
            result["registers"] = {
                r.name: f"0x{r.value:08x}" for r in regs.registers
            }
        return json.dumps(result, indent=2)
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


@mcp.tool()
async def mtib_debug_control(
    session_id: str, action: str = "halt"
) -> str:
    """Control target execution.

    action: "halt", "resume", "step", or "step_over"
    """
    try:
        if action == "halt":
            resp = await client.stub.DebugHalt(
                pb.DebugHaltRequest(session_id=session_id)
            )
        elif action == "resume":
            resp = await client.stub.DebugResume(
                pb.DebugResumeRequest(session_id=session_id)
            )
        elif action in ("step", "step_over"):
            resp = await client.stub.DebugStep(
                pb.DebugStepRequest(
                    session_id=session_id, step_over=(action == "step_over")
                )
            )
        else:
            return f"Unknown action '{action}'. Use: halt, resume, step, step_over"
        return "OK" if resp.success else f"Failed: {resp.message}"
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


@mcp.tool()
async def mtib_debug_backtrace(session_id: str, max_frames: int = 20) -> str:
    """Get the call stack trace (target must be halted)."""
    try:
        resp = await client.stub.Backtrace(
            pb.BacktraceRequest(session_id=session_id, max_frames=max_frames)
        )
        if not resp.success:
            return f"Backtrace failed: {resp.message}"
        frames = []
        for f in resp.frames:
            frames.append(
                {
                    "level": f.level,
                    "pc": f"0x{f.pc:08x}",
                    "function": f.function or "??",
                    "file": f"{f.file}:{f.line}" if f.file else "",
                }
            )
        return json.dumps(frames, indent=2)
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


@mcp.tool()
async def mtib_debug_memory(
    session_id: str,
    address: str,
    size: int = 256,
    write_hex: str = "",
    width: int = 8,
) -> str:
    """Read or write target memory.

    address: hex string like "0x20000000"
    size: bytes to read (ignored on write)
    write_hex: hex string to write (e.g. "deadbeef"). Empty = read.
    width: access width in bits — 8, 16, or 32
    """
    width_map = {8: 0, 16: 1, 32: 2}  # maps to AccessWidth enum
    if width not in width_map:
        return f"Invalid width {width}. Use: 8, 16, or 32"
    try:
        addr = int(address, 0)
    except ValueError:
        return f"Invalid address '{address}'"

    try:
        if write_hex:
            data = bytes.fromhex(write_hex)
            resp = await client.stub.WriteMemory(
                pb.WriteMemoryRequest(
                    session_id=session_id,
                    address=addr,
                    data=data,
                    width=width_map[width],
                )
            )
            return f"Wrote {len(data)} bytes to 0x{addr:08x}" if resp.success else f"Write failed: {resp.message}"
        else:
            resp = await client.stub.ReadMemory(
                pb.ReadMemoryRequest(
                    session_id=session_id,
                    address=addr,
                    size=size,
                    width=width_map[width],
                )
            )
            if not resp.success:
                return f"Read failed: {resp.message}"
            hex_dump = resp.data.hex()
            # Format as 16-byte lines
            lines = [f"0x{addr + i:08x}: {hex_dump[i*2:i*2+32]}" for i in range(0, len(resp.data), 16)]
            return "\n".join(lines)
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


@mcp.tool()
async def mtib_debug_breakpoint(
    session_id: str,
    action: str = "set",
    address: str = "",
    breakpoint_id: int = -1,
    bp_type: str = "hardware",
) -> str:
    """Set or clear a breakpoint.

    action: "set" or "clear"
    address: hex address for set (e.g. "0x08001234")
    breakpoint_id: ID returned by set, required for clear
    bp_type: "hardware" or "software"
    """
    try:
        if action == "set":
            if not address:
                return "address is required for set"
            addr = int(address, 0)
            bp = pb.BP_HARDWARE if bp_type == "hardware" else pb.BP_SOFTWARE
            resp = await client.stub.SetBreakpoint(
                pb.SetBreakpointRequest(
                    session_id=session_id, address=addr, type=bp
                )
            )
            if not resp.success:
                return f"Set breakpoint failed: {resp.message}"
            return json.dumps({"breakpoint_id": resp.breakpoint_id, "address": f"0x{addr:08x}"})
        elif action == "clear":
            if breakpoint_id < 0:
                return "breakpoint_id is required for clear"
            resp = await client.stub.ClearBreakpoint(
                pb.ClearBreakpointRequest(
                    session_id=session_id, breakpoint_id=breakpoint_id
                )
            )
            return "Cleared" if resp.success else f"Clear failed: {resp.message}"
        else:
            return f"Unknown action '{action}'. Use: set, clear"
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


# =========================================================================
# 4. Serial & Logs
#
# UART and Zephyr log streams stay open between tool calls so that no
# data is lost.  A background asyncio task continuously drains each gRPC
# stream into a ring buffer.  The read tools pull from the buffer using a
# monotonic cursor — pass the returned `cursor` back on the next call to
# get only new data.
# =========================================================================


@mcp.tool()
async def mtib_uart_open(
    target_id: str,
    port_name: str = "uart0",
    baud: int = 115200,
) -> str:
    """Open a UART port and start continuously buffering its output.

    The port stays open (and buffering) until mtib_uart_close is called.
    Returns a stream_key to pass to mtib_uart_read / mtib_uart_close.
    """
    try:
        key = await client.uart_open(target_id, port_name, baud)
        return json.dumps({"stream_key": key, "status": "buffering"})
    except Exception as e:
        return f"Failed to open UART: {e}"


@mcp.tool()
async def mtib_uart_read(
    stream_key: str,
    cursor: int = 0,
    limit: int = 200,
) -> str:
    """Read buffered UART output since the last cursor.

    On the first call pass cursor=0 to get all buffered lines.
    On subsequent calls pass the returned cursor to get only new lines.
    No data is lost between calls — the stream is buffered continuously.
    """
    try:
        entries, new_cursor = await client.uart_read(stream_key, cursor, limit)
        lines = [e["line"] for e in entries]
        return json.dumps(
            {
                "lines": lines,
                "count": len(lines),
                "cursor": new_cursor,
                "stream_key": stream_key,
            },
            indent=2,
        )
    except Exception as e:
        return f"UART read error: {e}"


@mcp.tool()
async def mtib_uart_close(stream_key: str) -> str:
    """Close a UART stream and stop buffering. Any unread data in the buffer is discarded."""
    try:
        await client.uart_close(stream_key)
        return f"Closed {stream_key}"
    except Exception as e:
        return f"UART close error: {e}"


@mcp.tool()
async def mtib_zephyr_shell(
    session_id: str,
    command: str,
    timeout_s: float = 10.0,
) -> str:
    """Execute a Zephyr shell command and return its output.

    session_id: a UART stream_id or debug session_id
    """
    try:
        resp = await client.stub.ZephyrShell(
            pb.ZephyrShellRequest(
                session_id=session_id,
                command=command,
                timeout_s=timeout_s,
            )
        )
        if not resp.success:
            return f"Shell command failed: {resp.message}"
        result = resp.output
        if resp.return_code != 0:
            result += f"\n(return code: {resp.return_code})"
        return result
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


@mcp.tool()
async def mtib_zephyr_logs_open(
    session_id: str,
    min_level: str = "ERR",
    modules: str = "",
) -> str:
    """Start continuously buffering Zephyr log entries.

    The stream stays open until mtib_zephyr_logs_close is called.
    min_level: "ERR", "WRN", "INF", or "DBG"
    modules: comma-separated module filter (empty = all)
    """
    level_map = {"ERR": 0, "WRN": 1, "INF": 2, "DBG": 3}
    level = level_map.get(min_level.upper(), 0)
    mod_list = [m.strip() for m in modules.split(",") if m.strip()] if modules else []
    try:
        key = await client.logs_open(session_id, level, mod_list)
        return json.dumps({"stream_key": key, "status": "buffering"})
    except Exception as e:
        return f"Failed to open log stream: {e}"


@mcp.tool()
async def mtib_zephyr_logs_read(
    stream_key: str,
    cursor: int = 0,
    limit: int = 200,
) -> str:
    """Read buffered Zephyr log entries since the last cursor.

    Pass cursor=0 on the first call.  Pass the returned cursor on
    subsequent calls to get only new entries.  No data is lost between calls.
    """
    try:
        entries, new_cursor = await client.logs_read(stream_key, cursor, limit)
        if not entries:
            return json.dumps({"entries": [], "count": 0, "cursor": new_cursor})
        lines = []
        for e in entries:
            lines.append(f"[{e['level']}] {e['module']}: {e['message']}")
        return json.dumps(
            {
                "entries": lines,
                "count": len(lines),
                "cursor": new_cursor,
                "stream_key": stream_key,
            },
            indent=2,
        )
    except Exception as e:
        return f"Log read error: {e}"


@mcp.tool()
async def mtib_zephyr_logs_close(stream_key: str) -> str:
    """Close a Zephyr log stream and stop buffering."""
    try:
        await client.logs_close(stream_key)
        return f"Closed {stream_key}"
    except Exception as e:
        return f"Log close error: {e}"


# =========================================================================
# 5. Power & Measurement
# =========================================================================


@mcp.tool()
async def mtib_power_measure(
    channel: str = "MAIN",
    duration_s: float = 1.0,
    sample_rate_hz: int = 1000,
) -> str:
    """Measure power consumption over a duration.

    channel: "MAIN", "VBAT", "3V3", "1V8"
    Returns average, min, max current and total energy.
    """
    chan_map = {
        "MAIN": pb.POWER_MAIN,
        "VBAT": pb.POWER_VBAT,
        "3V3": pb.POWER_3V3,
        "1V8": pb.POWER_1V8,
    }
    ch = chan_map.get(channel.upper())
    if ch is None:
        return f"Unknown channel '{channel}'. Use: {', '.join(chan_map)}"

    try:
        resp = await client.stub.PowerMeasure(
            pb.PowerMeasureRequest(
                channel=ch,
                duration_s=duration_s,
                sample_rate_hz=sample_rate_hz,
            )
        )
        if not resp.success:
            return f"Measurement failed: {resp.message}"
        return json.dumps(
            {
                "duration_s": round(resp.duration_s, 3),
                "average_uA": round(resp.average_ua, 2),
                "min_uA": round(resp.min_ua, 2),
                "max_uA": round(resp.max_ua, 2),
                "energy_uJ": round(resp.energy_uj, 2),
                "samples": resp.sample_count,
            },
            indent=2,
        )
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


@mcp.tool()
async def mtib_power_control(
    action: str,
    channel: str = "MAIN",
    voltage_v: float = 3.3,
    current_limit_ma: float = 500.0,
) -> str:
    """Enable, disable, or query a power channel.

    action: "enable", "disable", or "status"
    channel: "MAIN", "VBAT", "3V3", "1V8"
    voltage_v: supply voltage when enabling (0 = measure-only mode)
    """
    chan_map = {
        "MAIN": pb.POWER_MAIN,
        "VBAT": pb.POWER_VBAT,
        "3V3": pb.POWER_3V3,
        "1V8": pb.POWER_1V8,
    }
    ch = chan_map.get(channel.upper())
    if ch is None:
        return f"Unknown channel '{channel}'. Use: {', '.join(chan_map)}"

    try:
        if action == "enable":
            resp = await client.stub.PowerEnable(
                pb.PowerEnableRequest(
                    config=pb.PowerConfig(
                        channel=ch,
                        voltage_v=voltage_v,
                        current_limit_ma=current_limit_ma,
                    )
                )
            )
            return f"Power enabled: {channel} @ {voltage_v}V" if resp.success else f"Failed: {resp.message}"
        elif action == "disable":
            resp = await client.stub.PowerDisable(
                pb.PowerDisableRequest(channel=ch)
            )
            return f"Power disabled: {channel}" if resp.success else f"Failed: {resp.message}"
        elif action == "status":
            resp = await client.stub.PowerStatus(
                pb.PowerStatusRequest(channel=ch)
            )
            if not resp.success:
                return f"Status failed: {resp.message}"
            return json.dumps(
                {
                    "enabled": resp.enabled,
                    "voltage_V": round(resp.voltage_v, 3),
                    "current_mA": round(resp.current_ma, 3),
                    "power_mW": round(resp.power_mw, 3),
                },
                indent=2,
            )
        else:
            return f"Unknown action '{action}'. Use: enable, disable, status"
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


# =========================================================================
# 6. Testing
# =========================================================================


@mcp.tool()
async def mtib_twister_run(
    target_id: str,
    test_path: str,
    extra_args: str = "",
    timeout_s: float = 300.0,
) -> str:
    """Run a Zephyr Twister test suite on a target.

    test_path: e.g. "tests/kernel/threads/thread_apis"
    extra_args: space-separated additional twister arguments
    """
    args = extra_args.split() if extra_args else []
    try:
        resp = await client.stub.TwisterRun(
            pb.TwisterRunRequest(
                target_id=target_id,
                test_path=test_path,
                extra_args=args,
                timeout_s=timeout_s,
            )
        )
        if not resp.success:
            return f"Twister failed: {resp.message}"

        results = []
        pass_count = fail_count = skip_count = 0
        for r in resp.results:
            status_name = pb.TestResult.Status.Name(r.status)
            results.append(
                {
                    "name": r.name,
                    "status": status_name,
                    "duration_s": round(r.duration_s, 2),
                    "message": r.message,
                }
            )
            if r.status == pb.TestResult.STATUS_PASS:
                pass_count += 1
            elif r.status == pb.TestResult.STATUS_FAIL:
                fail_count += 1
            else:
                skip_count += 1

        summary = f"{pass_count} passed, {fail_count} failed, {skip_count} skipped"
        return json.dumps({"summary": summary, "results": results}, indent=2)
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


# =========================================================================
# 7. Bus I/O
# =========================================================================


@mcp.tool()
async def mtib_i2c_scan(bus: int = 1) -> str:
    """Scan an I2C bus and return detected device addresses."""
    try:
        resp = await client.stub.I2cScan(pb.I2cScanRequest(bus=bus))
        if not resp.success:
            return f"Scan failed: {resp.message}"
        addrs = [f"0x{a:02x}" for a in resp.addresses]
        return json.dumps({"bus": bus, "devices": addrs, "count": len(addrs)}, indent=2)
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


@mcp.tool()
async def mtib_i2c_transfer(
    bus: int,
    address: str,
    write_hex: str = "",
    read_size: int = 0,
) -> str:
    """Read from or write to an I2C device.

    address: 7-bit hex address (e.g. "0x48")
    write_hex: hex bytes to write (e.g. "0100")
    read_size: number of bytes to read back
    """
    try:
        addr = int(address, 0)
    except ValueError:
        return f"Invalid address '{address}'"

    write_data = bytes.fromhex(write_hex) if write_hex else b""
    try:
        resp = await client.stub.I2cTransfer(
            pb.I2cTransferRequest(
                bus=bus,
                address=addr,
                write_data=write_data,
                read_size=read_size,
            )
        )
        if not resp.success:
            return f"Transfer failed: {resp.message}"
        result: dict = {"nak": resp.nak}
        if resp.read_data:
            result["read_hex"] = resp.read_data.hex()
            result["read_bytes"] = list(resp.read_data)
        return json.dumps(result, indent=2)
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


# =========================================================================
# Entry point
# =========================================================================


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
