# python_service_template.tmpl
from enum import Enum
from protos.mtib_controller.mtib_controller_pb2 import * 
from cipher import *

# -----------------------------------------------------------------------------------------------------
#                                                                                                 Types
# -----------------------------------------------------------------------------------------------------
MTIBCONTROLLER_SERVICE_ID = 1

class MtibControllerRpc(Enum):
    HealthCheck = 1
    GetClusterInfo = 2
    Reset = 3
    ListTests = 4
    ExecuteTest = 5
    
class MtibController:
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
            service_id=MTIBCONTROLLER_SERVICE_ID,
            rpc_id=MtibControllerRpc.HealthCheck.value,
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
            service_id=MTIBCONTROLLER_SERVICE_ID,
            rpc_id=MtibControllerRpc.GetClusterInfo.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def ResetHandler(self, request:ResetRequest) -> Tuple[ResetResponse, CipherRpcErr]:
        print("Default Reset handler called")
        response: ResetResponse = ResetResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def ResetRpc(self, info:CipherUnaryRpcUserInfo, request:ResetRequest) -> Tuple[Optional[ResetResponse], CipherRpcErr]:
        response: ResetResponse = ResetResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCONTROLLER_SERVICE_ID,
            rpc_id=MtibControllerRpc.Reset.value,
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
            service_id=MTIBCONTROLLER_SERVICE_ID,
            rpc_id=MtibControllerRpc.ListTests.value,
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
            service_id=MTIBCONTROLLER_SERVICE_ID,
            rpc_id=MtibControllerRpc.ExecuteTest.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error

# MtibController RPCs
mtibcontroller_service_rpcs = [
    CipherRpcInfo(
        id=MtibControllerRpc.HealthCheck.value,
        type=CipherRpcType.UNARY,
        name="HealthCheck",
        handler=MtibController.HealthCheckHandler,
        request_info=CipherMessageInfo(HealthCheckRequest),
        response_info=CipherMessageInfo(HealthCheckResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibControllerRpc.GetClusterInfo.value,
        type=CipherRpcType.UNARY,
        name="GetClusterInfo",
        handler=MtibController.GetClusterInfoHandler,
        request_info=CipherMessageInfo(GetClusterInfoRequest),
        response_info=CipherMessageInfo(GetClusterInfoResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibControllerRpc.Reset.value,
        type=CipherRpcType.UNARY,
        name="Reset",
        handler=MtibController.ResetHandler,
        request_info=CipherMessageInfo(ResetRequest),
        response_info=CipherMessageInfo(ResetResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibControllerRpc.ListTests.value,
        type=CipherRpcType.UNARY,
        name="ListTests",
        handler=MtibController.ListTestsHandler,
        request_info=CipherMessageInfo(ListTestsRequest),
        response_info=CipherMessageInfo(ListTestsResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibControllerRpc.ExecuteTest.value,
        type=CipherRpcType.UNARY,
        name="ExecuteTest",
        handler=MtibController.ExecuteTestHandler,
        request_info=CipherMessageInfo(ExecuteTestRequest),
        response_info=CipherMessageInfo(ExecuteTestResponse),
        supports_parallelism=True
    ),
]

# MtibController Service Definition
mtibcontroller_service_info = CipherServiceInfo(
    id=MTIBCONTROLLER_SERVICE_ID,
    name="MtibController",
    num_allowed_hops=1,
    rpcs=mtibcontroller_service_rpcs
)
