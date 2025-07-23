# Standard includes
import time
import sys

# Corekinect includes
from corekinect.utils import Logger

# Private includes
from corekinect.mtib_client.v1 import MtibV1Client
from test.helper import run_sample

# Import types directly from the protocol
from protocols.mtib.mtib_pb2 import HostType, UartStreamRequest


def sample(client: MtibV1Client, logger: Logger) -> None:
    """
    Debug UART serialization issue.
    """
    logger.info("Debug UART Serialization")
    
    # Test target - use the correct protobuf enum value
    target = HostType.HOST_TYPE_NRF9160
    logger.info(f"Testing with target: {target} (type: {type(target)})")
    
    # Test creating a simple request
    try:
        request = UartStreamRequest(target=target, data=b"test")
        logger.info(f"Created request: {request}")
        logger.info(f"Request target: {request.target} (type: {type(request.target)})")
        logger.info(f"Request data: {request.data}")
    except Exception as e:
        logger.error(f"Error creating request: {e}")
        return
    
    # Test simple stream
    def request_iterator():
        yield UartStreamRequest(target=target, data=b"AT\r\n")
        yield UartStreamRequest(target=target, data=b"")
    
    try:
        logger.info("Starting UART stream...")
        response_count = 0
        
        for response in client.UartStream(target, request_iterator()):
            logger.info(f"Got response: {response}")
            response_count += 1
            if response_count >= 5:
                break
                
    except Exception as e:
        logger.error(f"UART stream error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_sample(sample, "uart_debug") 