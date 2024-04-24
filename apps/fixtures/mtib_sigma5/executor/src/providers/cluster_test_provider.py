# Standard includes

# App includes
from config import conf
from src.tests.core import Test

# Protocol includes
from protos.cluster_test.cluster_test_pb2 import (
    HealthCheckRequest, HealthCheckResponse,
    ExecuteTestRequest, ExecuteTestResponse
)
from protos.cluster_operator.cluster_operator_pb2_grpc import ClusterOperatorServicer

class ClusterTestServicerProvider(ClusterOperatorServicer):
    # -------------------------------------------------------------------------------------------------
    #                                                                                 Pass Test Cluster
    # -----------------------------------------------------------------------------------------------*/
    def __init__(self, test:Test):
        self.test:Test = test

    # -------------------------------------------------------------------------------------------------
    #                                                                                       HealthCheck
    # -----------------------------------------------------------------------------------------------*/
    def HealthCheck(self, request:HealthCheckRequest, context):        
        return HealthCheckResponse()
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                    GetClusterInfo
    # -----------------------------------------------------------------------------------------------*/
    def ExecuteTest(self, request:ExecuteTestRequest, context):
        # First we confirm that the requested test Id matches the test we're serving
        if request.testId != self.test.info.id:
            pass 
        
        
