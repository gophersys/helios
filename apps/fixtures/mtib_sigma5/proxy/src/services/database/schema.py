# Standard imports
from typing import Optional
from enum import Enum
from dataclasses import dataclass, field
from typing import List

# 3rd party includes
import grpc
from google.protobuf.json_format import MessageToJson, MessageToDict, Parse, ParseDict

# Protocol includes
from protos.cluster_operator.cluster_operator_pb2 import (
    ClusterStatus
)
from protos.cluster_operator.cluster_operator_pb2_grpc import ClusterOperatorStub
from protos.cluster_test.cluster_test_pb2 import (
    TestStepResult, TestInfo
)

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


# -------------------------------------------------------------------------------------------------
#                                                                                       Deployments
# -----------------------------------------------------------------------------------------------*/
@dataclass
class DeploymentInfo:
    name: str
    uuid: str
    created_at: str

    def marshal(self) -> dict:
        return {
            "name": self.name,
            "uuid": self.uuid,
            "created_at": self.created_at,
        }

    @classmethod
    def unmarshal(cls, data: dict) -> 'DeploymentInfo':
        return cls(
            name=data['name'],
            uuid=data['uuid'],
            created_at=data['created_at']
        )

# -------------------------------------------------------------------------------------------------
#                                                                                              Logs
# -----------------------------------------------------------------------------------------------*/
@dataclass
class LogInfo:
    created_at: str
    logs_folder: str
    last_updated_at: str

    def marshal(self) -> dict:
        return {
            "created_at": self.created_at,
            "logs_folder": self.logs_folder,
            "last_updated_at": self.last_updated_at
        }

    @classmethod
    def unmarshal(cls, data: dict) -> 'LogInfo':
        return cls(
            created_at=data['created_at'],
            logs_folder=data['logs_folder'],
            last_updated_at=data['last_updated_at'],
        )

# -------------------------------------------------------------------------------------------------
#                                                                                      Test results
# -----------------------------------------------------------------------------------------------*/

@dataclass
class TestExecution:
    test_info: TestInfo
    test_config: str
    test_nodes: List[str]  # Assuming test_nodes should be a list of node identifiers
    started_at: str
    finished_at: str
    error:str
    stopped: bool
    results: List[List[TestStepResult]]

    def marshal(self) -> dict:
        """ Serialize the TestExecution object to a dictionary, handling Protobuf types. """
        return {
            "test_info": MessageToDict(self.test_info, including_default_value_fields=True),  # Serialize the Protobuf TestInfo object to a JSON string
            "test_config": self.test_config,
            "test_nodes": self.test_nodes,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "stopped": self.stopped,
            "results": [[MessageToDict(step, including_default_value_fields=True) for step in result_group] for result_group in self.results] # Serialize the Protobuf TestInfo object to a JSON string
        }

    @classmethod
    def unmarshal(cls, data: dict) -> 'TestExecution':
        """ Deserialize a dictionary to a TestExecution object, handling Protobuf types. """
        test_info = TestInfo()
        ParseDict(data["test_info"], test_info)  # Deserialize the dictionary back to a TestInfo object

        results = []
        for result_group in data["results"]:
            group = [TestStepResult() for _ in result_group]
            for result_dict, result_obj in zip(result_group, group):
                ParseDict(result_dict, result_obj)
            results.append(group)

        return cls(
            test_info=test_info,
            test_config=data["test_config"],
            test_nodes=data["test_nodes"],
            started_at=data["started_at"],
            finished_at=data["finished_at"],
            error=data["error"],
            stopped=data["stopped"],
            results=results
        )

    
@dataclass
class TestExecutionInfo:
    test_name:str 
    uuid: str                  # Unique identifier for this execution entry
    error: str
    created_at: str            # When this entry was initially added to the file system

    def marshal(self) -> dict:
        return {
            "test_name": self.test_name,
            "uuid": self.uuid,
            "error": self.error,
            "created_at": self.created_at,
        }

    @classmethod
    def unmarshal(cls, data: dict) -> 'TestExecutionInfo':
        return cls(
            test_name=data["test_name"],
            uuid=data["uuid"],
            error=data["error"],
            created_at=data["created_at"],
        )
    
# -------------------------------------------------------------------------------------------------
#                                                                                          Clusters
# -----------------------------------------------------------------------------------------------*/
@dataclass
class ClusterInfo:
    name: str
    type: ClusterType
    uuid: str
    registered: bool
    created_at: str
    last_updated_at: str
    current_deployment: str
    deployments: List[DeploymentInfo] = field(default_factory=list)
    logs: List[LogInfo] = field(default_factory=list)
    executions: List[TestExecutionInfo] = field(default_factory=list)

    def marshal(self) -> dict:
        return {
            "name": self.name,
            "type": ClusterType.to_string(self.type),
            "uuid": self.uuid,
            "registered": self.registered,
            "created_at": self.created_at,
            "last_updated_at": self.last_updated_at,
            "current_deployment": self.current_deployment,
            "deployments": [deployment.marshal() for deployment in self.deployments],
            "logs": [log.marshal() for log in self.logs],
            "executions": [execution.marshal() for execution in self.executions]
        }

    @classmethod
    def unmarshal(cls, data: dict) -> 'ClusterInfo':
        # Unmarshall the lists independently first
        deployments = [DeploymentInfo.unmarshal(deployment) for deployment in data.get('deployments', [])]
        logs = [LogInfo.unmarshal(log) for log in data.get('logs', [])]
        executions = [TestExecutionInfo.unmarshal(execution) for execution in data.get('executions', [])]
        
        return cls(
            name=data['name'],
            type=ClusterType.from_string(data['type']),
            uuid=data['uuid'],
            registered=data['registered'],
            created_at=data['created_at'],
            last_updated_at=data['last_updated_at'],
            current_deployment=data['current_deployment'],
            deployments=deployments,
            logs=logs,
            executions=executions
        )
        
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
                 info:ClusterInfo,
                 status:ClusterStatus,
                 error:str,
                 url:Optional[str],
                 channel:Optional[grpc.Channel],
                 stub:Optional[ClusterOperatorStub]):
        self.info:ClusterInfo = info
        self.status:ClusterStatus = status
        self.error:str = error
        self.url:str = url
        self.channel:grpc.Channel = channel
        self.stub:ClusterOperatorStub = stub
        