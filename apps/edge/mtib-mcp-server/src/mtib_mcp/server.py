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
# 8. Logic Analyzer
# =========================================================================


@mcp.tool()
async def mtib_analyzer_list_providers() -> str:
    """List available logic analyzer backends (Saleae, sigrok, simulation).

    Returns information about each provider: availability, max sample rate,
    channel count, supported protocols, and detected hardware.
    """
    try:
        resp = await client.stub.ListAnalyzerProviders(
            pb.ListAnalyzerProvidersRequest()
        )
        if not resp.success:
            return f"Failed to list providers: {resp.message}"

        providers = []
        for p in resp.providers:
            providers.append(
                {
                    "name": p.name,
                    "display_name": p.display_name,
                    "available": p.available,
                    "max_sample_rate_hz": p.max_sample_rate_hz,
                    "max_channels": p.max_channels,
                    "supported_protocols": list(p.supported_protocols),
                    "supports_streaming": p.supports_streaming,
                    "supports_triggers": p.supports_triggers,
                    "hardware_detected": p.hardware_detected or "none",
                    "supported_export_formats": list(p.supported_export_formats),
                }
            )
        return json.dumps({"providers": providers}, indent=2)
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


@mcp.tool()
async def mtib_analyzer_capture_start(
    channels: str,
    sample_rate_hz: int = 1_000_000,
    duration_s: float = 1.0,
    provider: str = "auto",
    trigger_enabled: bool = False,
    trigger_channel: int = 0,
    trigger_edge: str = "rising",
    pre_trigger_s: float = 0.0,
    timeout_s: float = 60.0,
    max_samples: int = 0,
    max_memory_mb: int = 512,
) -> str:
    """Start a logic analyzer capture.

    channels: comma-separated channel definitions like "0:SCL,1:SDA,2:CS"
    sample_rate_hz: sampling rate (up to 500MHz for some hardware)
    duration_s: capture duration in seconds
    provider: "auto", "saleae", "sigrok", or "simulation"
    trigger_enabled: wait for trigger before capturing
    trigger_channel: channel index to trigger on
    trigger_edge: "rising", "falling", or "either"
    pre_trigger_s: seconds of data to capture before trigger
    timeout_s: overall operation timeout (default 60s)
    max_samples: hard limit on total samples (0 = unlimited)
    max_memory_mb: memory limit (default 512 MB)

    Returns a capture_id for use with other analyzer tools.
    """
    # Parse channels
    channel_configs = []
    for ch_spec in channels.split(","):
        ch_spec = ch_spec.strip()
        if ":" in ch_spec:
            ch_num, label = ch_spec.split(":", 1)
            channel_configs.append(
                pb.AnalyzerChannelConfig(
                    channel=int(ch_num.strip()),
                    label=label.strip(),
                    enabled=True,
                )
            )
        else:
            channel_configs.append(
                pb.AnalyzerChannelConfig(
                    channel=int(ch_spec),
                    label=f"CH{ch_spec}",
                    enabled=True,
                )
            )

    # Parse provider
    provider_map = {
        "auto": pb.PROVIDER_AUTO,
        "saleae": pb.PROVIDER_SALEAE,
        "sigrok": pb.PROVIDER_SIGROK,
        "simulation": pb.PROVIDER_SIMULATION,
    }
    prov = provider_map.get(provider.lower())
    if prov is None:
        return f"Invalid provider '{provider}'. Use: {', '.join(provider_map)}"

    # Parse trigger edge
    edge_map = {
        "rising": pb.AnalyzerCaptureConfig.TRIGGER_RISING,
        "falling": pb.AnalyzerCaptureConfig.TRIGGER_FALLING,
        "either": pb.AnalyzerCaptureConfig.TRIGGER_EITHER,
    }
    edge = edge_map.get(trigger_edge.lower())
    if edge is None:
        return f"Invalid trigger_edge '{trigger_edge}'. Use: {', '.join(edge_map)}"

    try:
        resp = await client.stub.AnalyzerCaptureStart(
            pb.AnalyzerCaptureStartRequest(
                config=pb.AnalyzerCaptureConfig(
                    channels=channel_configs,
                    sample_rate_hz=sample_rate_hz,
                    duration_s=duration_s,
                    trigger_enabled=trigger_enabled,
                    trigger_channel=trigger_channel,
                    trigger_edge=edge,
                    pre_trigger_s=pre_trigger_s,
                    timeout_s=timeout_s,
                    max_samples=max_samples,
                    max_memory_mb=max_memory_mb,
                ),
                prefer_provider=prov,
            )
        )
        if not resp.success:
            return f"Capture start failed: {resp.message}"
        return json.dumps(
            {
                "capture_id": resp.capture_id,
                "provider_used": resp.provider_used,
                "status": "started",
            },
            indent=2,
        )
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


