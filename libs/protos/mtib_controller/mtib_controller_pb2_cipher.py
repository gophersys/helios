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
]

# MtibController Service Definition
mtibcontroller_service_info = CipherServiceInfo(
    id=MTIBCONTROLLER_SERVICE_ID,
    name="MtibController",
    num_allowed_hops=1,
    rpcs=mtibcontroller_service_rpcs
)
