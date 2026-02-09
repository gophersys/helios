"""Mock MtibV2 gRPC server for testing."""

import grpc
from concurrent import futures

from protocols.mtib_v2 import mtib_v2_pb2 as pb2
from protocols.mtib_v2 import mtib_v2_pb2_grpc as pb2_grpc


class MockMtibV2Servicer(pb2_grpc.MtibV2Servicer):
    """Simple mock server that returns success responses for all RPCs."""

    # Health & System
    def HealthCheck(self, request, context):
        return pb2.HealthCheckResponse(
            ready=True,
            version="2.0.0-mock",
            errors=[],
            capabilities={"debug": "true", "power": "true"},
        )

    def SystemInfo(self, request, context):
        return pb2.SystemInfoResponse(
            success=True,
            message="",
            hostname="mock-mtib",
            os="Linux",
            cpu_usage=12.5,
            memory_usage=45.0,
            disk_usage=30.0,
            uptime=pb2.Timestamp(seconds=3600, nanos=0),
        )

    # Target Management
    def ListTargets(self, request, context):
        return pb2.ListTargetsResponse(
            success=True,
            message="",
            targets=[
                pb2.TargetDevice(
                    id="nrf52840_dk",
                    name="nRF52840 DK",
                    arch=pb2.ARCH_ARM_CORTEX_M4,
                    chip="nRF52840",
                    board="nrf52840dk_nrf52840",
                    has_debug=True,
                    has_uart=True,
                    has_rtt=True,
                    has_swo=False,
                    flash_size_kb=1024,
                    ram_size_kb=256,
                )
            ],
        )

    def ListProbes(self, request, context):
        return pb2.ListProbesResponse(
            success=True,
            message="",
            probes=[
                pb2.DebugProbe(
                    id="jlink-001",
                    type=pb2.PROBE_JLINK,
                    serial="000680012345",
                    firmware_version="V7.80a",
                    supported_targets=["nrf52840_dk"],
                )
            ],
        )

    # Debug Probe
    def DebugConnect(self, request, context):
        return pb2.DebugConnectResponse(
            success=True,
            message="",
            session_id="debug-session-001",
            state=pb2.DEBUG_STATE_HALTED,
        )

    def DebugDisconnect(self, request, context):
        return pb2.Response(success=True, message="")

    def DebugStatus(self, request, context):
        return pb2.DebugStatusResponse(
            success=True,
            message="",
            state=pb2.DEBUG_STATE_HALTED,
            pc=0x08000100,
            halt_reason="breakpoint",
        )

    def DebugHalt(self, request, context):
        return pb2.Response(success=True, message="")

    def DebugResume(self, request, context):
        return pb2.Response(success=True, message="")

    def DebugStep(self, request, context):
        return pb2.Response(success=True, message="")

    def DebugReset(self, request, context):
        return pb2.Response(success=True, message="")

    def ReadRegisters(self, request, context):
        return pb2.ReadRegistersResponse(
            success=True,
            message="",
            registers=[
                pb2.RegisterValue(name="R0", value=0x00000000, size_bits=32),
                pb2.RegisterValue(name="PC", value=0x08000100, size_bits=32),
                pb2.RegisterValue(name="SP", value=0x20008000, size_bits=32),
            ],
        )

    def WriteRegister(self, request, context):
        return pb2.Response(success=True, message="")

    def ReadMemory(self, request, context):
        return pb2.ReadMemoryResponse(
            success=True, message="", data=b"\x00" * request.size
        )

    def WriteMemory(self, request, context):
        return pb2.Response(success=True, message="")

    def SetBreakpoint(self, request, context):
        return pb2.SetBreakpointResponse(
            success=True, message="", breakpoint_id=1
        )

    def ClearBreakpoint(self, request, context):
        return pb2.Response(success=True, message="")

    def SetWatchpoint(self, request, context):
        return pb2.SetWatchpointResponse(
            success=True, message="", watchpoint_id=1
        )

    def Backtrace(self, request, context):
        return pb2.BacktraceResponse(
            success=True,
            message="",
            frames=[
                pb2.StackFrame(
                    level=0,
                    pc=0x08000100,
                    sp=0x20008000,
                    function="main",
                    file="main.c",
                    line=42,
                )
            ],
        )

    # Flash
    def FlashInfo(self, request, context):
        return pb2.FlashInfoResponse(
            success=True,
            message="",
            regions=[
                pb2.FlashRegion(
                    start=0x00000000, size=1048576, sector_size=4096, writable=True
                )
            ],
        )

    def FlashErase(self, request, context):
        return pb2.Response(success=True, message="")

    def FlashWrite(self, request, context):
        return pb2.FlashWriteResponse(
            success=True, message="", bytes_written=len(request.data), time_ms=100
        )

    def FlashProgram(self, request, context):
        return pb2.FlashProgramResponse(
            success=True, message="", bytes_programmed=65536, time_ms=500
        )

    # RTT
    def RttStart(self, request, context):
        return pb2.RttStartResponse(
            success=True, message="", num_up_channels=2, num_down_channels=1
        )

    def RttStop(self, request, context):
        return pb2.Response(success=True, message="")

    # SWO
    def SwoStart(self, request, context):
        return pb2.Response(success=True, message="")

    def SwoStop(self, request, context):
        return pb2.Response(success=True, message="")

    # UART
    def UartOpen(self, request, context):
        return pb2.UartOpenResponse(
            success=True, message="", stream_id="uart-stream-001"
        )

    def UartClose(self, request, context):
        return pb2.Response(success=True, message="")

    # Power
    def PowerEnable(self, request, context):
        return pb2.Response(success=True, message="")

    def PowerDisable(self, request, context):
        return pb2.Response(success=True, message="")

    def PowerStatus(self, request, context):
        return pb2.PowerStatusResponse(
            success=True,
            message="",
            enabled=True,
            voltage_v=3.3,
            current_ma=15.2,
            power_mw=50.16,
        )

    def PowerMeasure(self, request, context):
        return pb2.PowerMeasureResponse(
            success=True,
            message="",
            duration_s=1.0,
            average_ua=15200.0,
            min_ua=12000.0,
            max_ua=18500.0,
            energy_uj=15200.0,
            sample_count=1000,
            samples=[],
        )

    # Logic
    def LogicCaptureStart(self, request, context):
        return pb2.LogicCaptureStartResponse(
            success=True, message="", capture_id="capture-001"
        )

    def LogicCaptureStatus(self, request, context):
        return pb2.LogicCaptureStatusResponse(
            success=True, message="", status=2, progress=1.0
        )

    def LogicCaptureStop(self, request, context):
        return pb2.Response(success=True, message="")

    def AddDecoder(self, request, context):
        return pb2.AddDecoderResponse(
            success=True, message="", decoder_id="decoder-001"
        )

    def GetDecodedData(self, request, context):
        return pb2.GetDecodedDataResponse(success=True, message="", data=[])

    # GPIO
    def GpioConfig(self, request, context):
        return pb2.Response(success=True, message="")

    def GpioWrite(self, request, context):
        return pb2.Response(success=True, message="")

    def GpioRead(self, request, context):
        return pb2.GpioReadResponse(success=True, message="", value=True)

    # I2C
    def I2cConfigure(self, request, context):
        return pb2.Response(success=True, message="")

    def I2cTransfer(self, request, context):
        return pb2.I2cTransferResponse(
            success=True, message="", read_data=b"\xAB\xCD", nak=False
        )

    def I2cScan(self, request, context):
        return pb2.I2cScanResponse(
            success=True, message="", addresses=[0x48, 0x68, 0x76]
        )

    # SPI
    def SpiConfigure(self, request, context):
        return pb2.Response(success=True, message="")

    def SpiTransfer(self, request, context):
        return pb2.SpiTransferResponse(
            success=True, message="", rx_data=b"\xFF\xFE"
        )

    # CAN
    def CanConfigure(self, request, context):
        return pb2.Response(success=True, message="")

    def CanSend(self, request, context):
        return pb2.Response(success=True, message="")

    def CanSetFilter(self, request, context):
        return pb2.Response(success=True, message="")

    # BLE
    def BleScan(self, request, context):
        return pb2.BleScanResponse(
            success=True,
            message="",
            devices=[
                pb2.BleDevice(
                    address="AA:BB:CC:DD:EE:FF",
                    name="Test Device",
                    rssi=-42,
                    advertising_data=b"\x02\x01\x06",
                    connectable=True,
                )
            ],
        )

    def BleConnect(self, request, context):
        return pb2.BleConnectResponse(
            success=True, message="", connection_id="ble-conn-001"
        )

    def BleDisconnect(self, request, context):
        return pb2.Response(success=True, message="")

    def BleDiscoverServices(self, request, context):
        return pb2.BleDiscoverServicesResponse(
            success=True,
            message="",
            services=[
                pb2.BleService(
                    uuid="180f",
                    characteristics=[
                        pb2.BleCharacteristic(uuid="2a19", properties=2, handle=3)
                    ],
                )
            ],
        )

    def BleRead(self, request, context):
        return pb2.BleReadResponse(success=True, message="", data=b"\x64")

    def BleWrite(self, request, context):
        return pb2.Response(success=True, message="")

    # Zephyr
    def ZephyrShell(self, request, context):
        return pb2.ZephyrShellResponse(
            success=True, message="", output="kernel uptime: 12345\n", return_code=0
        )

    def ZephyrDevicetree(self, request, context):
        return pb2.ZephyrDevicetreeResponse(
            success=True,
            message="",
            root=pb2.ZephyrDevicetreeNode(
                path="/",
                compatible="",
                label="",
                status="okay",
                properties={},
                children=[],
            ),
        )

    def ZephyrThreads(self, request, context):
        return pb2.ZephyrThreadsResponse(
            success=True,
            message="",
            threads=[
                pb2.ZephyrThread(
                    id=1,
                    name="main",
                    state=1,
                    priority=0,
                    stack_size=4096,
                    stack_used=1024,
                    cycles=100000,
                )
            ],
        )

    def TwisterRun(self, request, context):
        return pb2.TwisterRunResponse(
            success=True,
            message="",
            results=[
                pb2.TestResult(
                    name="test_thread_create",
                    status=0,
                    duration_s=0.5,
                    message="PASS",
                    log="",
                )
            ],
            full_log="All tests passed.\n",
        )

    # Files
    def ListFiles(self, request, context):
        return pb2.ListFilesResponse(
            success=True,
            message="",
            files=[
                pb2.FileInfo(
                    name="firmware.hex",
                    size=65536,
                    sha256="abcdef1234567890",
                    modified=pb2.Timestamp(seconds=1700000000, nanos=0),
                )
            ],
        )

    def UploadFile(self, request_iterator, context):
        for req in request_iterator:
            pass
        return pb2.UploadFileResponse(
            success=True, message="", sha256="abcdef1234567890"
        )

    def DownloadFile(self, request, context):
        yield pb2.DownloadFileResponse(
            success=True, message="", data=b"file-content-here", eof=True
        )

    def DeleteFile(self, request, context):
        return pb2.Response(success=True, message="")


def create_mock_server(port: int = 0) -> tuple:
    """Create and start a mock gRPC server.

    Args:
        port: Port to bind to. 0 for random available port.

    Returns:
        (server, port) tuple.
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    pb2_grpc.add_MtibV2Servicer_to_server(MockMtibV2Servicer(), server)
    actual_port = server.add_insecure_port(f"127.0.0.1:{port}")
    server.start()
    return server, actual_port
