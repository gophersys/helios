#!/usr/bin/env python3
"""
MTIB V2 Real-Time Stream Monitor

Connects to the MTIB Server V2 gRPC endpoint and monitors:
  1. UART output from the device under test (DUT)
  2. Zephyr log messages (parsed kernel/application logs)

Usage:
    # Monitor UART on default target (uart0 at 115200 baud)
    python stream_monitor.py --host 127.0.0.1 --port 50052

    # Monitor a specific target with custom baud rate
    python stream_monitor.py --host 127.0.0.1 --port 50052 --target nrf52840_dk --baud 115200

    # Monitor Zephyr logs only
    python stream_monitor.py --host 127.0.0.1 --port 50052 --mode logs

    # Monitor both UART and Zephyr logs
    python stream_monitor.py --host 127.0.0.1 --port 50052 --mode all

    # Limit monitoring duration (default: unlimited)
    python stream_monitor.py --host 127.0.0.1 --port 50052 --duration 300

Environment variables (override CLI args):
    SERVER_HOST  - Server address (default: 127.0.0.1)
    SERVER_PORT  - Server port (default: 50052)
"""

import argparse
import os
import signal
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from typing import Iterator, Optional

# ---------------------------------------------------------------------------
# Path setup -- ensure we can import from the monorepo libs
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
for _p in [
    os.path.join(_REPO_ROOT, "libs"),
    os.path.join(_REPO_ROOT, "libs", "python"),
]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import grpc
from protocols.mtib_v2.mtib_v2_pb2 import (
    Empty,
    HealthCheckRequest,
    UartConfig,
    UartOpenRequest,
    UartStreamRequest,
    UartStreamResponse,
    ZephyrLogStreamRequest,
)
from protocols.mtib_v2.mtib_v2_pb2_grpc import MtibV2Stub


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# ANSI color codes for terminal output
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"


LOG_LEVEL_NAMES = {0: "ERR", 1: "WRN", 2: "INF", 3: "DBG"}
LOG_LEVEL_COLORS = {
    0: Colors.RED,
    1: Colors.YELLOW,
    2: Colors.GREEN,
    3: Colors.DIM,
}

# Global flag for graceful shutdown
_running = True


def _timestamp() -> str:
    """Return a formatted timestamp string for the current time."""
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _signal_handler(signum, frame):
    """Handle interrupt signals for graceful shutdown."""
    global _running
    _running = False
    print(f"\n{Colors.YELLOW}[{_timestamp()}] Received signal {signum}, shutting down...{Colors.RESET}")


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

def check_health(stub: MtibV2Stub) -> bool:
    """Perform a health check and print server status."""
    try:
        resp = stub.HealthCheck(HealthCheckRequest(), timeout=5)
        print(f"{Colors.GREEN}[{_timestamp()}] [HEALTH] Server ready: {resp.ready}, version: {resp.version}{Colors.RESET}")
        if resp.errors:
            for err in resp.errors:
                print(f"{Colors.RED}[{_timestamp()}] [HEALTH] Error: {err}{Colors.RESET}")
        if resp.capabilities:
            caps = ", ".join(f"{k}={v}" for k, v in resp.capabilities.items())
            print(f"{Colors.CYAN}[{_timestamp()}] [HEALTH] Capabilities: {caps}{Colors.RESET}")
        return resp.ready
    except grpc.RpcError as e:
        print(f"{Colors.RED}[{_timestamp()}] [HEALTH] Health check failed: {e.code()} - {e.details()}{Colors.RESET}")
        return False
    except Exception as e:
        print(f"{Colors.RED}[{_timestamp()}] [HEALTH] Health check failed: {e}{Colors.RESET}")
        return False


# ---------------------------------------------------------------------------
# List Targets
# ---------------------------------------------------------------------------

def list_targets(stub: MtibV2Stub) -> list:
    """List available targets and return the list."""
    try:
        resp = stub.ListTargets(Empty(), timeout=5)
        if resp.targets:
            print(f"{Colors.CYAN}[{_timestamp()}] [TARGETS] Available targets:{Colors.RESET}")
            for t in resp.targets:
                print(f"  {Colors.BOLD}{t.id}{Colors.RESET} - {t.name} ({t.chip}, board={t.board})"
                      f" uart={t.has_uart} debug={t.has_debug} rtt={t.has_rtt}")
        else:
            print(f"{Colors.YELLOW}[{_timestamp()}] [TARGETS] No targets reported by server{Colors.RESET}")
        return list(resp.targets)
    except grpc.RpcError as e:
        print(f"{Colors.YELLOW}[{_timestamp()}] [TARGETS] Could not list targets: {e.code()} - {e.details()}{Colors.RESET}")
        return []
    except Exception as e:
        print(f"{Colors.YELLOW}[{_timestamp()}] [TARGETS] Could not list targets: {e}{Colors.RESET}")
        return []