@mcp.tool()
async def mtib_analyzer_capture_status(capture_id: str) -> str:
    """Get the status of a running or completed capture.

    Returns: status (waiting_trigger/capturing/complete/error), progress,
    samples captured, samples dropped, and memory usage.
    """
    try:
        resp = await client.stub.AnalyzerCaptureStatus(
            pb.AnalyzerCaptureStatusRequest(capture_id=capture_id)
        )
        if not resp.success:
            return f"Status query failed: {resp.message}"

        status_name = pb.AnalyzerCaptureStatusResponse.Status.Name(resp.status)
        return json.dumps(
            {
                "capture_id": capture_id,
                "status": status_name.replace("STATUS_", "").lower(),
                "progress": round(resp.progress, 3),
                "samples_captured": resp.samples_captured,
                "samples_dropped": resp.samples_dropped,
                "memory_usage_mb": round(resp.memory_usage_mb, 2),
            },
            indent=2,
        )
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


@mcp.tool()
async def mtib_analyzer_stream_samples(
    capture_id: str,
    max_samples: int = 1000,
    interval_s: float = 0.1,
) -> str:
    """Stream recent samples from an active or completed capture.

    This is a one-shot read, not a persistent stream. Call repeatedly
    to poll for new samples during capture.

    max_samples: limit samples per call (default 1000)
    interval_s: internal polling interval for the stream (default 0.1s)

    Returns samples as timestamp + digital values per channel.
    """
    try:
        # The RPC is a server-streaming call, but we'll just consume the
        # first chunk and return it (one-shot read for MCP simplicity)
        stream = client.stub.AnalyzerStream(
            pb.AnalyzerStreamRequest(
                capture_id=capture_id,
                max_samples_per_chunk=max_samples,
                interval_s=interval_s,
            )
        )

        # Read first response
        resp = await stream.read()
        if resp == grpc.aio.EOF:
            return json.dumps({"samples": [], "capture_complete": True})

        if not resp.success:
            return f"Stream failed: {resp.message}"

        samples = []
        for s in resp.samples:
            samples.append(
                {
                    "timestamp_ns": s.timestamp_ns,
                    "digital_values": list(s.digital_values),
                }
            )

        # Cancel the stream after first read
        stream.cancel()

        return json.dumps(
            {
                "samples": samples,
                "count": len(samples),
                "capture_complete": resp.capture_complete,
                "total_samples": resp.total_samples,
                "samples_dropped": resp.samples_dropped,
            },
            indent=2,
        )
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


@mcp.tool()
async def mtib_analyzer_export(
    capture_id: str,
    format: str = "csv",
    output_path: str = "",
) -> str:
    """Export a capture to a file.

    format: "csv", "vcd", "native_saleae", or "native_sigrok"
    output_path: relative path (empty = auto-generate)

    Returns the full path to the exported file.
    """
    format_map = {
        "csv": pb.AnalyzerExportRequest.FORMAT_CSV,
        "vcd": pb.AnalyzerExportRequest.FORMAT_VCD,
        "native_saleae": pb.AnalyzerExportRequest.FORMAT_NATIVE_SALEAE,
        "native_sigrok": pb.AnalyzerExportRequest.FORMAT_NATIVE_SIGROK,
    }
    fmt = format_map.get(format.lower())
    if fmt is None:
        return f"Invalid format '{format}'. Use: {', '.join(format_map)}"

    try:
        resp = await client.stub.AnalyzerExport(
            pb.AnalyzerExportRequest(
                capture_id=capture_id,
                format=fmt,
                output_path=output_path,
            )
        )
        if not resp.success:
            return f"Export failed: {resp.message}"
        return json.dumps(
            {
                "file_path": resp.file_path,
                "file_size_bytes": resp.file_size_bytes,
                "file_size_mb": round(resp.file_size_bytes / (1024 * 1024), 2),
            },
            indent=2,
        )
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


