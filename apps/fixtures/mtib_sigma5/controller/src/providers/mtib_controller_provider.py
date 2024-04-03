# Standard includes
import grpc
import logging
import time
from typing import List
from concurrent import futures

# App includes
from config import conf

# Protocol includes
from protos.mtib_controller.mtib_controller_pb2_grpc import MtibControllerServicer
from .types import * # All types are declared externally for readability of this file

class MtibControllerServicerProvider(MtibControllerServicer):
    def __init__(self):
        pass

    # -------------------------------------------------------------------------------------------------
    #                                                                                       HealthCheck
    # -----------------------------------------------------------------------------------------------*/
    def HealthCheck(self, request, context):
        logging.debug("HealthCheck RPC Called")
        return HealthCheckResponse(ok=True)