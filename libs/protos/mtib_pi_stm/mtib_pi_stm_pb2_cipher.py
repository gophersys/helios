# python_service_template.tmpl
from enum import Enum
from protos.mtib_pi_stm.mtib_pi_stm_pb2 import * 
from cipher import *

# -----------------------------------------------------------------------------------------------------
#                                                                                                 Types
# -----------------------------------------------------------------------------------------------------
MTIBPISTM_SERVICE_ID = 1

class MtibPiStmRpc(Enum):
    GpioConfigurePin = 1
    GpioSetPin = 2
    GpioReadPin = 3
    AdcReadChannel = 4
    AdcReadAllChannels = 5
    DutEnablePower = 6
    DutEnableCharger = 7
    DutSetOutputVoltage = 8
    Ina219ReadCurrent = 9
    Ina219ReadVoltage = 10
    Ina219ReadPower = 11
    Bmp390ReadValues = 12
    Lis2de12ReadValues = 13
    Lis2de12ReadMaxForce = 14
    EepromReadFromMem = 15
    EepromWriteToMem = 16
    SigmaToPiMessage = 17
    PiToSigmaMessage = 18
    
class MtibPiStm:
    def __init__(self, daemon:Cipher):
        self.daemon: Cipher = daemon
    # Server side handlers
    def GpioConfigurePinHandler(self, request:GpioConfigurePinRequest) -> Tuple[GpioConfigurePinResponse, CipherRpcErr]:
        print("Default GpioConfigurePin handler called")
        response: GpioConfigurePinResponse = GpioConfigurePinResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def GpioConfigurePinRpc(self, info:CipherUnaryRpcUserInfo, request:GpioConfigurePinRequest) -> Tuple[Optional[GpioConfigurePinResponse], CipherRpcErr]:
        response: GpioConfigurePinResponse = GpioConfigurePinResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBPISTM_SERVICE_ID,
            rpc_id=MtibPiStmRpc.GpioConfigurePin.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def GpioSetPinHandler(self, request:GpioSetPinRequest) -> Tuple[GpioSetPinResponse, CipherRpcErr]:
        print("Default GpioSetPin handler called")
        response: GpioSetPinResponse = GpioSetPinResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def GpioSetPinRpc(self, info:CipherUnaryRpcUserInfo, request:GpioSetPinRequest) -> Tuple[Optional[GpioSetPinResponse], CipherRpcErr]:
        response: GpioSetPinResponse = GpioSetPinResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBPISTM_SERVICE_ID,
            rpc_id=MtibPiStmRpc.GpioSetPin.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def GpioReadPinHandler(self, request:GpioReadPinRequest) -> Tuple[GpioReadPinResponse, CipherRpcErr]:
        print("Default GpioReadPin handler called")
        response: GpioReadPinResponse = GpioReadPinResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def GpioReadPinRpc(self, info:CipherUnaryRpcUserInfo, request:GpioReadPinRequest) -> Tuple[Optional[GpioReadPinResponse], CipherRpcErr]:
        response: GpioReadPinResponse = GpioReadPinResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBPISTM_SERVICE_ID,
            rpc_id=MtibPiStmRpc.GpioReadPin.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def AdcReadChannelHandler(self, request:AdcReadChannelRequest) -> Tuple[AdcReadChannelResponse, CipherRpcErr]:
        print("Default AdcReadChannel handler called")
        response: AdcReadChannelResponse = AdcReadChannelResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def AdcReadChannelRpc(self, info:CipherUnaryRpcUserInfo, request:AdcReadChannelRequest) -> Tuple[Optional[AdcReadChannelResponse], CipherRpcErr]:
        response: AdcReadChannelResponse = AdcReadChannelResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBPISTM_SERVICE_ID,
            rpc_id=MtibPiStmRpc.AdcReadChannel.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def AdcReadAllChannelsHandler(self, request:AdcReadAllChannelsRequest) -> Tuple[AdcReadAllChannelsResponse, CipherRpcErr]:
        print("Default AdcReadAllChannels handler called")
        response: AdcReadAllChannelsResponse = AdcReadAllChannelsResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def AdcReadAllChannelsRpc(self, info:CipherUnaryRpcUserInfo, request:AdcReadAllChannelsRequest) -> Tuple[Optional[AdcReadAllChannelsResponse], CipherRpcErr]:
        response: AdcReadAllChannelsResponse = AdcReadAllChannelsResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBPISTM_SERVICE_ID,
            rpc_id=MtibPiStmRpc.AdcReadAllChannels.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def DutEnablePowerHandler(self, request:DutEnablePowerRequest) -> Tuple[DutEnablePowerResponse, CipherRpcErr]:
        print("Default DutEnablePower handler called")
        response: DutEnablePowerResponse = DutEnablePowerResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def DutEnablePowerRpc(self, info:CipherUnaryRpcUserInfo, request:DutEnablePowerRequest) -> Tuple[Optional[DutEnablePowerResponse], CipherRpcErr]:
        response: DutEnablePowerResponse = DutEnablePowerResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBPISTM_SERVICE_ID,
            rpc_id=MtibPiStmRpc.DutEnablePower.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def DutEnableChargerHandler(self, request:DutEnableChargerRequest) -> Tuple[DutEnableChargerResponse, CipherRpcErr]:
        print("Default DutEnableCharger handler called")
        response: DutEnableChargerResponse = DutEnableChargerResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def DutEnableChargerRpc(self, info:CipherUnaryRpcUserInfo, request:DutEnableChargerRequest) -> Tuple[Optional[DutEnableChargerResponse], CipherRpcErr]:
        response: DutEnableChargerResponse = DutEnableChargerResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBPISTM_SERVICE_ID,
            rpc_id=MtibPiStmRpc.DutEnableCharger.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def DutSetOutputVoltageHandler(self, request:DutSetOutputVoltageRequest) -> Tuple[DutSetOutputVoltageResponse, CipherRpcErr]:
        print("Default DutSetOutputVoltage handler called")
        response: DutSetOutputVoltageResponse = DutSetOutputVoltageResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def DutSetOutputVoltageRpc(self, info:CipherUnaryRpcUserInfo, request:DutSetOutputVoltageRequest) -> Tuple[Optional[DutSetOutputVoltageResponse], CipherRpcErr]:
        response: DutSetOutputVoltageResponse = DutSetOutputVoltageResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBPISTM_SERVICE_ID,
            rpc_id=MtibPiStmRpc.DutSetOutputVoltage.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def Ina219ReadCurrentHandler(self, request:Ina219ReadCurrentRequest) -> Tuple[Ina219ReadCurrentResponse, CipherRpcErr]:
        print("Default Ina219ReadCurrent handler called")
        response: Ina219ReadCurrentResponse = Ina219ReadCurrentResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def Ina219ReadCurrentRpc(self, info:CipherUnaryRpcUserInfo, request:Ina219ReadCurrentRequest) -> Tuple[Optional[Ina219ReadCurrentResponse], CipherRpcErr]:
        response: Ina219ReadCurrentResponse = Ina219ReadCurrentResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBPISTM_SERVICE_ID,
            rpc_id=MtibPiStmRpc.Ina219ReadCurrent.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def Ina219ReadVoltageHandler(self, request:Ina219ReadVoltageRequest) -> Tuple[Ina219ReadVoltageResponse, CipherRpcErr]:
        print("Default Ina219ReadVoltage handler called")
        response: Ina219ReadVoltageResponse = Ina219ReadVoltageResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def Ina219ReadVoltageRpc(self, info:CipherUnaryRpcUserInfo, request:Ina219ReadVoltageRequest) -> Tuple[Optional[Ina219ReadVoltageResponse], CipherRpcErr]:
        response: Ina219ReadVoltageResponse = Ina219ReadVoltageResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBPISTM_SERVICE_ID,
            rpc_id=MtibPiStmRpc.Ina219ReadVoltage.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def Ina219ReadPowerHandler(self, request:Ina219ReadPowerRequest) -> Tuple[Ina219ReadPowerResponse, CipherRpcErr]:
        print("Default Ina219ReadPower handler called")
        response: Ina219ReadPowerResponse = Ina219ReadPowerResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def Ina219ReadPowerRpc(self, info:CipherUnaryRpcUserInfo, request:Ina219ReadPowerRequest) -> Tuple[Optional[Ina219ReadPowerResponse], CipherRpcErr]:
        response: Ina219ReadPowerResponse = Ina219ReadPowerResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBPISTM_SERVICE_ID,
            rpc_id=MtibPiStmRpc.Ina219ReadPower.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def Bmp390ReadValuesHandler(self, request:Bmp390ReadValuesRequest) -> Tuple[Bmp390ReadValuesResponse, CipherRpcErr]:
        print("Default Bmp390ReadValues handler called")
        response: Bmp390ReadValuesResponse = Bmp390ReadValuesResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def Bmp390ReadValuesRpc(self, info:CipherUnaryRpcUserInfo, request:Bmp390ReadValuesRequest) -> Tuple[Optional[Bmp390ReadValuesResponse], CipherRpcErr]:
        response: Bmp390ReadValuesResponse = Bmp390ReadValuesResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBPISTM_SERVICE_ID,
            rpc_id=MtibPiStmRpc.Bmp390ReadValues.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def Lis2de12ReadValuesHandler(self, request:Lis2de12ReadValuesRequest) -> Tuple[Lis2de12ReadValuesResponse, CipherRpcErr]:
        print("Default Lis2de12ReadValues handler called")
        response: Lis2de12ReadValuesResponse = Lis2de12ReadValuesResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def Lis2de12ReadValuesRpc(self, info:CipherUnaryRpcUserInfo, request:Lis2de12ReadValuesRequest) -> Tuple[Optional[Lis2de12ReadValuesResponse], CipherRpcErr]:
        response: Lis2de12ReadValuesResponse = Lis2de12ReadValuesResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBPISTM_SERVICE_ID,
            rpc_id=MtibPiStmRpc.Lis2de12ReadValues.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def Lis2de12ReadMaxForceHandler(self, request:Lis2de12ReadMaxForceRequest) -> Tuple[Lis2de12ReadMaxForceResponse, CipherRpcErr]:
        print("Default Lis2de12ReadMaxForce handler called")
        response: Lis2de12ReadMaxForceResponse = Lis2de12ReadMaxForceResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def Lis2de12ReadMaxForceRpc(self, info:CipherUnaryRpcUserInfo, request:Lis2de12ReadMaxForceRequest) -> Tuple[Optional[Lis2de12ReadMaxForceResponse], CipherRpcErr]:
        response: Lis2de12ReadMaxForceResponse = Lis2de12ReadMaxForceResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBPISTM_SERVICE_ID,
            rpc_id=MtibPiStmRpc.Lis2de12ReadMaxForce.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def EepromReadFromMemHandler(self, request:EepromReadFromMemRequest) -> Tuple[EepromReadFromMemResponse, CipherRpcErr]:
        print("Default EepromReadFromMem handler called")
        response: EepromReadFromMemResponse = EepromReadFromMemResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def EepromReadFromMemRpc(self, info:CipherUnaryRpcUserInfo, request:EepromReadFromMemRequest) -> Tuple[Optional[EepromReadFromMemResponse], CipherRpcErr]:
        response: EepromReadFromMemResponse = EepromReadFromMemResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBPISTM_SERVICE_ID,
            rpc_id=MtibPiStmRpc.EepromReadFromMem.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def EepromWriteToMemHandler(self, request:EepromWriteToMemRequest) -> Tuple[EepromWriteToMemResponse, CipherRpcErr]:
        print("Default EepromWriteToMem handler called")
        response: EepromWriteToMemResponse = EepromWriteToMemResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def EepromWriteToMemRpc(self, info:CipherUnaryRpcUserInfo, request:EepromWriteToMemRequest) -> Tuple[Optional[EepromWriteToMemResponse], CipherRpcErr]:
        response: EepromWriteToMemResponse = EepromWriteToMemResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBPISTM_SERVICE_ID,
            rpc_id=MtibPiStmRpc.EepromWriteToMem.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def SigmaToPiMessageHandler(self, request:UartMessageRequest) -> Tuple[UartMessageResponse, CipherRpcErr]:
        print("Default SigmaToPiMessage handler called")
        response: UartMessageResponse = UartMessageResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def SigmaToPiMessageRpc(self, info:CipherUnaryRpcUserInfo, request:UartMessageRequest) -> Tuple[Optional[UartMessageResponse], CipherRpcErr]:
        response: UartMessageResponse = UartMessageResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBPISTM_SERVICE_ID,
            rpc_id=MtibPiStmRpc.SigmaToPiMessage.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def PiToSigmaMessageHandler(self, request:UartMessageRequest) -> Tuple[UartMessageResponse, CipherRpcErr]:
        print("Default PiToSigmaMessage handler called")
        response: UartMessageResponse = UartMessageResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def PiToSigmaMessageRpc(self, info:CipherUnaryRpcUserInfo, request:UartMessageRequest) -> Tuple[Optional[UartMessageResponse], CipherRpcErr]:
        response: UartMessageResponse = UartMessageResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBPISTM_SERVICE_ID,
            rpc_id=MtibPiStmRpc.PiToSigmaMessage.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error