# ---------------------------------------------------------------------------
# UART Monitor
# ---------------------------------------------------------------------------

def monitor_uart(
    stub: MtibV2Stub,
    target_id: str,
    port_name: str = "uart0",
    baud: int = 115200,
    duration: Optional[float] = None,
):
    """
    Open a UART stream and print all received data with timestamps.

    This uses the V2 protocol flow:
      1. UartOpen  -> get stream_id
      2. UartStream (bidirectional) -> send empty requests, receive data
      3. UartClose when done
    """
    global _running
    stream_id = None

    # --- Step 1: Open UART ---
    print(f"{Colors.CYAN}[{_timestamp()}] [UART] Opening UART: target={target_id} port={port_name} baud={baud}{Colors.RESET}")
    try:
        config = UartConfig(baud=baud, data_bits=8, parity=0, stop_bits=0, flow_control=0)
        open_resp = stub.UartOpen(
            UartOpenRequest(target_id=target_id, port_name=port_name, config=config),
            timeout=10,
        )
        if not open_resp.success:
            print(f"{Colors.RED}[{_timestamp()}] [UART] Failed to open: {open_resp.message}{Colors.RESET}")
            return
        stream_id = open_resp.stream_id
        print(f"{Colors.GREEN}[{_timestamp()}] [UART] Opened successfully, stream_id={stream_id}{Colors.RESET}")
    except grpc.RpcError as e:
        print(f"{Colors.RED}[{_timestamp()}] [UART] gRPC error opening UART: {e.code()} - {e.details()}{Colors.RESET}")
        return
    except Exception as e:
        print(f"{Colors.RED}[{_timestamp()}] [UART] Error opening UART: {e}{Colors.RESET}")
        return

    # --- Step 2: Stream data ---
    start_time = time.monotonic()
    bytes_received = 0
    line_buffer = ""

    def request_iterator() -> Iterator[UartStreamRequest]:
        """Generate keep-alive requests for the bidirectional stream."""
        while _running:
            if duration and (time.monotonic() - start_time) >= duration:
                break
            yield UartStreamRequest(stream_id=stream_id, data=b"")
            time.sleep(0.05)  # 50ms polling interval

    try:
        print(f"{Colors.CYAN}[{_timestamp()}] [UART] Streaming started. Press Ctrl+C to stop.{Colors.RESET}")
        print(f"{Colors.DIM}{'=' * 80}{Colors.RESET}")

        for response in stub.UartStream(request_iterator()):
            if not _running:
                break
            if duration and (time.monotonic() - start_time) >= duration:
                break

            if not response.success:
                print(f"{Colors.RED}[{_timestamp()}] [UART] Stream error: {response.message}{Colors.RESET}")
                break

            if response.data:
                bytes_received += len(response.data)
                text = response.data.decode("utf-8", errors="replace")

                # Build up lines from the stream and print them with timestamps
                line_buffer += text
                while "\n" in line_buffer:
                    line, line_buffer = line_buffer.split("\n", 1)
                    ts = _timestamp()
                    # Color-code based on content patterns
                    if any(kw in line.lower() for kw in ["error", "fail", "fault", "panic", "assert"]):
                        print(f"{Colors.RED}[{ts}] [UART] {line}{Colors.RESET}")
                    elif any(kw in line.lower() for kw in ["warn", "warning"]):
                        print(f"{Colors.YELLOW}[{ts}] [UART] {line}{Colors.RESET}")
                    elif any(kw in line.lower() for kw in ["pass", "success", "ok", "done"]):
                        print(f"{Colors.GREEN}[{ts}] [UART] {line}{Colors.RESET}")
                    elif line.startswith("uart:") or line.startswith("***"):
                        print(f"{Colors.MAGENTA}[{ts}] [UART] {line}{Colors.RESET}")
                    else:
                        print(f"[{ts}] [UART] {line}")
                    sys.stdout.flush()

        # Flush any remaining partial line
        if line_buffer.strip():
            print(f"[{_timestamp()}] [UART] {line_buffer}")

    except grpc.RpcError as e:
        if _running:
            print(f"{Colors.RED}[{_timestamp()}] [UART] Stream RPC error: {e.code()} - {e.details()}{Colors.RESET}")
    except Exception as e:
        if _running:
            print(f"{Colors.RED}[{_timestamp()}] [UART] Stream error: {e}{Colors.RESET}")
            traceback.print_exc()

    # --- Step 3: Close UART ---
    print(f"{Colors.DIM}{'=' * 80}{Colors.RESET}")
    elapsed = time.monotonic() - start_time
    print(f"{Colors.CYAN}[{_timestamp()}] [UART] Stream ended. Duration: {elapsed:.1f}s, Bytes received: {bytes_received}{Colors.RESET}")

    if stream_id:
        try:
            from protocols.mtib_v2.mtib_v2_pb2 import UartCloseRequest
            stub.UartClose(UartCloseRequest(stream_id=stream_id), timeout=5)
            print(f"{Colors.GREEN}[{_timestamp()}] [UART] Closed stream {stream_id}{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.YELLOW}[{_timestamp()}] [UART] Error closing stream: {e}{Colors.RESET}")


