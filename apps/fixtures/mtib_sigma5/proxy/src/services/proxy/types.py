# Standard imports
from typing import Optional
from enum import Enum

# 3rd party includes
import grpc

# Protocol includes
from protos.cluster_operator.cluster_operator_pb2_grpc import ClusterOperatorStub

# App includes
from config import conf

class ClusterType(Enum):
    """
    These are the types of compute groups that the server supports
    """
    MANUFACTURING = 0
    
    @staticmethod
    def is_valid_type(type_str: str) -> bool:
        """
        Check if the provided type string corresponds to a valid enum member.

        Args:
            type_str (str): The type string to check.

        Returns:
            bool: True if it is a valid enum member, False otherwise.
        """
        try:
            ClusterType[type_str.upper()]
            return True
        except KeyError:
            return False
    
    @staticmethod
    def from_string(type_str:str):
        if type_str == "Manufacturing":
            return ClusterType.MANUFACTURING
        else:
            return None
        
    def to_string(self):
        if self == ClusterType.MANUFACTURING:
            return "Manufacturing"
        else:
            return "Unknown"
    
class ClusterStatus(Enum):
    """
    This status is unique to the proxy server and is used to manage
    the state of a cluster entry.
    """
    DISCONNECTED = 0
    CONNECTED = 1
    
    def to_string(self):
        if self == ClusterStatus.DISCONNECTED:
            return "Disconnected"
        elif self == ClusterStatus.CONNECTED:
            return "Connected"
        else:
            return "Unknown status"

class Cluster:
    """
    Represents a network or server cluster with communication capabilities.

    Attributes:
        name (str): The name of the cluster.
        type (ClusterType): The type of the cluster.
        uuid (str): The unique identifier for the cluster.
        registered (bool): Indicates whether the cluster has connected since creation.
        status (ClusterStatus): The operational status of the cluster.
        url (Optional[str]): The URL for accessing the cluster, if applicable.
        channel (Optional[grpc.Channel]): The gRPC channel for communication with the cluster.
        stub (Optional[ClusterOperatorStub]): The gRPC stub for interfacing with cluster operations.
    """
    def __init__(self,
                 name:str,
                 type:ClusterType,
                 uuid:str,
                 registered:bool, 
                 status:ClusterStatus,
                 url:Optional[str],
                 channel:Optional[grpc.Channel],
                 stub:Optional[ClusterOperatorStub]):
        self.name:str = name
        self.type:ClusterType = type
        self.uuid:str = uuid
        self.registered:bool = registered
        self.status:ClusterStatus = status
        self.url:str = url
        self.channel:grpc.Channel = channel
        self.stub:ClusterOperatorStub = stub