# Standard imports
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

# 3rd party includes
import grpc
# App includes
from config import conf
from google.protobuf.json_format import (MessageToDict, MessageToJson, Parse,
                                         ParseDict)
# Protocol includes
from protos.cluster_operator.cluster_operator_pb2 import ClusterStatus
from protos.cluster_operator.cluster_operator_pb2_grpc import \
    ClusterOperatorStub
from protos.cluster_test.cluster_test_pb2 import TestInfo, TestStepResult


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
    def from_string(type_str: str):
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
            "createdAt": self.created_at,
        }

    @classmethod
    def unmarshal(cls, data: dict) -> "DeploymentInfo":
        return cls(name=data["name"], uuid=data["uuid"], created_at=data["createdAt"])


# -------------------------------------------------------------------------------------------------
#                                                                                              Logs
# -----------------------------------------------------------------------------------------------*/
@dataclass
class LogInfo:
    created_at: str
    logs_folder: str
    last_updated_at: str

    def marshal(self) -> dict:
        return {"createdAt": self.created_at, "logsFolder": self.logs_folder, "lastUpdatedAt": self.last_updated_at}

    @classmethod
    def unmarshal(cls, data: dict) -> "LogInfo":
        return cls(
            created_at=data["createdAt"],
            logs_folder=data["logsFolder"],
            last_updated_at=data["lastUpdatedAt"],
        )


# -------------------------------------------------------------------------------------------------
#                                                                                      Test results
# -----------------------------------------------------------------------------------------------*/


@dataclass
class TestExecution:
    test_info: TestInfo
    deployment_uuid: str
    test_config: str
    test_nodes: List[str]  # Assuming test_nodes should be a list of node identifiers
    started_at: str
    finished_at: str
    error: str
    stopped: bool
    results: List[List[TestStepResult]]

    def marshal(self) -> dict:
        """Serialize the TestExecution object to a dictionary, handling Protobuf types."""
        return {
            "testInfo": MessageToDict(
                self.test_info, always_print_fields_with_no_presence=True, preserving_proto_field_name=True
            ),  # Serialize the Protobuf TestInfo object to a JSON string
            "deploymentUuid": self.deployment_uuid,
            "testConfig": self.test_config,
            "testNodes": self.test_nodes,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "error": self.error,
            "stopped": self.stopped,
            "results": [
                [
                    MessageToDict(step, always_print_fields_with_no_presence=True, preserving_proto_field_name=True)
                    for step in result_group
                ]
                for result_group in self.results
            ],  # Serialize the Protobuf TestInfo object to a JSON string
        }

    @classmethod
    def unmarshal(cls, data: dict) -> "TestExecution":
        """Deserialize a dictionary to a TestExecution object, handling Protobuf types."""
        test_info = TestInfo()
        ParseDict(data["testInfo"], test_info)  # Deserialize the dictionary back to a TestInfo object

        results = []
        for result_group in data["results"]:
            group = [TestStepResult() for _ in result_group]
            for result_dict, result_obj in zip(result_group, group):
                ParseDict(result_dict, result_obj)
            results.append(group)

        return cls(
            test_info=test_info,
            deployment_uuid=data["deploymentUuid"],
            test_config=data["testConfig"],
            test_nodes=data["testNodes"],
            started_at=data["startedAt"],
            finished_at=data["finishedAt"],
            error=data["error"],
            stopped=data["stopped"],
            results=results,
        )


@dataclass
class TestExecutionInfo:
    test_name: str
    uuid: str  # Unique identifier for this execution entry
    error: str
    uploaded: bool  # Has this been uploaded to CC
    created_at: str  # When this entry was initially added to the file system

    def marshal(self) -> dict:
        return {
            "testName": self.test_name,
            "uuid": self.uuid,
            "error": self.error,
            "uploaded": self.uploaded,
            "createdAt": self.created_at,
        }

    @classmethod
    def unmarshal(cls, data: dict) -> "TestExecutionInfo":
        return cls(
            test_name=data["testName"],
            uuid=data["uuid"],
            error=data["error"],
            uploaded=data["uploaded"],
            created_at=data["createdAt"],
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
            "createdAt": self.created_at,
            "lastUpdatedAt": self.last_updated_at,
            "currentDeployment": self.current_deployment,
            "deployments": [deployment.marshal() for deployment in self.deployments],
            "logs": [log.marshal() for log in self.logs],
            "executions": [execution.marshal() for execution in self.executions],
        }

    @classmethod
    def unmarshal(cls, data: dict) -> "ClusterInfo":
        # Unmarshall the lists independently first
        deployments = [DeploymentInfo.unmarshal(deployment) for deployment in data.get("deployments", [])]
        logs = [LogInfo.unmarshal(log) for log in data.get("logs", [])]
        executions = [TestExecutionInfo.unmarshal(execution) for execution in data.get("executions", [])]

        return cls(
            name=data["name"],
            type=ClusterType.from_string(data["type"]),
            uuid=data["uuid"],
            registered=data["registered"],
            created_at=data["createdAt"],
            last_updated_at=data["lastUpdatedAt"],
            current_deployment=data["currentDeployment"],
            deployments=deployments,
            logs=logs,
            executions=executions,
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

    def __init__(
        self,
        info: ClusterInfo,
        status: ClusterStatus,
        error: str,
        url: Optional[str],
        channel: Optional[grpc.Channel],
        stub: Optional[ClusterOperatorStub],
    ):
        self.info: ClusterInfo = info
        self.status: ClusterStatus = status
        self.error: str = error
        self.url: str = url
        self.channel: grpc.Channel = channel
        self.stub: ClusterOperatorStub = stub