# ---------------------------------------------------------------------------
# Zephyr Log Monitor
# ---------------------------------------------------------------------------

def monitor_zephyr_logs(
    stub: MtibV2Stub,
    session_id: str = "",
    min_level: int = 0,
    modules: list = None,
    duration: Optional[float] = None,
):
    """
    Stream Zephyr kernel/application log messages with timestamps.

    Uses ZephyrLogStream (server-streaming RPC).
    """
    global _running
    start_time = time.monotonic()
    entry_count = 0

    print(f"{Colors.CYAN}[{_timestamp()}] [ZLOG] Starting Zephyr log stream"
          f" (min_level={LOG_LEVEL_NAMES.get(min_level, str(min_level))}"
          f", modules={modules or 'all'}){Colors.RESET}")
    print(f"{Colors.DIM}{'=' * 80}{Colors.RESET}")

    try:
        request = ZephyrLogStreamRequest(
            session_id=session_id,
            min_level=min_level,
            modules=modules or [],
        )
        # Use a long timeout for the stream (or None for indefinite)
        stream_timeout = duration + 10 if duration else 3600
        stream = stub.ZephyrLogStream(request, timeout=stream_timeout)

        for response in stream:
            if not _running:
                break
            if duration and (time.monotonic() - start_time) >= duration:
                break

            for entry in response.entries:
                entry_count += 1
                level_name = LOG_LEVEL_NAMES.get(entry.level, f"L{entry.level}")
                color = LOG_LEVEL_COLORS.get(entry.level, Colors.RESET)

                # Format the log entry timestamp from the protobuf Timestamp
                if entry.timestamp and entry.timestamp.seconds > 0:
                    entry_ts = datetime.fromtimestamp(
                        entry.timestamp.seconds + entry.timestamp.nanos / 1e9,
                        tz=timezone.utc,
                    ).strftime("%H:%M:%S.%f")[:-3]
                else:
                    entry_ts = _timestamp()

                loc = ""
                if entry.file:
                    loc = f" ({entry.file}:{entry.line})"

                print(f"{color}[{_timestamp()}] [ZLOG] [{entry_ts}] <{level_name}>"
                      f" [{entry.module or '?'}] {entry.message}{loc}{Colors.RESET}")
                sys.stdout.flush()

    except grpc.RpcError as e:
        if _running:
            code = e.code()
            if code == grpc.StatusCode.UNIMPLEMENTED:
                print(f"{Colors.YELLOW}[{_timestamp()}] [ZLOG] ZephyrLogStream not implemented on this server{Colors.RESET}")
            elif code == grpc.StatusCode.DEADLINE_EXCEEDED:
                print(f"{Colors.YELLOW}[{_timestamp()}] [ZLOG] Stream timed out after {duration or stream_timeout}s{Colors.RESET}")
            else:
                print(f"{Colors.RED}[{_timestamp()}] [ZLOG] Stream RPC error: {code} - {e.details()}{Colors.RESET}")
    except Exception as e:
        if _running:
            print(f"{Colors.RED}[{_timestamp()}] [ZLOG] Stream error: {e}{Colors.RESET}")
            traceback.print_exc()

    print(f"{Colors.DIM}{'=' * 80}{Colors.RESET}")
    elapsed = time.monotonic() - start_time
    print(f"{Colors.CYAN}[{_timestamp()}] [ZLOG] Log stream ended. Duration: {elapsed:.1f}s, Entries: {entry_count}{Colors.RESET}")


