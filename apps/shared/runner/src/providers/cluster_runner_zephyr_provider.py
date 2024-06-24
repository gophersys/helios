# Standard includes
import logging
import os
from queue import Queue
from typing import Optional, Tuple

# App includes
from config import conf
# Corekinect includes
from corekinect.cipher.cipher import Cipher, CipherRpcErr
from protos.mtib_runner_zephyr.mtib_runner_zephyr_pb2_cipher import \
    MtibRunnerZephyr

from .shared import uart_shared_state
# Protocol includes
from .types import *


class MtibRunnerZephyrProvider(MtibRunnerZephyr):
    def __init__(self, daemon: Cipher):
        self.daemon = daemon

    def SigmaToPiMessageHandler(
        self, request: UartMessageRequest
    ) -> Tuple[UartMessageResponse, Optional[CipherRpcErr]]:
        response = UartMessageResponse(success=True, error="")

        # Queue the received data for the corresponding device
        if request.device in uart_shared_state.rx_queues:
            uart_shared_state.rx_queues[request.device].put(request.data)

        return response, None
