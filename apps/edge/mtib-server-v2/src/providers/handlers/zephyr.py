"""Zephyr-specific handler for V2 protocol."""

import subprocess
import time
from typing import TYPE_CHECKING, Iterator

from corekinect.utils import Logger
from src.shared.types import (
    Response,
    TestResult,
    TwisterRunRequest,
    TwisterRunResponse,
    ZephyrDevicetreeNode,
    ZephyrDevicetreeRequest,
    ZephyrDevicetreeResponse,
    ZephyrLogEntry,
    ZephyrLogStreamRequest,
    ZephyrLogStreamResponse,
    ZephyrShellRequest,
    ZephyrShellResponse,
    ZephyrThread,
    ZephyrThreadsRequest,
    ZephyrThreadsResponse,
)

if TYPE_CHECKING:
    from src.hardware import HardwareContext


class ZephyrHandler:
    """Handles Zephyr-specific RPCs."""

    def __init__(self, logger: Logger, hardware: "HardwareContext"):
        self.logger = logger
        self.hardware = hardware

    def shell(self, request: ZephyrShellRequest, context) -> ZephyrShellResponse:
        """Execute a Zephyr shell command via UART or RTT."""
        try:
            # TODO: Send command via UART/RTT handler and capture response
            # For now, this is a placeholder that documents the architecture
            session_id = request.session_id
            command = request.command
            timeout = request.timeout_s or 5.0

            self.logger.info(f"Zephyr shell: '{command}' (session={session_id}, timeout={timeout}s)")

            # TODO: Route through UART or RTT based on session type
            return ZephyrShellResponse(
                success=False,
                message="Zephyr shell requires active UART or RTT session (TODO)",
                output="",
                return_code=-1,
            )
        except Exception as e:
            return ZephyrShellResponse(success=False, message=str(e), output="", return_code=-1)

    def log_stream(self, request: ZephyrLogStreamRequest, context) -> Iterator[ZephyrLogStreamResponse]:
        """Server-streaming Zephyr log capture."""
        self.logger.info(f"Zephyr log stream started: session={request.session_id}")
        try:
            # TODO: Parse Zephyr log output from UART/RTT
            while context.is_active():
                # TODO: Read log data from UART/RTT, parse into ZephyrLogEntry
                time.sleep(0.1)
        except Exception as e:
            self.logger.error(f"Zephyr log stream error: {e}")
        finally:
            self.logger.info("Zephyr log stream ended")

    def devicetree(self, request: ZephyrDevicetreeRequest, context) -> ZephyrDevicetreeResponse:
        """Inspect Zephyr devicetree (requires debug connection with ELF)."""
        # TODO: Parse devicetree from ELF file via debug session
        return ZephyrDevicetreeResponse(
            success=False,
            message="Devicetree inspection requires debug session with ELF (TODO)",
        )

    def threads(self, request: ZephyrThreadsRequest, context) -> ZephyrThreadsResponse:
        """Inspect Zephyr thread state."""
        try:
            # TODO: Read thread info via shell command or debug probe
            return ZephyrThreadsResponse(
                success=False,
                message="Thread inspection requires active session (TODO)",
            )
        except Exception as e:
            return ZephyrThreadsResponse(success=False, message=str(e))

    def twister_run(self, request: TwisterRunRequest, context) -> TwisterRunResponse:
        """Execute Zephyr Twister test framework."""
        try:
            cmd = ["west", "twister"]
            if request.target_id:
                cmd.extend(["-p", request.target_id])
            if request.test_path:
                cmd.extend(["-T", request.test_path])
            cmd.extend(list(request.extra_args))

            timeout = request.timeout_s or 300.0

            self.logger.info(f"Running Twister: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            # Parse test results from Twister output
            # TODO: Parse actual Twister XML/JSON output
            results = []
            if result.returncode == 0:
                results.append(TestResult(
                    name=request.test_path or "all",
                    status=0,  # STATUS_PASS
                    duration_s=0.0,
                    message="Passed",
                    log="",
                ))

            return TwisterRunResponse(
                success=result.returncode == 0,
                message="" if result.returncode == 0 else result.stderr,
                results=results,
                full_log=result.stdout + result.stderr,
            )
        except FileNotFoundError:
            return TwisterRunResponse(
                success=False,
                message="west/twister not found in PATH",
                results=[],
                full_log="",
            )
        except subprocess.TimeoutExpired:
            return TwisterRunResponse(
                success=False,
                message=f"Twister timed out after {timeout}s",
                results=[],
                full_log="",
            )
        except Exception as e:
            return TwisterRunResponse(success=False, message=str(e), results=[], full_log="")