@mcp.tool()
async def mtib_analyzer_add_decoder(
    capture_id: str,
    protocol: str,
    decoder_name: str = "",
    config: str = "",
) -> str:
    """Add a protocol decoder to a capture.

    protocol: "i2c", "spi", "uart", "can", "jtag", "swd", "1wire", "lin", "i2s", "pwm"
    decoder_name: optional name (auto-generated if empty)
    config: JSON config like '{"sda_channel": 0, "scl_channel": 1}' for I2C,
            '{"rx_channel": 0, "tx_channel": 1, "baud": 115200}' for UART, etc.

    Returns a decoder_id for use with mtib_analyzer_get_decoded_data.

    I2C config keys: sda_channel, scl_channel
    SPI config keys: clk_channel, mosi_channel, miso_channel, cs_channel, cpol, cpha, bits_per_word, msb_first
    UART config keys: rx_channel, tx_channel, baud, data_bits, parity ("none"/"even"/"odd")
    """
    protocol_map = {
        "i2c": pb.PROTOCOL_I2C,
        "spi": pb.PROTOCOL_SPI,
        "uart": pb.PROTOCOL_UART,
        "1wire": pb.PROTOCOL_1WIRE,
        "jtag": pb.PROTOCOL_JTAG,
        "swd": pb.PROTOCOL_SWD,
        "can": pb.PROTOCOL_CAN,
        "lin": pb.PROTOCOL_LIN,
        "i2s": pb.PROTOCOL_I2S,
        "pwm": pb.PROTOCOL_PWM,
    }
    proto = protocol_map.get(protocol.lower())
    if proto is None:
        return f"Invalid protocol '{protocol}'. Use: {', '.join(protocol_map)}"

    # Parse config JSON
    cfg = {}
    if config:
        try:
            cfg = json.loads(config)
        except json.JSONDecodeError as e:
            return f"Invalid JSON config: {e}"

    # Build the decoder request
    req = pb.AddDecoderRequest(
        capture_id=capture_id,
        decoder_name=decoder_name or f"{protocol}_decoder",
        protocol=proto,
    )

    # Set protocol-specific config
    if proto == pb.PROTOCOL_I2C:
        req.i2c.CopyFrom(
            pb.I2cDecoderConfig(
                sda_channel=cfg.get("sda_channel", 0),
                scl_channel=cfg.get("scl_channel", 1),
            )
        )
    elif proto == pb.PROTOCOL_SPI:
        req.spi.CopyFrom(
            pb.SpiDecoderConfig(
                clk_channel=cfg.get("clk_channel", 0),
                mosi_channel=cfg.get("mosi_channel", 1),
                miso_channel=cfg.get("miso_channel", 2),
                cs_channel=cfg.get("cs_channel", 3),
                cpol=cfg.get("cpol", False),
                cpha=cfg.get("cpha", False),
                bits_per_word=cfg.get("bits_per_word", 8),
                msb_first=cfg.get("msb_first", True),
            )
        )
    elif proto == pb.PROTOCOL_UART:
        parity_map = {"none": pb.PARITY_NONE, "even": pb.PARITY_EVEN, "odd": pb.PARITY_ODD}
        parity_str = cfg.get("parity", "none").lower()
        parity = parity_map.get(parity_str, pb.PARITY_NONE)
        req.uart.CopyFrom(
            pb.UartDecoderConfig(
                rx_channel=cfg.get("rx_channel", 0),
                tx_channel=cfg.get("tx_channel", 1),
                baud=cfg.get("baud", 115200),
                data_bits=cfg.get("data_bits", 8),
                parity=parity,
            )
        )

    try:
        resp = await client.stub.AddDecoder(req)
        if not resp.success:
            return f"Add decoder failed: {resp.message}"
        return json.dumps(
            {
                "decoder_id": resp.decoder_id,
                "protocol": protocol,
            },
            indent=2,
        )
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


