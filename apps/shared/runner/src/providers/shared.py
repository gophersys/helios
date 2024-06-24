from queue import Queue
from typing import Dict


class UARTSharedState:
    rx_queues: Dict[int, Queue] = {}


uart_shared_state = UARTSharedState()