# ---------------------------------------------------------------------------
# Combined Monitor (runs UART + Zephyr logs in parallel threads)
# ---------------------------------------------------------------------------

def monitor_all(
    stub: MtibV2Stub,
    target_id: str,
    port_name: str = "uart0",
    baud: int = 115200,
    session_id: str = "",
    log_level: int = 0,
    duration: Optional[float] = None,
):
    """Run UART and Zephyr log monitors in parallel threads."""
    uart_thread = threading.Thread(
        target=monitor_uart,
        args=(stub, target_id, port_name, baud, duration),
        daemon=True,
        name="uart-monitor",
    )
    log_thread = threading.Thread(
        target=monitor_zephyr_logs,
        args=(stub, session_id, log_level, None, duration),
        daemon=True,
        name="zephyr-log-monitor",
    )

    uart_thread.start()
    log_thread.start()

    # Wait for both threads to finish (or until interrupted)
    try:
        while _running:
            uart_thread.join(timeout=1.0)
            log_thread.join(timeout=1.0)
            if not uart_thread.is_alive() and not log_thread.is_alive():
                break
    except KeyboardInterrupt:
        pass


# ---------------------------------------------------------------------------
# Direct low-level monitor (no UartOpen, just use the stub directly)
# ---------------------------------------------------------------------------

