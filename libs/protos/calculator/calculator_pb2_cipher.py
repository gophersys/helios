# python_service_template.tmpl
from enum import Enum
from protos.calculator.calculator_pb2 import * 
from cipher import *

# -----------------------------------------------------------------------------------------------------
#                                                                                                 Types
# -----------------------------------------------------------------------------------------------------
CALCULATOR_SERVICE_ID = 1

class CalculatorRpc(Enum):
    AddIntegers = 1
    
class Calculator:
    def __init__(self, daemon:Cipher):
        self.daemon: Cipher = daemon
    # Server side handlers
    def AddIntegersHandler(self, request:AddIntegersRequest) -> Tuple[AddIntegersResponse, CipherRpcErr]:
        print("Default AddIntegers handler called")
        response: AddIntegersResponse = AddIntegersResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def AddIntegersRpc(self, info:CipherUnaryRpcUserInfo, request:AddIntegersRequest) -> Tuple[Optional[AddIntegersResponse], CipherRpcErr]:
        response: AddIntegersResponse = AddIntegersResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=CALCULATOR_SERVICE_ID,
            rpc_id=CalculatorRpc.AddIntegers.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error

# Calculator RPCs
calculator_service_rpcs = [
    CipherRpcInfo(
        id=CalculatorRpc.AddIntegers.value,
        type=CipherRpcType.UNARY,
        name="AddIntegers",
        handler=Calculator.AddIntegersHandler,
        request_info=CipherMessageInfo(AddIntegersRequest),
        response_info=CipherMessageInfo(AddIntegersResponse),
        supports_parallelism=True
    ),
]

# Calculator Service Definition
calculator_service_info = CipherServiceInfo(
    id=CALCULATOR_SERVICE_ID,
    name="Calculator",
    num_allowed_hops=1,
    rpcs=calculator_service_rpcs
)
