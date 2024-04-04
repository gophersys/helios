# Standard includes
import grpc
import logging
import time
from typing import List
from concurrent import futures

# App includes
from config import conf
from src.app.controller import ControllerServer

# Protocol includes
from protos.mtib_controller.mtib_controller_pb2_grpc import MtibControllerServicer
from .types import * # All types are declared externally for readability of this file

class MtibControllerServicerProvider(MtibControllerServicer):
    def __init__(self):
        pass

    # -------------------------------------------------------------------------------------------------
    #                                                                                       HealthCheck
    # -----------------------------------------------------------------------------------------------*/
    def HealthCheck(self, request:HealthCheckRequest, context):
        logging.debug("HealthCheck RPC Called")
        if ControllerServer().error != "":
            return HealthCheckResponse(ok=False, error=ControllerServer().error)
        
        return HealthCheckResponse(ok=True)
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                  Cluster Metadata
    # -----------------------------------------------------------------------------------------------*/
    def GetClusterMetadata(self, request:GetClusterMetadataRequest, context):
        logging.debug("GetClusterMetadata RPC Called")
        return GetClusterMetadataResponse()