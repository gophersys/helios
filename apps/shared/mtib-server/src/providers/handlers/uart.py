import grpc
import serial
import threading
import time
import weakref
import queue
from typing import Iterator, Dict, Optional, Set
from queue import Queue
from corekinect.utils import Logger
from src.shared.types import *


class UartHandler:
    def __init__(self, logger: Logger):
        self.logger = logger
        
        # Map HostType to UART device paths
        self.uart_devices = {
            HostType.HOST_TYPE_NRF9160: "/dev/verdin-uart2",
            HostType.HOST_TYPE_NRF52840: "/dev/verdin-uart1",
            HostType.HOST_TYPE_NRF5340: "/dev/uart1",  # Using uart1 for NRF5340
            HostType.HOST_TYPE_NRF9151: "/dev/uart2",  # Using uart2 for NRF9151
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
        self.rx_stop_events: Dict[HostType, threading.Event] = {}
        
        # Device state
        self.device_active: Dict[HostType, bool] = {}

    def _get_uart_device(self, target: HostType) -> Optional[str]:
        """Get the UART device path for a given target."""
        return self.uart_devices.get(target)

    def _ensure_connection(self, target: HostType) -> Optional[str]:
        """Ensure a UART connection is established for the target."""
        if target not in self.connection_locks:
            self.connection_locks[target] = threading.Lock()
            
        with self.connection_locks[target]:
            if target in self.active_connections:
                return None  # Connection already exists
                
            device_path = self._get_uart_device(target)
            if not device_path:
                return f"Unknown target {target}"
                
            try:
                # Open UART connection with standard settings
                uart = serial.Serial(
                    port=device_path,
                    baudrate=115200,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=1,
                    write_timeout=1
                )
                
                self.active_connections[target] = uart
                self.logger.info(f"UART connection established for {target} on {device_path}")
                
                # Initialize multi-client support
                if target not in self.client_streams:
                    self.client_streams[target] = set()
                if target not in self.client_locks:
                    self.client_locks[target] = threading.Lock()
                if target not in self.tx_queues:
                    self.tx_queues[target] = Queue()
                
                # Start RX thread for this connection
                self._start_rx_thread(target)
                
                return None
                
            except Exception as e:
                return f"Failed to open UART device {device_path}: {str(e)}"

    def _start_rx_thread(self, target: HostType):
        """Start a background thread to read from UART and broadcast to all clients."""
        if target in self.rx_threads and self.rx_threads[target].is_alive():
            return  # Thread already running
            
        if target not in self.rx_stop_events:
            self.rx_stop_events[target] = threading.Event()
            
        def rx_worker():
            uart = self.active_connections[target]
            while not self.rx_stop_events[target].is_set():
                try:
                    if uart.in_waiting > 0:
                        data = uart.read(uart.in_waiting)
                        if data:
                            # Broadcast to all clients
                            self._broadcast_to_clients(target, data)
                    else:
                        time.sleep(0.01)  # Small delay to prevent busy waiting
                except Exception as e:
                    self.logger.error(f"Error reading from UART {target}: {str(e)}")
                    break
                    
        self.rx_threads[target] = threading.Thread(target=rx_worker, daemon=True)
        self.rx_threads[target].start()
        
        # Start TX worker thread
        self._start_tx_thread(target)

    def _start_tx_thread(self, target: HostType):
        """Start a background thread to send data from TX queue to device."""
        def tx_worker():
            uart = self.active_connections[target]
            while not self.rx_stop_events[target].is_set():
                try:
                    # Get data from TX queue
                    data = self.tx_queues[target].get(timeout=0.1)
                    if data:
                        uart.write(data)
                        uart.flush()
                        self.logger.debug(f"Sent {len(data)} bytes to {target}")
                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"Error writing to UART {target}: {str(e)}")
                    break
                    
        tx_thread = threading.Thread(target=tx_worker, daemon=True)
        tx_thread.start()

    def _broadcast_to_clients(self, target: HostType, data: bytes):
        """Broadcast data to all connected clients for this target."""
        with self.client_locks[target]:
            # Clean up dead references
            dead_refs = set()
            for client_ref in self.client_streams[target]:
                client = client_ref()
                if client is None:
                    dead_refs.add(client_ref)
                else:
                    try:
                        client.put(data)
                    except:
                        dead_refs.add(client_ref)
            
            # Remove dead references
            self.client_streams[target] -= dead_refs

    def _close_connection(self, target: HostType):
        """Close UART connection for a target."""
        with self.connection_locks[target]:
            if target in self.rx_stop_events:
                self.rx_stop_events[target].set()
                
            if target in self.rx_threads and self.rx_threads[target].is_alive():
                self.rx_threads[target].join(timeout=1.0)
                
            if target in self.active_connections:
                try:
                    self.active_connections[target].close()
                except:
                    pass
                del self.active_connections[target]
                
            # Clear client streams
            if target in self.client_streams:
                self.client_streams[target].clear()
                
            self.logger.info(f"UART connection closed for {target}")

    def stream(self, request_iterator: Iterator[UartStreamRequest], context: grpc.ServicerContext) -> Iterator[UartStreamResponse]:
        """Handle bidirectional UART streaming with multi-client support."""
        current_target = None
        client_queue = Queue()
        
        try:
            self.logger.info("UART stream started")
            # Process incoming requests and handle TX/RX
            for request in request_iterator:
                if not context.is_active():
                    break
                    
                # Set current target from first request
                if current_target is None:
                    current_target = request.target
                    self.logger.info(f"Starting UART stream for target {current_target} (type: {type(current_target)})")
                    
                    # Ensure connection is established
                    if err := self._ensure_connection(current_target):
                        context.set_code(grpc.StatusCode.INTERNAL)
                        context.set_details(f"Failed to establish UART connection: {err}")
                        return
                    
                    # Register this client
                    with self.client_locks[current_target]:
                        self.client_streams[current_target].add(weakref.ref(client_queue))
                
                # Handle TX data (queue for sending to device)
                if request.data:
                    try:
                        self.tx_queues[current_target].put(request.data)
                        self.logger.debug(f"Queued {len(request.data)} bytes for {current_target}")
                    except Exception as e:
                        error_msg = f"Failed to queue data for {current_target}: {str(e)}"
                        self.logger.error(error_msg)
                        yield UartStreamResponse(
                            success=False,
                            message=error_msg,
                            target=current_target
                        )
                        continue
                
                # Handle RX data (check client queue for received data)
                try:
                    # Non-blocking read from client queue
                    data = client_queue.get_nowait()
                    if data:
                        yield UartStreamResponse(
                            success=True,
                            message="",
                            target=current_target,
                            data=data
                        )
                except queue.Empty:
                    # No data available, send empty response to keep stream alive
                    yield UartStreamResponse(
                        success=True,
                        message="",
                        target=current_target
                    )
                        
        except grpc.RpcError as e:
            # Handle gRPC errors (client disconnection, etc.)
            if e.code() == grpc.StatusCode.CANCELLED:
                self.logger.info("UART stream cancelled by client")
            else:
                self.logger.error(f"UART stream gRPC error: {e.code()} - {e.details()}")
        except Exception as e:
            error_msg = f"UART stream error: {str(e)}"
            self.logger.error(error_msg)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(error_msg)
            
        finally:
            # Clean up client registration
            if current_target:
                with self.client_locks[current_target]:
                    # Remove this client's queue reference
                    for ref in list(self.client_streams[current_target]):
                        if ref() == client_queue:
                            self.client_streams[current_target].discard(ref)
                            break
                
                # Close connection if no more clients
                if not self.client_streams[current_target]:
                    self._close_connection(current_target)
                
                self.logger.info(f"UART stream ended for target {current_target}") 