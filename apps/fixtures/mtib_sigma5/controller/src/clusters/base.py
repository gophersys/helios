from abc import ABC, abstractmethod
from typing import Tuple
from protos.mtib_controller.mtib_controller_pb2 import (
    HealthCheckRequest, HealthCheckResponse,
    ClusterInfo, GetClusterInfoRequest, GetClusterInfoResponse,
    RunnerInfo, HardwareInfo, SoftwareInfo
)

class BaseTestCluster(ABC):
    @abstractmethod
    def setup(self) -> Tuple[bool, str]:
        """
        Setup or initialize the test cluster.
        Returns a boolean indicating success.
        """
        pass

    @abstractmethod
    def get_cluster_metadata(self) -> ClusterInfo:
        """
        Fetches metadata about the test cluster.
        Returns a dictionary containing metadata such as runners, supported hardware, etc.
        """
        pass