# python_service_template.tmpl
from enum import Enum
from protos.cluster_test.cluster_test_pb2 import * 
from cipher import *

# -----------------------------------------------------------------------------------------------------
#                                                                                                 Types
# -----------------------------------------------------------------------------------------------------
CLUSTERTEST_SERVICE_ID = 1

class ClusterTestRpc(Enum):
    HealthCheck = 1
    Execute = 2
    
class ClusterTest:
    def __init__(self, daemon:Cipher):
        self.daemon: Cipher = daemon
    # Server side handlers
    def HealthCheckHandler(self, request:HealthCheckRequest) -> Tuple[HealthCheckResponse, CipherRpcErr]:
        print("Default HealthCheck handler called")
        response: HealthCheckResponse = HealthCheckResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def HealthCheckRpc(self, info:CipherUnaryRpcUserInfo, request:HealthCheckRequest) -> Tuple[Optional[HealthCheckResponse], CipherRpcErr]:
        response: HealthCheckResponse = HealthCheckResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=CLUSTERTEST_SERVICE_ID,
            rpc_id=ClusterTestRpc.HealthCheck.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def ExecuteHandler(self, request:ExecuteRequest) -> Tuple[ExecuteResponse, CipherRpcErr]:
        print("Default Execute handler called")
        response: ExecuteResponse = ExecuteResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def ExecuteRpc(self, info:CipherUnaryRpcUserInfo, request:ExecuteRequest) -> Tuple[Optional[ExecuteResponse], CipherRpcErr]:
        response: ExecuteResponse = ExecuteResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=CLUSTERTEST_SERVICE_ID,
            rpc_id=ClusterTestRpc.Execute.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error

# ClusterTest RPCs
clustertest_service_rpcs = [
    CipherRpcInfo(
        id=ClusterTestRpc.HealthCheck.value,
        type=CipherRpcType.UNARY,
        name="HealthCheck",
        handler=ClusterTest.HealthCheckHandler,
        request_info=CipherMessageInfo(HealthCheckRequest),
        response_info=CipherMessageInfo(HealthCheckResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=ClusterTestRpc.Execute.value,
        type=CipherRpcType.UNARY,
        name="Execute",
        handler=ClusterTest.ExecuteHandler,
        request_info=CipherMessageInfo(ExecuteRequest),
        response_info=CipherMessageInfo(ExecuteResponse),
        supports_parallelism=True
    ),
]

# ClusterTest Service Definition
clustertest_service_info = CipherServiceInfo(
    id=CLUSTERTEST_SERVICE_ID,
    name="ClusterTest",
    num_allowed_hops=1,
    rpcs=clustertest_service_rpcs
)
