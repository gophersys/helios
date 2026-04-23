"""Legacy UART command infrastructure — standalone functions over MtibV1Client.

These functions implement the old per-command gRPC stream pattern (open stream,
send command, collect response, close stream). For new code, prefer
ShellCommander from shells/base.py which uses persistent streams.

All functions take a ``client`` (MtibV1Client instance) as their first argument.
"""

import queue
import re
import threading
import time
from typing import List, Optional, Tuple

from protocols.mtib.mtib_pb2 import HostType, UartStreamRequest


def send_uart_cmd(
    client,
    target: HostType,
    command: str,
    success_patterns: Optional[List[str]] = None,
    timeout_s: float = 60,
    drain_first: bool = True,
) -> Tuple[Optional[str], Optional[str]]:
    """Helper to send UART command and collect response.

    Args:
        client: MtibV1Client instance.
        target: HostType for UART target processor.
        command: Shell command string to send.
        success_patterns: List of patterns that indicate command completed.
        timeout_s: Timeout in seconds.
        drain_first: Drain UART buffer before sending (prevents bleeding).

    Returns:
        Tuple of (full_response, error).

    The request iterator uses a threading.Event-based stop signal so
    the gRPC stream terminates promptly when the response is complete,
    rather than blocking on the iterator's sleep.
    """
    try:
        # Drain any pending data first to prevent response bleeding
        if drain_first:
            drain_uart(client, target, duration_s=3.0)

        input_queue = queue.Queue()
        stop_requests = threading.Event()

        # Add commands to input queue
        input_queue.put(b"\r")  # Hit ENTER to get prompt
        time.sleep(0.1)
        input_queue.put(f"{command}\r".encode("utf-8"))

        def request_iterator():
            # Send initial target identification request immediately
            """Request iterator."""
            yield UartStreamRequest(target=target, data=b"")
            while not stop_requests.is_set():
                try:
                    data = input_queue.get_nowait()
                    yield UartStreamRequest(target=target, data=data)
                except queue.Empty:
                    # Keep the stream alive with empty requests.
                    # With the push-based server, these just keep the
                    # gRPC stream open; RX data arrives independently.
                    yield UartStreamRequest(target=target, data=b"")
                    # Wait with event so we can stop promptly
                    stop_requests.wait(timeout=0.05)

        response_lines = []
        start_time = time.time()
        command_echoed = False
        success_pattern_time = None

        try:
            for resp in client.UartStream(target, request_iterator()):
                if not resp.success:
                    stop_requests.set()
                    return None, f"UartStream error: {resp.message}"

                if resp.data and len(resp.data) > 0:
                    line = resp.data.decode("utf-8", errors="ignore")
                    response_lines.append(line)

                    full_response = "".join(response_lines)
                    # Strip ANSI escapes for matching — dual-processor
                    # UART interleaving embeds escape codes mid-pattern
                    stripped = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", full_response)

                    # Wait for command echo before treating response as valid
                    echo_to_check = command[:-1] if len(command) > 3 else command
                    if not command_echoed and echo_to_check in stripped:
                        command_echoed = True

                    # Check if any success pattern is present (only after echo)
                    if command_echoed and success_patterns and not success_pattern_time:
                        for pattern in success_patterns:
                            if pattern in stripped:
                                success_pattern_time = time.time()
                                break

                    # Once pattern found, wait for prompt OR additional time
                    if success_pattern_time:
                        elapsed_since_pattern = time.time() - success_pattern_time
                        if "Mfg shell:" in stripped or "Comms Mfg:" in stripped:
                            stop_requests.set()
                            return full_response, None
                        # Give 3 seconds after pattern for prompt to arrive
                        if elapsed_since_pattern > 3.0:
                            stop_requests.set()
                            return full_response, None

                if time.time() - start_time > timeout_s:
                    break
        finally:
            stop_requests.set()

        full_response = "".join(response_lines)
        stripped = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", full_response)
        # Check one more time after collecting all data
        if success_patterns:
            for pattern in success_patterns:
                if pattern in stripped:
                    return full_response, None

        return None, f"Timeout waiting for response. Got: {stripped[:500]}..."

    except Exception as e:
        return None, f"Exception: {str(e)}"


