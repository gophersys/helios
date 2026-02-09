"""Mock MTIB V2 gRPC server for testing the MCP server.

Implements the RPCs used by the 22 MCP tools with realistic mock responses.
Can be started as a subprocess or used in-process via start()/stop().
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
import uuid
from concurrent import futures

import grpc
from grpc import aio as grpc_aio

# Use the bundled proto from the MCP server package (same as what the server imports)
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "src"))
from mtib_mcp.proto import mtib_v2_pb2 as pb
from mtib_mcp.proto import mtib_v2_pb2_grpc as pb_grpc


class MockMtibV2Servicer(pb_grpc.MtibV2Servicer):
    """Returns realistic mock data for all RPCs used by MCP tools."""

    def __init__(self):
        self._sessions: dict[str, str] = {}  # session_id -> target_id
        self._uart_streams: dict[str, str] = {}  # stream_id -> target_id
        self._uploaded_files: dict[str, bytes] = {}

    # ------------------------------------------------------------------
    # Health & System
    # ------------------------------------------------------------------

    async def HealthCheck(self, request, context):
        return pb.HealthCheckResponse(
            ready=True,
            version="2.0.0-mock",
            errors=[],
            capabilities={"debug": "jlink", "power": "ppk2", "uart": "2x"},
        )

    async def SystemInfo(self, request, context):
        return pb.SystemInfoResponse(
            success=True,
            hostname="mock-mtib",
            os="Linux 6.1.0-rpi",
            cpu_usage=15.0,
            memory_usage=42.3,
            disk_usage=28.7,
        )

    # ------------------------------------------------------------------
    # Target Management
    # ------------------------------------------------------------------

    async def ListTargets(self, request, context):
        return pb.ListTargetsResponse(
            success=True,
            targets=[
                pb.TargetDevice(
                    id="nrf52840_dk",
                    name="nRF52840 DK",
                    arch=pb.ARCH_ARM_CORTEX_M4,
                    chip="nRF52840",
                    board="nrf52840dk_nrf52840",
                    has_debug=True,
                    has_uart=True,
                    has_rtt=True,
                    has_swo=False,
                    flash_size_kb=1024,
                    ram_size_kb=256,
                ),
            ],
        )

    async def ListProbes(self, request, context):
        return pb.ListProbesResponse(
            success=True,
            probes=[
                pb.DebugProbe(
                    id="jlink-001",
                    type=pb.PROBE_JLINK,
                    serial="000683456789",
                    firmware_version="V7.94e",
                    supported_targets=["nrf52840_dk"],
                ),
            ],
        )

    # ------------------------------------------------------------------
    # Debug Probe
    # ------------------------------------------------------------------

    async def DebugConnect(self, request, context):
        session_id = f"mock-session-{uuid.uuid4().hex[:8]}"
        self._sessions[session_id] = request.target_id
        state = pb.DEBUG_STATE_HALTED if request.halt_on_connect else pb.DEBUG_STATE_RUNNING
        return pb.DebugConnectResponse(
            success=True,
            session_id=session_id,
            state=state,
        )

    async def DebugDisconnect(self, request, context):
        self._sessions.pop(request.session_id, None)
        return pb.Response(success=True)

    async def DebugStatus(self, request, context):
        return pb.DebugStatusResponse(
            success=True,
            state=pb.DEBUG_STATE_HALTED,
            pc=0x0800_1234,
            halt_reason="breakpoint",
        )

    async def DebugHalt(self, request, context):
        return pb.Response(success=True)

    async def DebugResume(self, request, context):
        return pb.Response(success=True)

    async def DebugStep(self, request, context):
        return pb.Response(success=True)

    async def DebugReset(self, request, context):
        return pb.Response(success=True)

    async def ReadRegisters(self, request, context):
        regs = [
            pb.RegisterValue(name="R0", value=0x0000_0000, size_bits=32),
            pb.RegisterValue(name="R1", value=0x2000_0100, size_bits=32),
            pb.RegisterValue(name="R2", value=0x0000_0042, size_bits=32),
            pb.RegisterValue(name="SP", value=0x2003_FF00, size_bits=32),
            pb.RegisterValue(name="LR", value=0x0800_0FFF, size_bits=32),
            pb.RegisterValue(name="PC", value=0x0800_1234, size_bits=32),
            pb.RegisterValue(name="xPSR", value=0x6100_0000, size_bits=32),
        ]
        return pb.ReadRegistersResponse(success=True, registers=regs)

    async def WriteRegister(self, request, context):
        return pb.Response(success=True)

    async def ReadMemory(self, request, context):
        size = min(request.size, 4096)
        data = bytes(range(256)) * (size // 256 + 1)
        return pb.ReadMemoryResponse(success=True, data=data[:size])

    async def WriteMemory(self, request, context):
        return pb.Response(success=True)

    async def SetBreakpoint(self, request, context):
        return pb.SetBreakpointResponse(success=True, breakpoint_id=1)

    async def ClearBreakpoint(self, request, context):
        return pb.Response(success=True)

    async def SetWatchpoint(self, request, context):
        return pb.SetWatchpointResponse(success=True, watchpoint_id=1)

    async def Backtrace(self, request, context):
        frames = [
            pb.StackFrame(level=0, pc=0x0800_1234, sp=0x2003_FF00, function="main", file="src/main.c", line=42),
            pb.StackFrame(level=1, pc=0x0800_0FFF, sp=0x2003_FF10, function="k_thread_entry", file="kernel/thread.c", line=330),
        ]
        return pb.BacktraceResponse(success=True, frames=frames[:request.max_frames or 20])

    # ------------------------------------------------------------------
    # Flash Programming
    # ------------------------------------------------------------------

    async def FlashInfo(self, request, context):
        return pb.FlashInfoResponse(
            success=True,
            regions=[pb.FlashRegion(start=0x0, size=0x100000, sector_size=4096, writable=True)],
        )

    async def FlashErase(self, request, context):
        return pb.Response(success=True)

    async def FlashWrite(self, request, context):
        return pb.FlashWriteResponse(success=True, bytes_written=len(request.data), time_ms=12)

    async def FlashProgram(self, request, context):
        return pb.FlashProgramResponse(
            success=True,
            bytes_programmed=65536,
            time_ms=1200,
        )

    # ------------------------------------------------------------------
    # UART
    # ------------------------------------------------------------------

    async def UartOpen(self, request, context):
        stream_id = f"uart-{uuid.uuid4().hex[:8]}"
        self._uart_streams[stream_id] = request.target_id
        return pb.UartOpenResponse(success=True, stream_id=stream_id)

    async def UartClose(self, request, context):
        self._uart_streams.pop(request.stream_id, None)
        return pb.Response(success=True)

    async def UartStream(self, request_iterator, context):
        """Bidirectional UART stream: echo back any data, then send periodic mock output."""
        async for req in request_iterator:
            if req.data:
                yield pb.UartStreamResponse(success=True, data=req.data)
            else:
                yield pb.UartStreamResponse(
                    success=True,
                    data=b"[00:00:00.001,234] <inf> app: booted\r\n",
                )
                await asyncio.sleep(0.5)
                yield pb.UartStreamResponse(
                    success=True,
                    data=b"[00:00:01.000,000] <inf> app: running\r\n",
                )

    # ------------------------------------------------------------------
    # Power
    # ------------------------------------------------------------------

    async def PowerEnable(self, request, context):
        return pb.Response(success=True)

    async def PowerDisable(self, request, context):
        return pb.Response(success=True)

    async def PowerStatus(self, request, context):
        return pb.PowerStatusResponse(
            success=True,
            enabled=True,
            voltage_v=3.3,
            current_ma=10.0,
            power_mw=33.0,
        )

    async def PowerMeasure(self, request, context):
        return pb.PowerMeasureResponse(
            success=True,
            duration_s=request.duration_s,
            average_ua=1250.5,
            min_ua=980.0,
            max_ua=3200.0,
            energy_uj=4125.3,
            sample_count=request.sample_rate_hz,
        )

    async def PowerStream(self, request, context):
        for i in range(5):
            yield pb.PowerStreamResponse(
                success=True,
                samples=[pb.PowerSample(current_ua=1200.0 + i * 10, voltage_mv=3300.0)],
            )
            await asyncio.sleep(0.01)

    # ------------------------------------------------------------------
    # I2C
    # ------------------------------------------------------------------

    async def I2cConfigure(self, request, context):
        return pb.Response(success=True)

    async def I2cScan(self, request, context):
        return pb.I2cScanResponse(
            success=True,
            addresses=[0x19, 0x2F, 0x40, 0x41, 0x48, 0x49],
        )

    async def I2cTransfer(self, request, context):
        read_data = bytes(request.read_size) if request.read_size else b""
        return pb.I2cTransferResponse(success=True, read_data=read_data, nak=False)

    # ------------------------------------------------------------------
    # GPIO
    # ------------------------------------------------------------------

    async def GpioConfig(self, request, context):
        return pb.Response(success=True)

    async def GpioWrite(self, request, context):
        return pb.Response(success=True)

    async def GpioRead(self, request, context):
        return pb.GpioReadResponse(success=True, value=False)

    async def GpioWatch(self, request, context):
        yield pb.GpioEventResponse(pin=request.pin, value=True)
        await asyncio.sleep(0.1)
        yield pb.GpioEventResponse(pin=request.pin, value=False)

    # ------------------------------------------------------------------
    # Zephyr
    # ------------------------------------------------------------------

    async def ZephyrShell(self, request, context):
        return pb.ZephyrShellResponse(
            success=True,
            output=f"mocked shell output for: {request.command}",
            return_code=0,
        )

    async def ZephyrLogStream(self, request, context):
        yield pb.ZephyrLogStreamResponse(
            entries=[
                pb.ZephyrLogEntry(level=pb.LOG_LEVEL_INF, module="app", message="System initialized"),
                pb.ZephyrLogEntry(level=pb.LOG_LEVEL_DBG, module="drv", message="Sensor ready"),
            ]
        )

    async def ZephyrDevicetree(self, request, context):
        return pb.ZephyrDevicetreeResponse(
            success=True,
            root=pb.ZephyrDevicetreeNode(
                path="/",
                compatible="nordic,nrf52840-dk",
                children=[
                    pb.ZephyrDevicetreeNode(path="/soc/i2c@40003000", compatible="nordic,nrf-twi", label="i2c0"),
                ],
            ),
        )

    async def ZephyrThreads(self, request, context):
        return pb.ZephyrThreadsResponse(
            success=True,
            threads=[
                pb.ZephyrThread(id=1, name="main", state=pb.ZephyrThread.STATE_RUNNING, priority=0, stack_size=4096, stack_used=1024),
                pb.ZephyrThread(id=2, name="idle", state=pb.ZephyrThread.STATE_READY, priority=15, stack_size=512, stack_used=128),
            ],
        )

    # ------------------------------------------------------------------
    # Testing
    # ------------------------------------------------------------------

    async def TwisterRun(self, request, context):
        return pb.TwisterRunResponse(
            success=True,
            results=[
                pb.TestResult(name="test_thread_create", status=pb.TestResult.STATUS_PASS, duration_s=1.2),
                pb.TestResult(name="test_thread_join", status=pb.TestResult.STATUS_PASS, duration_s=0.8),
                pb.TestResult(name="test_thread_priority", status=pb.TestResult.STATUS_SKIP, duration_s=0.0, message="Skipped: requires FPU"),
            ],
        )

    # ------------------------------------------------------------------
    # File Management
    # ------------------------------------------------------------------

    async def ListFiles(self, request, context):
        return pb.ListFilesResponse(
            success=True,
            files=[
                pb.FileInfo(name="firmware.hex", size=131072, sha256="abcdef1234567890" * 4),
                pb.FileInfo(name="config.bin", size=4096, sha256="0123456789abcdef" * 4),
            ],
        )

    async def UploadFile(self, request_iterator, context):
        data = bytearray()
        filename = ""
        async for req in request_iterator:
            filename = req.filename or filename
            data.extend(req.chunk)
        sha = hashlib.sha256(data).hexdigest()
        self._uploaded_files[filename] = bytes(data)
        return pb.UploadFileResponse(success=True, sha256=sha)

    async def DownloadFile(self, request, context):
        data = self._uploaded_files.get(request.filename, b"mock file content")
        yield pb.DownloadFileResponse(success=True, data=data, eof=True)

    async def DeleteFile(self, request, context):
        self._uploaded_files.pop(request.filename, None)
        return pb.Response(success=True)

    # ------------------------------------------------------------------
    # Stubs for remaining RPCs (not used by MCP tools)
    # ------------------------------------------------------------------

    async def RttStart(self, request, context):
        return pb.RttStartResponse(success=True, num_up_channels=2, num_down_channels=1)

    async def RttStop(self, request, context):
        return pb.Response(success=True)

    async def RttStream(self, request_iterator, context):
        async for req in request_iterator:
            yield pb.RttStreamResponse(success=True, channel=req.channel, data=req.data or b"")

    async def SwoStart(self, request, context):
        return pb.Response(success=True)

    async def SwoStop(self, request, context):
        return pb.Response(success=True)

    async def SwoStream(self, request, context):
        yield pb.SwoStreamResponse(port=0, data=b"mock swo data")

    async def SpiConfigure(self, request, context):
        return pb.Response(success=True)

    async def SpiTransfer(self, request, context):
        return pb.SpiTransferResponse(success=True, rx_data=bytes(request.rx_size))

    async def CanConfigure(self, request, context):
        return pb.Response(success=True)

    async def CanSend(self, request, context):
        return pb.Response(success=True)

    async def CanSetFilter(self, request, context):
        return pb.Response(success=True)

    async def CanReceive(self, request, context):
        yield pb.CanReceiveResponse(success=True, frame=pb.CanFrame(id=0x100, data=b"\x01\x02"))

    async def BleScan(self, request, context):
        return pb.BleScanResponse(success=True, devices=[])

    async def BleConnect(self, request, context):
        return pb.BleConnectResponse(success=True, connection_id="ble-mock-1")

    async def BleDisconnect(self, request, context):
        return pb.Response(success=True)

    async def BleDiscoverServices(self, request, context):
        return pb.BleDiscoverServicesResponse(success=True, services=[])

    async def BleRead(self, request, context):
        return pb.BleReadResponse(success=True, data=b"\x00")

    async def BleWrite(self, request, context):
        return pb.Response(success=True)

    async def BleNotifications(self, request, context):
        yield pb.BleNotificationResponse(connection_id="ble-mock-1", handle=1, data=b"\x01")

    async def LogicCaptureStart(self, request, context):
        return pb.LogicCaptureStartResponse(success=True, capture_id="cap-mock-1")

    async def LogicCaptureStatus(self, request, context):
        return pb.LogicCaptureStatusResponse(success=True, status=pb.LogicCaptureStatusResponse.STATUS_COMPLETE, progress=1.0)

    async def LogicCaptureStop(self, request, context):
        return pb.Response(success=True)

    async def AddDecoder(self, request, context):
        return pb.AddDecoderResponse(success=True, decoder_id="dec-mock-1")

    async def GetDecodedData(self, request, context):
        return pb.GetDecodedDataResponse(success=True, data=[])


# ======================================================================
# Server lifecycle
# ======================================================================


async def start_server(port: int = 0) -> tuple[grpc_aio.Server, int]:
    """Start the mock server on the given port (0 = random).

    Returns (server, actual_port).
    """
    server = grpc_aio.server(futures.ThreadPoolExecutor(max_workers=4))
    pb_grpc.add_MtibV2Servicer_to_server(MockMtibV2Servicer(), server)
    actual_port = server.add_insecure_port(f"[::]:{port}")
    await server.start()
    return server, actual_port


async def _run_standalone(port: int) -> None:
    server, actual_port = await start_server(port)
    print(f"Mock MTIB server listening on port {actual_port}")
    await server.wait_for_termination()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 50054
    asyncio.run(_run_standalone(port))
