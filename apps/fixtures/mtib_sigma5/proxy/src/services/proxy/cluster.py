import logging
import grpc
import uuid
import shutil
import yaml
import os
import time
import json
from urllib.parse import urlparse
from datetime import datetime
import threading
from typing import List, Tuple, Optional
import docker
from pathlib import Path

import grpc

from config import conf

# Assuming protos are already correctly imported
# from protos.cluster_controller.cluster_controller_pb2 import (
#     ClusterStatus, HealthCheckRequest, HealthCheckResponse,
#     UpdateDeploymentRequest, UpdateDeploymentResponse,
#     ClusterInfo, GetClusterInfoRequest, GetClusterInfoResponse,
#     TestInfo, ListTestsRequest, ListTestsResponse,
#     ExecuteTestRequest
# )
from protos.cluster_operator.cluster_operator_pb2_grpc import ClusterOperatorStub


class TestCluster:
    """
    This class is used by the proxy server to keep track of a test cluster throughout
    its lifetime. It includes metadata, gRPC stubs, and all other objects needed to  
    Attributes:
        uuid (str): Unique identifier for the cluster.
        url (str): URL where the cluster controller can be accessed.
        stub (ClusterControllerStub): gRPC stub for communicating with the cluster. This stub is used to perform
                                   operations on the cluster via gRPC calls.
        info (ClusterInfo): Dataclass containing detailed information about the cluster such as cluster configuration,
                            node information, and other relevant metadata.
        status (ClusterStatus): The current operational status of the cluster, initialized as NotReady and updated based on cluster operations.
        error (str): String to capture any errors related to the cluster operations, initially empty.
        connected_at (str): Timestamp representing when the cluster was first connected or registered with the proxy server.
    """
    def __init__(self,
                 uuid:str,
                 url:str,
                 channel:grpc.Channel,
                 stub:ClusterOperatorStub):
        """
        Instantiates a new class:

         Parameters:
            uuid (str): The unique identifier of the test cluster.
            url (str): The URL for accessing the cluster.
            stub (ClusterControllerStub): The gRPC stub for remote procedure calls to the cluster.
            info (ClusterInfo): Metadata and other important information about the cluster.
            connected_at (str): The date and time at which the cluster was connected to the proxy.
        """
        self.uuid:str = uuid
        self.url:str = url
        self.channel:grpc.Channel = channel
        self.stub:ClusterOperatorStub = stub

    # def to_json(self) -> str:
    #     pass

    # def connect(self) -> str:
    #     return ""
    
    # def update(self) -> str:
    #     return ""
