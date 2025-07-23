# Standard includes
import time
import sys
import threading
import queue
import select
import os

# Corekinect includes
from corekinect.utils import Logger

# Private includes
from corekinect.mtib_client.v1 import MtibV1Client

# Import types directly from the protocol
from protocols.mtib.mtib_pb2 import HostType, UartStreamRequest


from test.helper import run_sample


class UartTerminal:
    """Interactive UART terminal like minicom."""
    
    def __init__(self, client: MtibV1Client, logger: Logger, target: HostType):
        self.client = client
        self.logger = logger
        self.target = target
        self.running = False
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        
    def start(self):
        """Start the interactive UART terminal."""
        self.running = True
        self.logger.info(f"Starting UART terminal for {self.target}")
        self.logger.info("Type your commands and press Enter. Ctrl+C to exit.")
        
        # Start input thread
        input_thread = threading.Thread(target=self._input_loop, daemon=True)
        input_thread.start()
        
        # Start output thread
        output_thread = threading.Thread(target=self._output_loop, daemon=True)
        output_thread.start()
        
        try:
            # Main loop - handle UART stream
            self._uart_loop()
        except KeyboardInterrupt:
            self.logger.info("\nTerminal interrupted by user")
        finally:
            self.stop()
    
    def _input_loop(self):
        """Background thread to read user input."""
        while self.running:
            try:
                # Check if input is available (non-blocking)
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    line = sys.stdin.readline()
                    if line:
                        # Add newline and encode
                        data = line.encode('utf-8')
                        self.input_queue.put(data)
            except:
                break
    
    def _output_loop(self):
        """Background thread to write output to console."""
        while self.running:
            try:
                data = self.output_queue.get(timeout=0.1)
                if data:
                    # Write to stdout without newline (raw output)
                    sys.stdout.write(data.decode('utf-8', errors='ignore'))
                    sys.stdout.flush()
            except queue.Empty:
                continue
            except:
                break
    
    def _uart_loop(self):
        """Main UART communication loop."""
        def request_iterator():
            while self.running:
                try:
                    # Get input from queue (non-blocking)
                    data = self.input_queue.get_nowait()
                    yield UartStreamRequest(target=self.target, data=data)
                except queue.Empty:
                    # No input, send empty request to keep stream alive
                    yield UartStreamRequest(target=self.target, data=b"")
        
        # Start UART stream
        for response in self.client.UartStream(self.target, request_iterator()):
            if not self.running:
                break
                
            if not response.success:
                self.logger.error(f"UART stream error: {response.message}")
                break
            
            if response.data:
                # Put received data in output queue
                self.output_queue.put(response.data)
    
    def stop(self):
        """Stop the terminal."""
        self.running = False
        self.logger.info("UART terminal stopped")


def sample(client: MtibV1Client, logger: Logger) -> None:
    """
    Interactive UART terminal like minicom.
    """
    logger.info("Interactive UART Terminal")
    
    # Test target - use protobuf enum
    target = HostType.HOST_TYPE_NRF52840
    logger.info(f"Opening UART terminal for target: {target}")
    
    # Create and start terminal
    terminal = UartTerminal(client, logger, target)
    terminal.start()


if __name__ == "__main__":
    run_sample(sample, "uart_simple") 