# MtibPiStm RPCs
mtibpistm_service_rpcs = [
    CipherRpcInfo(
        id=MtibPiStmRpc.GpioConfigurePin.value,
        type=CipherRpcType.UNARY,
        name="GpioConfigurePin",
        handler=MtibPiStm.GpioConfigurePinHandler,
        request_info=CipherMessageInfo(GpioConfigurePinRequest),
        response_info=CipherMessageInfo(GpioConfigurePinResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPiStmRpc.GpioSetPin.value,
        type=CipherRpcType.UNARY,
        name="GpioSetPin",
        handler=MtibPiStm.GpioSetPinHandler,
        request_info=CipherMessageInfo(GpioSetPinRequest),
        response_info=CipherMessageInfo(GpioSetPinResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPiStmRpc.GpioReadPin.value,
        type=CipherRpcType.UNARY,
        name="GpioReadPin",
        handler=MtibPiStm.GpioReadPinHandler,
        request_info=CipherMessageInfo(GpioReadPinRequest),
        response_info=CipherMessageInfo(GpioReadPinResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPiStmRpc.AdcReadChannel.value,
        type=CipherRpcType.UNARY,
        name="AdcReadChannel",
        handler=MtibPiStm.AdcReadChannelHandler,
        request_info=CipherMessageInfo(AdcReadChannelRequest),
        response_info=CipherMessageInfo(AdcReadChannelResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPiStmRpc.AdcReadAllChannels.value,
        type=CipherRpcType.UNARY,
        name="AdcReadAllChannels",
        handler=MtibPiStm.AdcReadAllChannelsHandler,
        request_info=CipherMessageInfo(AdcReadAllChannelsRequest),
        response_info=CipherMessageInfo(AdcReadAllChannelsResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPiStmRpc.DutEnablePower.value,
        type=CipherRpcType.UNARY,
        name="DutEnablePower",
        handler=MtibPiStm.DutEnablePowerHandler,
        request_info=CipherMessageInfo(DutEnablePowerRequest),
        response_info=CipherMessageInfo(DutEnablePowerResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPiStmRpc.DutEnableCharger.value,
        type=CipherRpcType.UNARY,
        name="DutEnableCharger",
        handler=MtibPiStm.DutEnableChargerHandler,
        request_info=CipherMessageInfo(DutEnableChargerRequest),
        response_info=CipherMessageInfo(DutEnableChargerResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPiStmRpc.DutSetOutputVoltage.value,
        type=CipherRpcType.UNARY,
        name="DutSetOutputVoltage",
        handler=MtibPiStm.DutSetOutputVoltageHandler,
        request_info=CipherMessageInfo(DutSetOutputVoltageRequest),
        response_info=CipherMessageInfo(DutSetOutputVoltageResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPiStmRpc.Ina219ReadCurrent.value,
        type=CipherRpcType.UNARY,
        name="Ina219ReadCurrent",
        handler=MtibPiStm.Ina219ReadCurrentHandler,
        request_info=CipherMessageInfo(Ina219ReadCurrentRequest),
        response_info=CipherMessageInfo(Ina219ReadCurrentResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPiStmRpc.Ina219ReadVoltage.value,
        type=CipherRpcType.UNARY,
        name="Ina219ReadVoltage",
        handler=MtibPiStm.Ina219ReadVoltageHandler,
        request_info=CipherMessageInfo(Ina219ReadVoltageRequest),
        response_info=CipherMessageInfo(Ina219ReadVoltageResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPiStmRpc.Ina219ReadPower.value,
        type=CipherRpcType.UNARY,
        name="Ina219ReadPower",
        handler=MtibPiStm.Ina219ReadPowerHandler,
        request_info=CipherMessageInfo(Ina219ReadPowerRequest),
        response_info=CipherMessageInfo(Ina219ReadPowerResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPiStmRpc.Bmp390ReadValues.value,
        type=CipherRpcType.UNARY,
        name="Bmp390ReadValues",
        handler=MtibPiStm.Bmp390ReadValuesHandler,
        request_info=CipherMessageInfo(Bmp390ReadValuesRequest),
        response_info=CipherMessageInfo(Bmp390ReadValuesResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPiStmRpc.Lis2de12ReadValues.value,
        type=CipherRpcType.UNARY,
        name="Lis2de12ReadValues",
        handler=MtibPiStm.Lis2de12ReadValuesHandler,
        request_info=CipherMessageInfo(Lis2de12ReadValuesRequest),
        response_info=CipherMessageInfo(Lis2de12ReadValuesResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPiStmRpc.Lis2de12ReadMaxForce.value,
        type=CipherRpcType.UNARY,
        name="Lis2de12ReadMaxForce",
        handler=MtibPiStm.Lis2de12ReadMaxForceHandler,
        request_info=CipherMessageInfo(Lis2de12ReadMaxForceRequest),
        response_info=CipherMessageInfo(Lis2de12ReadMaxForceResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPiStmRpc.EepromReadFromMem.value,
        type=CipherRpcType.UNARY,
        name="EepromReadFromMem",
        handler=MtibPiStm.EepromReadFromMemHandler,
        request_info=CipherMessageInfo(EepromReadFromMemRequest),
        response_info=CipherMessageInfo(EepromReadFromMemResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPiStmRpc.EepromWriteToMem.value,
        type=CipherRpcType.UNARY,
        name="EepromWriteToMem",
        handler=MtibPiStm.EepromWriteToMemHandler,
        request_info=CipherMessageInfo(EepromWriteToMemRequest),
        response_info=CipherMessageInfo(EepromWriteToMemResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPiStmRpc.SigmaToPiMessage.value,
        type=CipherRpcType.UNARY,
        name="SigmaToPiMessage",
        handler=MtibPiStm.SigmaToPiMessageHandler,
        request_info=CipherMessageInfo(UartMessageRequest),
        response_info=CipherMessageInfo(UartMessageResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPiStmRpc.PiToSigmaMessage.value,
        type=CipherRpcType.UNARY,
        name="PiToSigmaMessage",
        handler=MtibPiStm.PiToSigmaMessageHandler,
        request_info=CipherMessageInfo(UartMessageRequest),
        response_info=CipherMessageInfo(UartMessageResponse),
        supports_parallelism=True
    ),
]

# MtibPiStm Service Definition
mtibpistm_service_info = CipherServiceInfo(
    id=MTIBPISTM_SERVICE_ID,
    name="MtibPiStm",
    num_allowed_hops=1,
    rpcs=mtibpistm_service_rpcs
)
