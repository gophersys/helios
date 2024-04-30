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
from enum import Enum

import grpc

from config import conf

# Assuming protos are already correctly imported
from protos.cluster_operator.cluster_operator_pb2 import (
    OperatorStatus
)

from protos.cluster_operator.cluster_operator_pb2_grpc import ClusterOperatorStub

class TestClusterStatus(Enum):
    DISCONNECTED = 0
    CONNECTED = 1
    
    def to_human_readable(self):
        if self == TestClusterStatus.DISCONNECTED:
            return "Disconnected"
        elif self == TestClusterStatus.CONNECTED:
            return "Connected"
        else:
            return "Unknown status"

class TestCluster:
    def __init__(self,
                 name:str,
                 type:str,
                 uuid:str,
                 registered:bool, 
                 status:TestClusterStatus,
                 url:Optional[str],
                 channel:Optional[grpc.Channel],
                 stub:Optional[ClusterOperatorStub]):
        self.name:str = name
        self.type:str = type
        self.uuid:str = uuid
        self.registered:bool = registered
        self.status:TestClusterStatus = status
        self.url:str = url
        self.channel:grpc.Channel = channel
        self.stub:ClusterOperatorStub = stub