def monitor_uart_direct(
    stub: MtibV2Stub,
    stream_id: str = "default",
    duration: Optional[float] = None,
):
    """
    Directly open a UartStream without a prior UartOpen call.

    Useful when the server auto-creates streams or for quick debugging
    when you already know the stream_id.
    """
    global _running
    start_time = time.monotonic()
    bytes_received = 0
    line_buffer = ""

    def request_iterator() -> Iterator[UartStreamRequest]:
        while _running:
            if duration and (time.monotonic() - start_time) >= duration:
                break
            yield UartStreamRequest(stream_id=stream_id, data=b"")
            time.sleep(0.05)

    try:
        print(f"{Colors.CYAN}[{_timestamp()}] [UART-DIRECT] Streaming on stream_id={stream_id}{Colors.RESET}")
        print(f"{Colors.DIM}{'=' * 80}{Colors.RESET}")

        for response in stub.UartStream(request_iterator()):
            if not _running:
                break
            if duration and (time.monotonic() - start_time) >= duration:
                break

            if response.data:
                bytes_received += len(response.data)
                text = response.data.decode("utf-8", errors="replace")
                line_buffer += text
                while "\n" in line_buffer:
                    line, line_buffer = line_buffer.split("\n", 1)
                    ts = _timestamp()
                    if any(kw in line.lower() for kw in ["error", "fail", "fault", "panic"]):
                        print(f"{Colors.RED}[{ts}] [UART] {line}{Colors.RESET}")
                    elif any(kw in line.lower() for kw in ["warn"]):
                        print(f"{Colors.YELLOW}[{ts}] [UART] {line}{Colors.RESET}")
                    elif any(kw in line.lower() for kw in ["pass", "success", "ok"]):
                        print(f"{Colors.GREEN}[{ts}] [UART] {line}{Colors.RESET}")
                    else:
                        print(f"[{ts}] [UART] {line}")
                    sys.stdout.flush()

        if line_buffer.strip():
            print(f"[{_timestamp()}] [UART] {line_buffer}")

    except grpc.RpcError as e:
        if _running:
            print(f"{Colors.RED}[{_timestamp()}] [UART-DIRECT] RPC error: {e.code()} - {e.details()}{Colors.RESET}")
    except Exception as e:
        if _running:
            print(f"{Colors.RED}[{_timestamp()}] [UART-DIRECT] Error: {e}{Colors.RESET}")
            traceback.print_exc()

    print(f"{Colors.DIM}{'=' * 80}{Colors.RESET}")
    elapsed = time.monotonic() - start_time
    print(f"{Colors.CYAN}[{_timestamp()}] [UART-DIRECT] Done. Duration: {elapsed:.1f}s, Bytes: {bytes_received}{Colors.RESET}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="MTIB V2 Real-Time Stream Monitor -- watch UART output and Zephyr logs during manufacturing tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                   # Connect to localhost:50052, monitor UART
  %(prog)s --host 192.168.1.100 --port 50052 # Remote server
  %(prog)s --mode logs                        # Zephyr logs only
  %(prog)s --mode all                         # Both UART and Zephyr logs
  %(prog)s --target nrf52840_dk --baud 115200 # Specific target and baud rate
  %(prog)s --duration 300                     # Monitor for 5 minutes then stop
        """,
    )
    parser.add_argument("--host", default=None, help="Server address (default: $SERVER_HOST or 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="Server port (default: $SERVER_PORT or 50052)")
    parser.add_argument("--target", default="nrf52840_dk", help="Target device ID (default: nrf52840_dk)")
    parser.add_argument("--uart-port", default="uart0", help="UART port name (default: uart0)")
    parser.add_argument("--baud", type=int, default=115200, help="UART baud rate (default: 115200)")
    parser.add_argument(
        "--mode",
        choices=["uart", "logs", "all"],
        default="uart",
        help="Monitor mode: uart (default), logs (Zephyr logs), all (both in parallel)",
    )
    parser.add_argument("--session-id", default="", help="Debug/UART session ID for Zephyr log streaming")
    parser.add_argument(
        "--log-level",
        type=int,
        default=0,
        choices=[0, 1, 2, 3],
        help="Minimum Zephyr log level: 0=ERR, 1=WRN, 2=INF, 3=DBG (default: 0 = show all)",
    )
    parser.add_argument("--duration", type=float, default=None, help="Duration in seconds (default: unlimited)")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")

    args = parser.parse_args()

    # Resolve host/port from args -> env -> defaults
    host = args.host or os.environ.get("SERVER_HOST", "127.0.0.1")
    port = args.port or int(os.environ.get("SERVER_PORT", "50052"))

    # Disable colors if requested
    if args.no_color:
        for attr in dir(Colors):
            if not attr.startswith("_"):
                setattr(Colors, attr, "")

    # Register signal handlers
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Banner
    print(f"{Colors.BOLD}")
    print("=" * 80)
    print("  MTIB V2 Stream Monitor")
    print(f"  Server:   {host}:{port}")
    print(f"  Mode:     {args.mode}")
    print(f"  Target:   {args.target}")
    print(f"  UART:     {args.uart_port} @ {args.baud} baud")
    if args.duration:
        print(f"  Duration: {args.duration}s")
    else:
        print("  Duration: unlimited (Ctrl+C to stop)")
    print("=" * 80)
    print(f"{Colors.RESET}")

    # Connect to gRPC server
    addr = f"{host}:{port}"
    print(f"[{_timestamp()}] Connecting to {addr}...")

    try:
        channel = grpc.insecure_channel(
            addr,
            options=[
                ("grpc.keepalive_time_ms", 10000),
                ("grpc.keepalive_timeout_ms", 5000),
                ("grpc.keepalive_permit_without_calls", 1),
                ("grpc.max_receive_message_length", 16 * 1024 * 1024),
            ],
        )
        stub = MtibV2Stub(channel)
    except Exception as e:
        print(f"{Colors.RED}[{_timestamp()}] Failed to create gRPC channel: {e}{Colors.RESET}")
        sys.exit(1)

    # Health check
    if not check_health(stub):
        print(f"{Colors.YELLOW}[{_timestamp()}] Server not ready, attempting to monitor anyway...{Colors.RESET}")

    # List available targets for context
    list_targets(stub)

    print()

    # Run the appropriate monitor
    try:
        if args.mode == "uart":
            monitor_uart(stub, args.target, args.uart_port, args.baud, args.duration)
        elif args.mode == "logs":
            monitor_zephyr_logs(stub, args.session_id, args.log_level, None, args.duration)
        elif args.mode == "all":
            monitor_all(
                stub,
                args.target,
                args.uart_port,
                args.baud,
                args.session_id,
                args.log_level,
                args.duration,
            )
    except KeyboardInterrupt:
        pass
    finally:
        print(f"\n[{_timestamp()}] Closing gRPC channel...")
        try:
            channel.close()
        except Exception:
            pass
        print(f"[{_timestamp()}] Monitor exited.")


if __name__ == "__main__":
    main()
