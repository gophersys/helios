# python_service_template.tmpl
from enum import Enum
from protos.test_case.test_case_pb2 import * 
from corekinect.cipher.cipher import *

# -----------------------------------------------------------------------------------------------------
#                                                                                                 Types
# -----------------------------------------------------------------------------------------------------
TESTCASERUNTIMESERVICE_SERVICE_ID = 1

class TestCaseRuntimeServiceRpc(Enum):
    HealthCheck = 1
    GetTestInfo = 2
    Run = 3
    Stop = 4
    GetAssets = 5
    GetAsset = 6
    
class TestCaseRuntimeService:
    def __init__(self, daemon:Cipher):
        self.daemon: Cipher = daemon
    # Server side handlers
    def HealthCheckHandler(self, request:Empty) -> Tuple[HealthCheckResponse, CipherRpcErr]:
        print("Default HealthCheck handler called")
        response: HealthCheckResponse = HealthCheckResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def HealthCheckRpc(self, info:CipherUnaryRpcUserInfo, request:Empty) -> Tuple[Optional[HealthCheckResponse], CipherRpcErr]:
        response: HealthCheckResponse = HealthCheckResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=TESTCASERUNTIMESERVICE_SERVICE_ID,
            rpc_id=TestCaseRuntimeServiceRpc.HealthCheck.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def GetTestInfoHandler(self, request:Empty) -> Tuple[GetTestInfoResponse, CipherRpcErr]:
        print("Default GetTestInfo handler called")
        response: GetTestInfoResponse = GetTestInfoResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def GetTestInfoRpc(self, info:CipherUnaryRpcUserInfo, request:Empty) -> Tuple[Optional[GetTestInfoResponse], CipherRpcErr]:
        response: GetTestInfoResponse = GetTestInfoResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=TESTCASERUNTIMESERVICE_SERVICE_ID,
            rpc_id=TestCaseRuntimeServiceRpc.GetTestInfo.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def RunHandler(self, request:RunRequest) -> Tuple[RunResponse, CipherRpcErr]:
        print("Default Run handler called")
        response: RunResponse = RunResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def RunRpc(self, info:CipherUnaryRpcUserInfo, request:RunRequest) -> Tuple[Optional[RunResponse], CipherRpcErr]:
        response: RunResponse = RunResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=TESTCASERUNTIMESERVICE_SERVICE_ID,
            rpc_id=TestCaseRuntimeServiceRpc.Run.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def StopHandler(self, request:StopRequest) -> Tuple[StopResponse, CipherRpcErr]:
        print("Default Stop handler called")
        response: StopResponse = StopResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def StopRpc(self, info:CipherUnaryRpcUserInfo, request:StopRequest) -> Tuple[Optional[StopResponse], CipherRpcErr]:
        response: StopResponse = StopResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=TESTCASERUNTIMESERVICE_SERVICE_ID,
            rpc_id=TestCaseRuntimeServiceRpc.Stop.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def GetAssetsHandler(self, request:Empty) -> Tuple[GetAssetsResponse, CipherRpcErr]:
        print("Default GetAssets handler called")
        response: GetAssetsResponse = GetAssetsResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def GetAssetsRpc(self, info:CipherUnaryRpcUserInfo, request:Empty) -> Tuple[Optional[GetAssetsResponse], CipherRpcErr]:
        response: GetAssetsResponse = GetAssetsResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=TESTCASERUNTIMESERVICE_SERVICE_ID,
            rpc_id=TestCaseRuntimeServiceRpc.GetAssets.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def GetAssetHandler(self, request:GetAssetRequest) -> Tuple[GetAssetRequest, CipherRpcErr]:
        print("Default GetAsset handler called")
        response: GetAssetRequest = GetAssetRequest()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def GetAssetRpc(self, info:CipherUnaryRpcUserInfo, request:GetAssetRequest) -> Tuple[Optional[GetAssetRequest], CipherRpcErr]:
        response: GetAssetRequest = GetAssetRequest()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=TESTCASERUNTIMESERVICE_SERVICE_ID,
            rpc_id=TestCaseRuntimeServiceRpc.GetAsset.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error

# TestCaseRuntimeService RPCs
testcaseruntimeservice_service_rpcs = [
    CipherRpcInfo(
        id=TestCaseRuntimeServiceRpc.HealthCheck.value,
        type=CipherRpcType.UNARY,
        name="HealthCheck",
        handler=TestCaseRuntimeService.HealthCheckHandler,
        request_info=CipherMessageInfo(Empty),
        response_info=CipherMessageInfo(HealthCheckResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=TestCaseRuntimeServiceRpc.GetTestInfo.value,
        type=CipherRpcType.UNARY,
        name="GetTestInfo",
        handler=TestCaseRuntimeService.GetTestInfoHandler,
        request_info=CipherMessageInfo(Empty),
        response_info=CipherMessageInfo(GetTestInfoResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=TestCaseRuntimeServiceRpc.Run.value,
        type=CipherRpcType.UNARY,
        name="Run",
        handler=TestCaseRuntimeService.RunHandler,
        request_info=CipherMessageInfo(RunRequest),
        response_info=CipherMessageInfo(RunResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=TestCaseRuntimeServiceRpc.Stop.value,
        type=CipherRpcType.UNARY,
        name="Stop",
        handler=TestCaseRuntimeService.StopHandler,
        request_info=CipherMessageInfo(StopRequest),
        response_info=CipherMessageInfo(StopResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=TestCaseRuntimeServiceRpc.GetAssets.value,
        type=CipherRpcType.UNARY,
        name="GetAssets",
        handler=TestCaseRuntimeService.GetAssetsHandler,
        request_info=CipherMessageInfo(Empty),
        response_info=CipherMessageInfo(GetAssetsResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=TestCaseRuntimeServiceRpc.GetAsset.value,
        type=CipherRpcType.UNARY,
        name="GetAsset",
        handler=TestCaseRuntimeService.GetAssetHandler,
        request_info=CipherMessageInfo(GetAssetRequest),
        response_info=CipherMessageInfo(GetAssetRequest),
        supports_parallelism=True
    ),
]

# TestCaseRuntimeService Service Definition
testcaseruntimeservice_service_info = CipherServiceInfo(
    id=TESTCASERUNTIMESERVICE_SERVICE_ID,
    name="TestCaseRuntimeService",
    num_allowed_hops=1,
    rpcs=testcaseruntimeservice_service_rpcs
)