@mcp.tool()
async def mtib_analyzer_get_decoded_data(
    capture_id: str,
    decoder_id: str = "",
) -> str:
    """Get decoded protocol data from a capture.

    decoder_id: specific decoder to query (empty = all decoders)

    Returns decoded transactions (I2C addresses/data, SPI transfers, UART frames, etc.)
    """
    try:
        resp = await client.stub.GetDecodedData(
            pb.GetDecodedDataRequest(
                capture_id=capture_id,
                decoder_id=decoder_id,
            )
        )
        if not resp.success:
            return f"Get decoded data failed: {resp.message}"

        decoded = []
        for entry in resp.data:
            item = {"decoder_id": entry.decoder_id}
            if entry.HasField("i2c"):
                item["protocol"] = "i2c"
                item["data"] = {
                    "timestamp_ns": entry.i2c.timestamp.nanos,
                    "address": f"0x{entry.i2c.address:02x}",
                    "read": entry.i2c.read,
                    "data_hex": entry.i2c.data.hex(),
                    "ack": entry.i2c.ack,
                }
            elif entry.HasField("spi"):
                item["protocol"] = "spi"
                item["data"] = {
                    "timestamp_ns": entry.spi.timestamp.nanos,
                    "mosi_hex": entry.spi.mosi_data.hex(),
                    "miso_hex": entry.spi.miso_data.hex(),
                }
            elif entry.HasField("uart"):
                item["protocol"] = "uart"
                item["data"] = {
                    "timestamp_ns": entry.uart.timestamp.nanos,
                    "is_tx": entry.uart.is_tx,
                    "data_hex": entry.uart.data.hex(),
                    "data_ascii": entry.uart.data.decode("ascii", errors="replace"),
                    "parity_error": entry.uart.parity_error,
                    "framing_error": entry.uart.framing_error,
                }
            elif entry.HasField("can"):
                item["protocol"] = "can"
                item["data"] = {
                    "timestamp_ns": entry.can.timestamp.nanos,
                    "id": f"0x{entry.can.id:03x}",
                    "extended_id": entry.can.extended_id,
                    "rtr": entry.can.rtr,
                    "data_hex": entry.can.data.hex(),
                }
            decoded.append(item)

        return json.dumps(
            {
                "capture_id": capture_id,
                "decoder_id": decoder_id or "all",
                "count": len(decoded),
                "decoded": decoded,
            },
            indent=2,
        )
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


@mcp.tool()
async def mtib_analyzer_stop(capture_id: str) -> str:
    """Stop an active capture early (before duration expires or trigger).

    The capture will be available for export/decoding after stopping.
    """
    try:
        resp = await client.stub.AnalyzerCaptureStop(
            pb.AnalyzerCaptureStopRequest(capture_id=capture_id)
        )
        return "Capture stopped" if resp.success else f"Stop failed: {resp.message}"
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


@mcp.tool()
async def mtib_analyzer_cleanup(capture_id: str = "") -> str:
    """Clean up analyzer resources (memory, files) for inactive captures.

    capture_id: specific capture to clean (empty = clean all inactive)

    Returns list of cleaned captures and memory freed.
    """
    try:
        resp = await client.stub.AnalyzerCleanup(
            pb.AnalyzerCleanupRequest(capture_id=capture_id)
        )
        if not resp.success:
            return f"Cleanup failed: {resp.message}"
        return json.dumps(
            {
                "cleaned_capture_ids": list(resp.cleaned_capture_ids),
                "memory_freed_mb": round(resp.memory_freed_mb, 2),
            },
            indent=2,
        )
    except grpc.aio.AioRpcError as e:
        return _grpc_error(e)


# =========================================================================
# Entry point
# =========================================================================


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
