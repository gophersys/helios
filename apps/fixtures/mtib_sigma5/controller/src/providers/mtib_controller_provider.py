# Standard includes
import grpc
import logging
import time
from typing import List
from concurrent import futures

# App includes
from config import conf
from src.app.controller import ControllerServer
from src.clusters.base import BaseTestCluster

# Protocol includes
from protos.mtib_controller.mtib_controller_pb2_grpc import MtibControllerServicer
from .types import * # All types are declared externally for readability of this file

class MtibControllerServicerProvider(MtibControllerServicer):

    cluster:BaseTestCluster = None

    def __init__(self, cluster:BaseTestCluster):
        self.cluster = cluster
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                 Pass Test Cluster
    # -----------------------------------------------------------------------------------------------*/
    def set_test_cluster(self, cluster:BaseTestCluster):
        self.cluster = cluster

    # -------------------------------------------------------------------------------------------------
    #                                                                                       HealthCheck
    # -----------------------------------------------------------------------------------------------*/
    def HealthCheck(self, request:HealthCheckRequest, context):
        logging.debug("HealthCheck RPC Called")
        if ControllerServer().error != "":
            return HealthCheckResponse(status=ClusterStatus.Errored, error=ControllerServer().error)
        
        return HealthCheckResponse(status=ClusterStatus.Ready)
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                  Cluster Metadata
    # -----------------------------------------------------------------------------------------------*/
    def GetClusterInfo(self, request:GetClusterInfoRequest, context):
        return GetClusterInfoResponse(
            info = self.cluster.get_cluster_metadata()
        )