def drain_uart(
    client, target: HostType, duration_s: float = 3.0
) -> None:
    """Drain any pending UART data from the buffer.

    Call this between commands to prevent response bleeding, especially
    when debug output is enabled and flooding the UART.

    Args:
        client: MtibV1Client instance.
        target: HostType for UART target.
        duration_s: How long to drain (default 3s).
    """
    stop = threading.Event()

    def request_iterator():
        # Initial request to set target
        """Request iterator."""
        yield UartStreamRequest(target=target, data=b"")
        while not stop.is_set():
            yield UartStreamRequest(target=target, data=b"")
            stop.wait(timeout=0.05)

    try:
        start = time.time()
        for _ in client.UartStream(target, request_iterator()):
            if time.time() - start >= duration_s:
                stop.set()
                break
    except Exception:
        pass


def lock_shell(
    client, target: HostType, timeout_s: float = 30.0, spam_s: float = 5.0
) -> Tuple[bool, str]:
    """Lock the manufacturing shell on the given target processor.

    Spams lock_shell commands during the boot activation window (~0.4-7.4s
    post-boot), then pumps empty requests to drain buffered responses.
    Must be called right after PowerEnable.

    Args:
        client: MtibV1Client instance.
        target: HOST_TYPE_NRF52840 (app) or HOST_TYPE_NRF9151 (comms).
        timeout_s: Total time to wait for lock confirmation.
        spam_s: How long to actively spam lock_shell (default 5s).

    Returns:
        (success, full_output) — success is True if shell lock confirmed.
    """
    output_lines = []
    stop = threading.Event()

    def request_iterator():
        """Request iterator."""
        start = time.time()
        while time.time() - start < spam_s and not stop.is_set():
            yield UartStreamRequest(target=target, data=b"\rlock_shell\r")
            stop.wait(timeout=0.1)
        while time.time() - start < timeout_s and not stop.is_set():
            yield UartStreamRequest(target=target, data=b"")
            stop.wait(timeout=0.05)

    try:
        for resp in client.UartStream(target, request_iterator()):
            if resp.data:
                text = resp.data.decode("utf-8", errors="ignore")
                output_lines.append(text)
                if "mode ON" in text or "Mfg shell:" in text:
                    stop.set()
                    break
    except Exception:
        pass

    full_output = "".join(output_lines)
    success = "mode ON" in full_output or "Mfg shell:" in full_output
    return success, full_output


def lock_shell_app(client, timeout_s: float = 30.0) -> Tuple[bool, str]:
    """Lock manufacturing shell on nRF52840 (app processor)."""
    return lock_shell(client, HostType.HOST_TYPE_NRF52840, timeout_s=timeout_s)


def lock_shell_comms(client, timeout_s: float = 30.0) -> Tuple[bool, str]:
    """Lock manufacturing shell on nRF9151 (comms processor)."""
    return lock_shell(client, HostType.HOST_TYPE_NRF9151, timeout_s=timeout_s)


def debug_disable(
    client, target: HostType, timeout_s: float = 15.0
) -> Tuple[Optional[bool], Optional[str]]:
    """Disable debug UART output on the given target processor."""
    response, err = send_uart_cmd(
        client,
        target=target,
        command="debug_enable 0",
        success_patterns=["Debug is not enabled"],
        timeout_s=timeout_s,
    )
    if err:
        return None, err
    return "Debug is not enabled" in (response or ""), None


def debug_disable_app(client) -> Tuple[Optional[bool], Optional[str]]:
    """Disable debug UART output on nRF52840 (app processor)."""
    return debug_disable(client, HostType.HOST_TYPE_NRF52840)


def debug_disable_comms(client) -> Tuple[Optional[bool], Optional[str]]:
    """Disable debug UART output on nRF9151 (comms processor)."""
    return debug_disable(client, HostType.HOST_TYPE_NRF9151)
