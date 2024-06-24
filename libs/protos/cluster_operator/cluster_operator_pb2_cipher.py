# python_service_template.tmpl
from enum import Enum
from protos.cluster_operator.cluster_operator_pb2 import * 
from corekinect.cipher.cipher import *

# -----------------------------------------------------------------------------------------------------
#                                                                                                 Types
# -----------------------------------------------------------------------------------------------------
CLUSTEROPERATOR_SERVICE_ID = 1

class ClusterOperatorRpc(Enum):
    HealthCheck = 1
    GetClusterInfo = 2
    GetDeploymentInfo = 3
    ListTests = 4
    ExecuteTest = 5
    StopTest = 6
    RegisterTest = 7
    
class ClusterOperator:
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
            service_id=CLUSTEROPERATOR_SERVICE_ID,
            rpc_id=ClusterOperatorRpc.HealthCheck.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def GetClusterInfoHandler(self, request:GetClusterInfoRequest) -> Tuple[GetClusterInfoResponse, CipherRpcErr]:
        print("Default GetClusterInfo handler called")
        response: GetClusterInfoResponse = GetClusterInfoResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def GetClusterInfoRpc(self, info:CipherUnaryRpcUserInfo, request:GetClusterInfoRequest) -> Tuple[Optional[GetClusterInfoResponse], CipherRpcErr]:
        response: GetClusterInfoResponse = GetClusterInfoResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=CLUSTEROPERATOR_SERVICE_ID,
            rpc_id=ClusterOperatorRpc.GetClusterInfo.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def GetDeploymentInfoHandler(self, request:GetDeploymentInfoRequest) -> Tuple[GetDeploymentInfoResponse, CipherRpcErr]:
        print("Default GetDeploymentInfo handler called")
        response: GetDeploymentInfoResponse = GetDeploymentInfoResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def GetDeploymentInfoRpc(self, info:CipherUnaryRpcUserInfo, request:GetDeploymentInfoRequest) -> Tuple[Optional[GetDeploymentInfoResponse], CipherRpcErr]:
        response: GetDeploymentInfoResponse = GetDeploymentInfoResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=CLUSTEROPERATOR_SERVICE_ID,
            rpc_id=ClusterOperatorRpc.GetDeploymentInfo.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def ListTestsHandler(self, request:ListTestsRequest) -> Tuple[ListTestsResponse, CipherRpcErr]:
        print("Default ListTests handler called")
        response: ListTestsResponse = ListTestsResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def ListTestsRpc(self, info:CipherUnaryRpcUserInfo, request:ListTestsRequest) -> Tuple[Optional[ListTestsResponse], CipherRpcErr]:
        response: ListTestsResponse = ListTestsResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=CLUSTEROPERATOR_SERVICE_ID,
            rpc_id=ClusterOperatorRpc.ListTests.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def ExecuteTestHandler(self, request:ExecuteTestRequest) -> Tuple[ExecuteTestResponse, CipherRpcErr]:
        print("Default ExecuteTest handler called")
        response: ExecuteTestResponse = ExecuteTestResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def ExecuteTestRpc(self, info:CipherUnaryRpcUserInfo, request:ExecuteTestRequest) -> Tuple[Optional[ExecuteTestResponse], CipherRpcErr]:
        response: ExecuteTestResponse = ExecuteTestResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=CLUSTEROPERATOR_SERVICE_ID,
            rpc_id=ClusterOperatorRpc.ExecuteTest.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def StopTestHandler(self, request:StopTestRequest) -> Tuple[StopTestResponse, CipherRpcErr]:
        print("Default StopTest handler called")
        response: StopTestResponse = StopTestResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def StopTestRpc(self, info:CipherUnaryRpcUserInfo, request:StopTestRequest) -> Tuple[Optional[StopTestResponse], CipherRpcErr]:
        response: StopTestResponse = StopTestResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=CLUSTEROPERATOR_SERVICE_ID,
            rpc_id=ClusterOperatorRpc.StopTest.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def RegisterTestHandler(self, request:RegisterTestRequest) -> Tuple[RegisterTestResponse, CipherRpcErr]:
        print("Default RegisterTest handler called")
        response: RegisterTestResponse = RegisterTestResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def RegisterTestRpc(self, info:CipherUnaryRpcUserInfo, request:RegisterTestRequest) -> Tuple[Optional[RegisterTestResponse], CipherRpcErr]:
        response: RegisterTestResponse = RegisterTestResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=CLUSTEROPERATOR_SERVICE_ID,
            rpc_id=ClusterOperatorRpc.RegisterTest.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error

# ClusterOperator RPCs
clusteroperator_service_rpcs = [
    CipherRpcInfo(
        id=ClusterOperatorRpc.HealthCheck.value,
        type=CipherRpcType.UNARY,
        name="HealthCheck",
        handler=ClusterOperator.HealthCheckHandler,
        request_info=CipherMessageInfo(HealthCheckRequest),
        response_info=CipherMessageInfo(HealthCheckResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=ClusterOperatorRpc.GetClusterInfo.value,
        type=CipherRpcType.UNARY,
        name="GetClusterInfo",
        handler=ClusterOperator.GetClusterInfoHandler,
        request_info=CipherMessageInfo(GetClusterInfoRequest),
        response_info=CipherMessageInfo(GetClusterInfoResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=ClusterOperatorRpc.GetDeploymentInfo.value,
        type=CipherRpcType.UNARY,
        name="GetDeploymentInfo",
        handler=ClusterOperator.GetDeploymentInfoHandler,
        request_info=CipherMessageInfo(GetDeploymentInfoRequest),
        response_info=CipherMessageInfo(GetDeploymentInfoResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=ClusterOperatorRpc.ListTests.value,
        type=CipherRpcType.UNARY,
        name="ListTests",
        handler=ClusterOperator.ListTestsHandler,
        request_info=CipherMessageInfo(ListTestsRequest),
        response_info=CipherMessageInfo(ListTestsResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=ClusterOperatorRpc.ExecuteTest.value,
        type=CipherRpcType.UNARY,
        name="ExecuteTest",
        handler=ClusterOperator.ExecuteTestHandler,
        request_info=CipherMessageInfo(ExecuteTestRequest),
        response_info=CipherMessageInfo(ExecuteTestResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=ClusterOperatorRpc.StopTest.value,
        type=CipherRpcType.UNARY,
        name="StopTest",
        handler=ClusterOperator.StopTestHandler,
        request_info=CipherMessageInfo(StopTestRequest),
        response_info=CipherMessageInfo(StopTestResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=ClusterOperatorRpc.RegisterTest.value,
        type=CipherRpcType.UNARY,
        name="RegisterTest",
        handler=ClusterOperator.RegisterTestHandler,
        request_info=CipherMessageInfo(RegisterTestRequest),
        response_info=CipherMessageInfo(RegisterTestResponse),
        supports_parallelism=True
    ),
]

# ClusterOperator Service Definition
clusteroperator_service_info = CipherServiceInfo(
    id=CLUSTEROPERATOR_SERVICE_ID,
    name="ClusterOperator",
    num_allowed_hops=1,
    rpcs=clusteroperator_service_rpcs
)
