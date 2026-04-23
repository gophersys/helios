# Standard library
import os
import queue
import threading
import time
import weakref
from queue import Queue
from typing import Dict, Iterator, Optional, Set

# Third party
import grpc
import serial

# Corekinect
from corekinect.utils import Logger

# Proto types
from src.shared.types import (
    HostType,
    UartStreamRequest,
    UartStreamResponse,
)


class UartHandler:
    def __init__(self, logger: Logger):
        self.logger = logger

        # Map HostType to UART device paths
        # Theta board: nRF52840 (app proc) on uart1, nRF9151 (comms coproc) on uart2
        self.uart_devices = {
            HostType.HOST_TYPE_NRF9160: "/dev/verdin-uart1",
            HostType.HOST_TYPE_NRF52840: "/dev/verdin-uart2",  # Theta app proc on uart1
            HostType.HOST_TYPE_NRF5340: "/dev/verdin-uart1",  # Using uart1 for NRF5340
            HostType.HOST_TYPE_NRF9151: "/dev/verdin-uart1",  # Theta comms coproc on uart2
        }

        # Device-specific UART configurations
        self.uart_configs = {
            HostType.HOST_TYPE_NRF9160: {
                "baudrate": 115200,
                "bytesize": serial.EIGHTBITS,
                "parity": serial.PARITY_NONE,
                "stopbits": serial.STOPBITS_ONE,
                "timeout": 1,
                "write_timeout": 1,  # Increased write timeout
                "xonxoff": False,
                "rtscts": False,
                "dsrdtr": False,
            },
            HostType.HOST_TYPE_NRF52840: {
                "baudrate": 115200,
                "bytesize": serial.EIGHTBITS,
                "parity": serial.PARITY_NONE,
                "stopbits": serial.STOPBITS_ONE,
                "timeout": 1,
                "write_timeout": 1,
                "xonxoff": False,
                "rtscts": False,
                "dsrdtr": False,
            },
            HostType.HOST_TYPE_NRF5340: {
                "baudrate": 115200,
                "bytesize": serial.EIGHTBITS,
                "parity": serial.PARITY_NONE,
                "stopbits": serial.STOPBITS_ONE,
                "timeout": 1,
                "write_timeout": 5,
                "xonxoff": False,
                "rtscts": False,
                "dsrdtr": False,
            },
            HostType.HOST_TYPE_NRF9151: {
                "baudrate": 115200,
                "bytesize": serial.EIGHTBITS,
                "parity": serial.PARITY_NONE,
                "stopbits": serial.STOPBITS_ONE,
                "timeout": 1,
                "write_timeout": 5,
                "xonxoff": False,
                "rtscts": False,
                "dsrdtr": False,
            },
        }

        # Active UART connections
        self.active_connections: Dict[HostType, serial.Serial] = {}
        self.connection_locks: Dict[HostType, threading.Lock] = {}

        # Multi-client support
        self.client_streams: Dict[HostType, Set[weakref.ref]] = {}
        self.client_locks: Dict[HostType, threading.Lock] = {}

        # TX queue for each device (commands to send to device)
        self.tx_queues: Dict[HostType, Queue] = {}

        # RX thread for each device (reads from device and broadcasts to all clients)
        self.rx_threads: Dict[HostType, threading.Thread] = {}
        self.tx_threads: Dict[HostType, threading.Thread] = {}
        self.rx_stop_events: Dict[HostType, threading.Event] = {}

        # Device state
        self.device_active: Dict[HostType, bool] = {}

    def _get_uart_device(self, target: HostType) -> Optional[str]:
        """Get the UART device path for a given target."""
        return self.uart_devices.get(target)

    def _get_uart_config(self, target: HostType) -> Optional[dict]:
        """Get the UART configuration for a given target."""
        return self.uart_configs.get(target)

    def test_uart_connection(self, target: HostType) -> str:
        """Test UART connection by sending a simple test pattern."""
        try:
            # Ensure connection exists
            if err := self._ensure_connection(target):
                return f"Failed to establish connection: {err}"

            uart = self.active_connections[target]

            # Send a simple test pattern
            test_data = b"\r\n"
            self.logger.info(f"Testing UART connection for {target} by sending: {test_data.hex()}")

            # Queue the test data
            self.tx_queues[target].put(test_data)

            # Wait a bit for the data to be sent
            time.sleep(0.1)

            return f"Test data queued for {target}"

        except Exception as e:
            return f"UART test failed for {target}: {str(e)}"

    def get_uart_status(self, target: HostType) -> dict:
        """Get the current status of a UART connection."""
        status = {
            "target": target,
            "connected": False,
            "device_path": None,
            "config": None,
            "queue_size": 0,
            "threads_running": False,
            "active_clients": 0,
            "device_active": False,
        }

        try:
            if target in self.active_connections:
                uart = self.active_connections[target]
                status["connected"] = uart.is_open
                status["device_path"] = uart.port
                status["config"] = {
                    "baudrate": uart.baudrate,
                    "bytesize": uart.bytesize,
                    "parity": uart.parity,
                    "stopbits": uart.stopbits,
                    "timeout": uart.timeout,
                    "write_timeout": uart.write_timeout,
                }

            if target in self.tx_queues:
                status["queue_size"] = self.tx_queues[target].qsize()

            if target in self.rx_threads and target in self.tx_threads:
                status["threads_running"] = self.rx_threads[target].is_alive() and self.tx_threads[target].is_alive()

            if target in self.client_streams:
                status["active_clients"] = len(self.client_streams[target])

            if target in self.device_active:
                status["device_active"] = self.device_active[target]

        except Exception as e:
            status["error"] = str(e)

        return status

    def reset_uart_connection(self, target: HostType) -> str:
        """Force reset a UART connection for a target."""
        try:
            self.logger.info(f"Force resetting UART connection for {target}")
            self._close_connection(target)
            time.sleep(0.1)  # Small delay to ensure cleanup

            # Try to re-establish connection
            if err := self._ensure_connection(target):
                return f"Failed to re-establish connection: {err}"

            return f"Successfully reset UART connection for {target}"

        except Exception as e:
            return f"Failed to reset UART connection for {target}: {str(e)}"

    def _ensure_connection(self, target: HostType) -> Optional[str]:
        """Ensure a UART connection is established for the target."""
        if target not in self.connection_locks:
            self.connection_locks[target] = threading.Lock()

        with self.connection_locks[target]:
            # Check if connection exists and is still valid
            if target in self.active_connections:
                uart = self.active_connections[target]
                if uart.is_open:
                    return None  # Connection valid, RX thread handles data
                else:
                    # Connection exists but is closed, remove it
                    del self.active_connections[target]

            device_path = self._get_uart_device(target)
            if not device_path:
                return f"Unknown target {target}"

            # Check if device exists
            if not os.path.exists(device_path):
                return f"UART device {device_path} does not exist"

            config = self._get_uart_config(target)
            if not config:
                return f"No UART configuration for target {target}"

            try:
                # Open UART connection with device-specific settings
                # Note: Removed stty sane reset as it can interfere with pyserial settings
                uart = serial.Serial(port=device_path, **config)
                self.logger.info(f"Opened UART {device_path} for {target}")

                # Test the connection by trying to read any pending data
                uart.reset_input_buffer()
                uart.reset_output_buffer()

                self.active_connections[target] = uart
                self.logger.info(f"UART connection established for {target} on {device_path} with config: {config}")

                # Initialize multi-client support
                if target not in self.client_streams:
                    self.client_streams[target] = set()
                if target not in self.client_locks:
                    self.client_locks[target] = threading.Lock()
                if target not in self.tx_queues:
                    self.tx_queues[target] = Queue()
                if target not in self.rx_stop_events:
                    self.rx_stop_events[target] = threading.Event()

                # Start RX and TX threads for this connection
                self._start_rx_thread(target)
                self._start_tx_thread(target)

                # Mark device as active
                self.device_active[target] = True

                return None

            except Exception as e:
                return f"Failed to open UART device {device_path}: {str(e)}"

    def _start_rx_thread(self, target: HostType):
        """Start a background thread to read from UART and broadcast to all clients.

        Uses smart batching to reduce gRPC overhead:
        - Flushes on newline (complete log line from Zephyr RTOS)
        - Flushes when buffer >= 256 bytes (prevent unbounded buffering)
        - Flushes after 50ms timeout (for shell prompts without newline)

        This ensures complete log lines are sent as single messages while
        still delivering partial data (like shell prompts) promptly.
        """
        # Stop existing thread if running
        if target in self.rx_threads and self.rx_threads[target].is_alive():
            self.rx_stop_events[target].set()
            self.rx_threads[target].join(timeout=1.0)

        # Reset stop event
        self.rx_stop_events[target].clear()

        # Batching constants
        MAX_BUFFER_SIZE = 256
        FLUSH_TIMEOUT_MS = 50  # 50ms - faster for responsive shells
        NEWLINE_CHARS = b'\n\r'

        def rx_worker():
            uart = self.active_connections[target]
            self.logger.info(f"RX thread started for {target} with batching (newline/256B/50ms)")

            buffer = bytearray()
            last_flush_time = time.time()
            last_log_time = time.time()

            def flush_buffer():
                nonlocal buffer, last_flush_time
                if buffer:
                    chunk = bytes(buffer)
                    buffer.clear()
                    last_flush_time = time.time()
                    self.logger.debug(f"Flushing {len(chunk)} bytes from {target}")
                    self._broadcast_to_clients(target, chunk)

            def should_flush_on_newline() -> bool:
                """Check if buffer contains a newline and flush up to it."""
                nonlocal buffer, last_flush_time
                for i, byte in enumerate(buffer):
                    if byte in NEWLINE_CHARS:
                        # Flush up to and including the newline
                        chunk = bytes(buffer[:i + 1])
                        del buffer[:i + 1]
                        last_flush_time = time.time()
                        self.logger.debug(f"Newline flush: {len(chunk)} bytes from {target}")
                        self._broadcast_to_clients(target, chunk)
                        return True
                return False

            while not self.rx_stop_events[target].is_set():
                try:
                    # Block until at least 1 byte arrives (up to serial timeout)
                    data = uart.read(1)
                    if data:
                        # Immediately grab all remaining bytes available
                        in_waiting = uart.in_waiting
                        if in_waiting > 0:
                            additional = uart.read(min(in_waiting, 4096))
                            data += additional

                        buffer.extend(data)

                        # Check flush conditions (priority order)
                        # 1. Flush complete lines (newline detected)
                        while should_flush_on_newline():
                            pass  # Keep flushing lines while they exist

                        # 2. Flush if buffer too large
                        if len(buffer) >= MAX_BUFFER_SIZE:
                            flush_buffer()

                    # 3. Timeout flush for partial data (shell prompts etc)
                    elapsed_ms = (time.time() - last_flush_time) * 1000
                    if buffer and elapsed_ms >= FLUSH_TIMEOUT_MS:
                        self.logger.debug(f"Timeout flush after {elapsed_ms:.0f}ms")
                        flush_buffer()

                    # Periodic logging
                    current_time = time.time()
                    if current_time - last_log_time > 30:
                        self.logger.debug(f"RX thread for {target} alive, buffer={len(buffer)} bytes")
                        last_log_time = current_time

                except Exception as e:
                    if not self.rx_stop_events[target].is_set():
                        self.logger.error(f"Error reading from UART {target}: {str(e)}")
                    break

            # Final flush on shutdown
            if buffer:
                self.logger.debug(f"Final flush on shutdown: {len(buffer)} bytes")
                self._broadcast_to_clients(target, bytes(buffer))

        self.rx_threads[target] = threading.Thread(target=rx_worker, daemon=True)
        self.rx_threads[target].start()

    def _start_tx_thread(self, target: HostType):
        """Start a background thread to send data from TX queue to device."""
        # Stop existing thread if running
        if target in self.tx_threads and self.tx_threads[target].is_alive():
            self.rx_stop_events[target].set()  # Use same stop event for both threads
            self.tx_threads[target].join(timeout=1.0)

        def tx_worker():
            uart = self.active_connections[target]
            consecutive_errors = 0
            max_errors = 3

            while not self.rx_stop_events[target].is_set():
                try:
                    # Get data from TX queue
                    data = self.tx_queues[target].get(timeout=0.1)
                    if data and not self.rx_stop_events[target].is_set():
                        # Write data and verify it was sent
                        bytes_written = uart.write(data)
                        uart.flush()

                        if bytes_written != len(data):
                            self.logger.error(
                                f"Failed to write all data to {target}: wrote {bytes_written}/{len(data)} bytes"
                            )
                            consecutive_errors += 1
                        else:
                            self.logger.debug(f"Successfully sent {bytes_written} bytes to {target}: {data.hex()}")
                            consecutive_errors = 0  # Reset error counter on success

                        # Small delay to ensure data is processed
                        time.sleep(0.001)

                        # If we've had too many consecutive errors, try to recover
                        if consecutive_errors >= max_errors:
                            self.logger.error(f"Too many consecutive UART errors for {target}, attempting recovery...")
                            try:
                                # Try to reset the UART
                                uart.reset_output_buffer()
                                uart.reset_input_buffer()
                                # Send a test byte
                                test_byte = b"\r"
                                uart.write(test_byte)
                                uart.flush()
                                time.sleep(0.01)
                                consecutive_errors = 0
                                self.logger.info(f"UART recovery successful for {target}")
                            except Exception as recovery_error:
                                self.logger.error(f"UART recovery failed for {target}: {recovery_error}")
                                # Close connection and let it be re-established
                                break

                except queue.Empty:
                    continue
                except Exception as e:
                    if not self.rx_stop_events[target].is_set():
                        self.logger.error(f"Error writing to UART {target}: {str(e)}")
                        consecutive_errors += 1

                        # If it's a hardware error, try to recover
                        if "PortNotOpenError" in str(e) or "OSError" in str(e):
                            self.logger.error(f"Hardware UART error for {target}, closing connection")
                            break
                    break

        self.tx_threads[target] = threading.Thread(target=tx_worker, daemon=True)
        self.tx_threads[target].start()

    def _broadcast_to_clients(self, target: HostType, data: bytes):
        """Broadcast data to all connected clients for this target."""
        with self.client_locks[target]:
            # Clean up dead references
            dead_refs = set()
            for client_ref in list(self.client_streams[target]):  # Use list() to avoid modification during iteration
                client = client_ref()
                if client is None:
                    dead_refs.add(client_ref)
                else:
                    try:
                        client.put(data)
                    except Exception as e:
                        self.logger.debug(f"Failed to send data to client: {e}")
                        dead_refs.add(client_ref)

            # Remove dead references
            self.client_streams[target] -= dead_refs

    def _close_connection(self, target: HostType):
        """Close UART connection for a target."""
        with self.connection_locks[target]:
            # Set stop event first
            if target in self.rx_stop_events:
                self.rx_stop_events[target].set()

            # Wait for threads to finish
            if target in self.rx_threads and self.rx_threads[target].is_alive():
                self.rx_threads[target].join(timeout=2.0)

            if target in self.tx_threads and self.tx_threads[target].is_alive():
                self.tx_threads[target].join(timeout=2.0)

            # Close UART connection
            if target in self.active_connections:
                try:
                    self.active_connections[target].close()
                except Exception as e:
                    self.logger.debug(f"Error closing UART connection: {e}")
                del self.active_connections[target]

            # Clear client streams and queues
            if target in self.client_streams:
                self.client_streams[target].clear()
            if target in self.tx_queues:
                # Clear any pending data
                while not self.tx_queues[target].empty():
                    try:
                        self.tx_queues[target].get_nowait()
                    except queue.Empty:
                        break

            # Mark device as inactive
            self.device_active[target] = False

            self.logger.info(f"UART connection closed for {target}")

    def stream(
        self, request_iterator: Iterator[UartStreamRequest], context: grpc.ServicerContext
    ) -> Iterator[UartStreamResponse]:
        """Handle bidirectional UART streaming with push-based RX.

        RX and TX are fully decoupled:
        - A background thread consumes client requests (TX path)
        - The main generator yields RX data as soon as it arrives,
          WITHOUT waiting for the next client request

        This eliminates the previous bottleneck where the server could
        only yield one response per client request.
        """
        current_target = None
        client_queue = Queue()
        stop_event = threading.Event()
        target_ready = threading.Event()
        target_container = [None]
        init_error = [None]

        def tx_consumer():
            """Background thread: consume client requests, handle TX writes."""
            nonlocal current_target
            try:
                for request in request_iterator:
                    if stop_event.is_set() or not context.is_active():
                        break

                    # Initialize on first request
                    if target_container[0] is None:
                        current_target = request.target
                        target_container[0] = current_target
                        self.logger.info(
                            f"Starting UART stream for target {current_target}"
                        )

                        # Ensure connection is established
                        if err := self._ensure_connection(current_target):
                            init_error[0] = f"Failed to establish UART connection: {err}"
                            stop_event.set()
                            target_ready.set()
                            return

                        # Register this client
                        with self.client_locks[current_target]:
                            self.client_streams[current_target].add(weakref.ref(client_queue))

                        target_ready.set()

                    # Handle TX data (queue for sending to device)
                    if request.data:
                        try:
                            self.tx_queues[target_container[0]].put(request.data)
                            self.logger.debug(
                                f"Queued {len(request.data)} bytes for {target_container[0]}"
                            )
                        except Exception as e:
                            self.logger.error(f"Failed to queue TX data: {e}")

            except grpc.RpcError:
                pass  # Client disconnected
            except Exception as e:
                if not stop_event.is_set():
                    self.logger.debug(f"TX consumer error: {e}")
            finally:
                stop_event.set()
                target_ready.set()

        tx_thread = None

        try:
            self.logger.info("UART stream started (push-based)")

            # Start TX consumer in background thread
            tx_thread = threading.Thread(
                target=tx_consumer, daemon=True, name="uart-tx-consumer"
            )
            tx_thread.start()

            # Wait for target initialization
            target_ready.wait(timeout=10.0)
            if init_error[0]:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(init_error[0])
                return

            if stop_event.is_set() or target_container[0] is None:
                return

            current_target = target_container[0]

            # Main generator loop: yield RX data as soon as it arrives.
            # NOT gated by client requests.
            while not stop_event.is_set() and context.is_active():
                try:
                    # Block up to 10ms for data
                    data = client_queue.get(timeout=0.01)
                    if data:
                        yield UartStreamResponse(
                            success=True, message="", target=current_target, data=data
                        )
                except queue.Empty:
                    continue

        except grpc.RpcError as e:
            if hasattr(e, 'code') and e.code() == grpc.StatusCode.CANCELLED:
                self.logger.info("UART stream cancelled by client")
            else:
                self.logger.error(f"UART stream gRPC error: {e}")
        except Exception as e:
            error_msg = f"UART stream error: {str(e)}"
            self.logger.error(error_msg)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(error_msg)

        finally:
            stop_event.set()
            if tx_thread:
                tx_thread.join(timeout=1.0)

            # Clean up client registration
            if current_target:
                with self.client_locks[current_target]:
                    for ref in list(self.client_streams[current_target]):
                        if ref() == client_queue:
                            self.client_streams[current_target].discard(ref)
                            break

                if not self.client_streams[current_target]:
                    self.logger.info(f"No more clients for {current_target}, closing connection")
                    self._close_connection(current_target)
                else:
                    self.logger.info(
                        f"Client disconnected from {current_target}, "
                        f"{len(self.client_streams[current_target])} clients remaining"
                    )

                self.logger.info(f"UART stream ended for target {current_target}")
