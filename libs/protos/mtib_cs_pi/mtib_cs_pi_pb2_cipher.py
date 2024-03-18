# python_service_template.tmpl
from enum import Enum
from protos.mtib_cs_pi.mtib_cs_pi_pb2 import * 
from cipher import *

# -----------------------------------------------------------------------------------------------------
#                                                                                                 Types
# -----------------------------------------------------------------------------------------------------
MTIBCSPI_SERVICE_ID = 1

class MtibCsPiRpc(Enum):
    GpioConfig = 1
    GpioWrite = 2
    GpioRead = 3
    AdcRead = 4
    AdcReadAll = 5
    DutPowerEnable = 6
    DutChargePowerEnable = 7
    DutVoltageSet = 8
    DutCurrentRead = 9
    DutVoltageRead = 10
    DutPowerRead = 11
    AltimeterRead = 12
    AccelRead = 13
    AccelReadMaxForce = 14
    EepromRead = 15
    EepromWrite = 16
    ListFwFiles = 17
    UploadFwFile = 18
    DeleteFwFile = 19
    FlashHexFile = 20
    
class MtibCsPi:
    def __init__(self, daemon:Cipher):
        self.daemon: Cipher = daemon
    # Server side handlers
    def GpioConfigHandler(self, request:GpioConfigRequest) -> Tuple[GpioConfigResponse, CipherRpcErr]:
        print("Default GpioConfig handler called")
        response: GpioConfigResponse = GpioConfigResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def GpioConfigRpc(self, info:CipherUnaryRpcUserInfo, request:GpioConfigRequest) -> Tuple[Optional[GpioConfigResponse], CipherRpcErr]:
        response: GpioConfigResponse = GpioConfigResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.GpioConfig.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def GpioWriteHandler(self, request:GpioWriteRequest) -> Tuple[GpioWriteResponse, CipherRpcErr]:
        print("Default GpioWrite handler called")
        response: GpioWriteResponse = GpioWriteResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def GpioWriteRpc(self, info:CipherUnaryRpcUserInfo, request:GpioWriteRequest) -> Tuple[Optional[GpioWriteResponse], CipherRpcErr]:
        response: GpioWriteResponse = GpioWriteResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.GpioWrite.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def GpioReadHandler(self, request:GpioReadRequest) -> Tuple[GpioReadResponse, CipherRpcErr]:
        print("Default GpioRead handler called")
        response: GpioReadResponse = GpioReadResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def GpioReadRpc(self, info:CipherUnaryRpcUserInfo, request:GpioReadRequest) -> Tuple[Optional[GpioReadResponse], CipherRpcErr]:
        response: GpioReadResponse = GpioReadResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.GpioRead.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def AdcReadHandler(self, request:AdcReadRequest) -> Tuple[AdcReadResponse, CipherRpcErr]:
        print("Default AdcRead handler called")
        response: AdcReadResponse = AdcReadResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def AdcReadRpc(self, info:CipherUnaryRpcUserInfo, request:AdcReadRequest) -> Tuple[Optional[AdcReadResponse], CipherRpcErr]:
        response: AdcReadResponse = AdcReadResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.AdcRead.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def AdcReadAllHandler(self, request:AdcReadAllRequest) -> Tuple[AdcReadAllResponse, CipherRpcErr]:
        print("Default AdcReadAll handler called")
        response: AdcReadAllResponse = AdcReadAllResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def AdcReadAllRpc(self, info:CipherUnaryRpcUserInfo, request:AdcReadAllRequest) -> Tuple[Optional[AdcReadAllResponse], CipherRpcErr]:
        response: AdcReadAllResponse = AdcReadAllResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.AdcReadAll.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def DutPowerEnableHandler(self, request:DutPowerEnableRequest) -> Tuple[DutPowerEnableResponse, CipherRpcErr]:
        print("Default DutPowerEnable handler called")
        response: DutPowerEnableResponse = DutPowerEnableResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def DutPowerEnableRpc(self, info:CipherUnaryRpcUserInfo, request:DutPowerEnableRequest) -> Tuple[Optional[DutPowerEnableResponse], CipherRpcErr]:
        response: DutPowerEnableResponse = DutPowerEnableResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.DutPowerEnable.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def DutChargePowerEnableHandler(self, request:DutPowerEnableRequest) -> Tuple[DutPowerEnableResponse, CipherRpcErr]:
        print("Default DutChargePowerEnable handler called")
        response: DutPowerEnableResponse = DutPowerEnableResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def DutChargePowerEnableRpc(self, info:CipherUnaryRpcUserInfo, request:DutPowerEnableRequest) -> Tuple[Optional[DutPowerEnableResponse], CipherRpcErr]:
        response: DutPowerEnableResponse = DutPowerEnableResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.DutChargePowerEnable.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def DutVoltageSetHandler(self, request:DutVoltageSetRequest) -> Tuple[DutVoltageSetResponse, CipherRpcErr]:
        print("Default DutVoltageSet handler called")
        response: DutVoltageSetResponse = DutVoltageSetResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def DutVoltageSetRpc(self, info:CipherUnaryRpcUserInfo, request:DutVoltageSetRequest) -> Tuple[Optional[DutVoltageSetResponse], CipherRpcErr]:
        response: DutVoltageSetResponse = DutVoltageSetResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.DutVoltageSet.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def DutCurrentReadHandler(self, request:DutCurrentReadRequest) -> Tuple[DutCurrentReadResponse, CipherRpcErr]:
        print("Default DutCurrentRead handler called")
        response: DutCurrentReadResponse = DutCurrentReadResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def DutCurrentReadRpc(self, info:CipherUnaryRpcUserInfo, request:DutCurrentReadRequest) -> Tuple[Optional[DutCurrentReadResponse], CipherRpcErr]:
        response: DutCurrentReadResponse = DutCurrentReadResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.DutCurrentRead.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def DutVoltageReadHandler(self, request:DutVoltageReadRequest) -> Tuple[DutVoltageReadResponse, CipherRpcErr]:
        print("Default DutVoltageRead handler called")
        response: DutVoltageReadResponse = DutVoltageReadResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def DutVoltageReadRpc(self, info:CipherUnaryRpcUserInfo, request:DutVoltageReadRequest) -> Tuple[Optional[DutVoltageReadResponse], CipherRpcErr]:
        response: DutVoltageReadResponse = DutVoltageReadResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.DutVoltageRead.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def DutPowerReadHandler(self, request:DutPowerReadRequest) -> Tuple[DutPowerReadResponse, CipherRpcErr]:
        print("Default DutPowerRead handler called")
        response: DutPowerReadResponse = DutPowerReadResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def DutPowerReadRpc(self, info:CipherUnaryRpcUserInfo, request:DutPowerReadRequest) -> Tuple[Optional[DutPowerReadResponse], CipherRpcErr]:
        response: DutPowerReadResponse = DutPowerReadResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.DutPowerRead.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def AltimeterReadHandler(self, request:AltimeterReadRequest) -> Tuple[AltimeterReadResponse, CipherRpcErr]:
        print("Default AltimeterRead handler called")
        response: AltimeterReadResponse = AltimeterReadResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def AltimeterReadRpc(self, info:CipherUnaryRpcUserInfo, request:AltimeterReadRequest) -> Tuple[Optional[AltimeterReadResponse], CipherRpcErr]:
        response: AltimeterReadResponse = AltimeterReadResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.AltimeterRead.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def AccelReadHandler(self, request:AccelReadRequest) -> Tuple[AccelReadResponse, CipherRpcErr]:
        print("Default AccelRead handler called")
        response: AccelReadResponse = AccelReadResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def AccelReadRpc(self, info:CipherUnaryRpcUserInfo, request:AccelReadRequest) -> Tuple[Optional[AccelReadResponse], CipherRpcErr]:
        response: AccelReadResponse = AccelReadResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.AccelRead.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def AccelReadMaxForceHandler(self, request:AccelReadMaxRequest) -> Tuple[AccelReadMaxResponse, CipherRpcErr]:
        print("Default AccelReadMaxForce handler called")
        response: AccelReadMaxResponse = AccelReadMaxResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def AccelReadMaxForceRpc(self, info:CipherUnaryRpcUserInfo, request:AccelReadMaxRequest) -> Tuple[Optional[AccelReadMaxResponse], CipherRpcErr]:
        response: AccelReadMaxResponse = AccelReadMaxResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.AccelReadMaxForce.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def EepromReadHandler(self, request:EepromReadRequest) -> Tuple[EepromReadResponse, CipherRpcErr]:
        print("Default EepromRead handler called")
        response: EepromReadResponse = EepromReadResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def EepromReadRpc(self, info:CipherUnaryRpcUserInfo, request:EepromReadRequest) -> Tuple[Optional[EepromReadResponse], CipherRpcErr]:
        response: EepromReadResponse = EepromReadResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.EepromRead.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def EepromWriteHandler(self, request:EepromWriteRequest) -> Tuple[EepromWriteResponse, CipherRpcErr]:
        print("Default EepromWrite handler called")
        response: EepromWriteResponse = EepromWriteResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def EepromWriteRpc(self, info:CipherUnaryRpcUserInfo, request:EepromWriteRequest) -> Tuple[Optional[EepromWriteResponse], CipherRpcErr]:
        response: EepromWriteResponse = EepromWriteResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.EepromWrite.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def ListFwFilesHandler(self, request:ListFwFilesRequest) -> Tuple[ListFwFilesResponse, CipherRpcErr]:
        print("Default ListFwFiles handler called")
        response: ListFwFilesResponse = ListFwFilesResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def ListFwFilesRpc(self, info:CipherUnaryRpcUserInfo, request:ListFwFilesRequest) -> Tuple[Optional[ListFwFilesResponse], CipherRpcErr]:
        response: ListFwFilesResponse = ListFwFilesResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.ListFwFiles.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def UploadFwFileHandler(self, request:UploadFwFileRequest) -> Tuple[UploadFwFileResponse, CipherRpcErr]:
        print("Default UploadFwFile handler called")
        response: UploadFwFileResponse = UploadFwFileResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def UploadFwFileRpc(self, info:CipherUnaryRpcUserInfo, request:UploadFwFileRequest) -> Tuple[Optional[UploadFwFileResponse], CipherRpcErr]:
        response: UploadFwFileResponse = UploadFwFileResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.UploadFwFile.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def DeleteFwFileHandler(self, request:DeleteFwFileRequest) -> Tuple[DeleteFwFileResponse, CipherRpcErr]:
        print("Default DeleteFwFile handler called")
        response: DeleteFwFileResponse = DeleteFwFileResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def DeleteFwFileRpc(self, info:CipherUnaryRpcUserInfo, request:DeleteFwFileRequest) -> Tuple[Optional[DeleteFwFileResponse], CipherRpcErr]:
        response: DeleteFwFileResponse = DeleteFwFileResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.DeleteFwFile.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def FlashHexFileHandler(self, request:FlashHexFileRequest) -> Tuple[FlashHexFileResponse, CipherRpcErr]:
        print("Default FlashHexFile handler called")
        response: FlashHexFileResponse = FlashHexFileResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def FlashHexFileRpc(self, info:CipherUnaryRpcUserInfo, request:FlashHexFileRequest) -> Tuple[Optional[FlashHexFileResponse], CipherRpcErr]:
        response: FlashHexFileResponse = FlashHexFileResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBCSPI_SERVICE_ID,
            rpc_id=MtibCsPiRpc.FlashHexFile.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error

# MtibCsPi RPCs
mtibcspi_service_rpcs = [
    CipherRpcInfo(
        id=MtibCsPiRpc.GpioConfig.value,
        type=CipherRpcType.UNARY,
        name="GpioConfig",
        handler=MtibCsPi.GpioConfigHandler,
        request_info=CipherMessageInfo(GpioConfigRequest),
        response_info=CipherMessageInfo(GpioConfigResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibCsPiRpc.GpioWrite.value,
        type=CipherRpcType.UNARY,
        name="GpioWrite",
        handler=MtibCsPi.GpioWriteHandler,
        request_info=CipherMessageInfo(GpioWriteRequest),
        response_info=CipherMessageInfo(GpioWriteResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibCsPiRpc.GpioRead.value,
        type=CipherRpcType.UNARY,
        name="GpioRead",
        handler=MtibCsPi.GpioReadHandler,
        request_info=CipherMessageInfo(GpioReadRequest),
        response_info=CipherMessageInfo(GpioReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibCsPiRpc.AdcRead.value,
        type=CipherRpcType.UNARY,
        name="AdcRead",
        handler=MtibCsPi.AdcReadHandler,
        request_info=CipherMessageInfo(AdcReadRequest),
        response_info=CipherMessageInfo(AdcReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibCsPiRpc.AdcReadAll.value,
        type=CipherRpcType.UNARY,
        name="AdcReadAll",
        handler=MtibCsPi.AdcReadAllHandler,
        request_info=CipherMessageInfo(AdcReadAllRequest),
        response_info=CipherMessageInfo(AdcReadAllResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibCsPiRpc.DutPowerEnable.value,
        type=CipherRpcType.UNARY,
        name="DutPowerEnable",
        handler=MtibCsPi.DutPowerEnableHandler,
        request_info=CipherMessageInfo(DutPowerEnableRequest),
        response_info=CipherMessageInfo(DutPowerEnableResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibCsPiRpc.DutChargePowerEnable.value,
        type=CipherRpcType.UNARY,
        name="DutChargePowerEnable",
        handler=MtibCsPi.DutChargePowerEnableHandler,
        request_info=CipherMessageInfo(DutPowerEnableRequest),
        response_info=CipherMessageInfo(DutPowerEnableResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibCsPiRpc.DutVoltageSet.value,
        type=CipherRpcType.UNARY,
        name="DutVoltageSet",
        handler=MtibCsPi.DutVoltageSetHandler,
        request_info=CipherMessageInfo(DutVoltageSetRequest),
        response_info=CipherMessageInfo(DutVoltageSetResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibCsPiRpc.DutCurrentRead.value,
        type=CipherRpcType.UNARY,
        name="DutCurrentRead",
        handler=MtibCsPi.DutCurrentReadHandler,
        request_info=CipherMessageInfo(DutCurrentReadRequest),
        response_info=CipherMessageInfo(DutCurrentReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibCsPiRpc.DutVoltageRead.value,
        type=CipherRpcType.UNARY,
        name="DutVoltageRead",
        handler=MtibCsPi.DutVoltageReadHandler,
        request_info=CipherMessageInfo(DutVoltageReadRequest),
        response_info=CipherMessageInfo(DutVoltageReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibCsPiRpc.DutPowerRead.value,
        type=CipherRpcType.UNARY,
        name="DutPowerRead",
        handler=MtibCsPi.DutPowerReadHandler,
        request_info=CipherMessageInfo(DutPowerReadRequest),
        response_info=CipherMessageInfo(DutPowerReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibCsPiRpc.AltimeterRead.value,
        type=CipherRpcType.UNARY,
        name="AltimeterRead",
        handler=MtibCsPi.AltimeterReadHandler,
        request_info=CipherMessageInfo(AltimeterReadRequest),
        response_info=CipherMessageInfo(AltimeterReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibCsPiRpc.AccelRead.value,
        type=CipherRpcType.UNARY,
        name="AccelRead",
        handler=MtibCsPi.AccelReadHandler,
        request_info=CipherMessageInfo(AccelReadRequest),
        response_info=CipherMessageInfo(AccelReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibCsPiRpc.AccelReadMaxForce.value,
        type=CipherRpcType.UNARY,
        name="AccelReadMaxForce",
        handler=MtibCsPi.AccelReadMaxForceHandler,
        request_info=CipherMessageInfo(AccelReadMaxRequest),
        response_info=CipherMessageInfo(AccelReadMaxResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibCsPiRpc.EepromRead.value,
        type=CipherRpcType.UNARY,
        name="EepromRead",
        handler=MtibCsPi.EepromReadHandler,
        request_info=CipherMessageInfo(EepromReadRequest),
        response_info=CipherMessageInfo(EepromReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibCsPiRpc.EepromWrite.value,
        type=CipherRpcType.UNARY,
        name="EepromWrite",
        handler=MtibCsPi.EepromWriteHandler,
        request_info=CipherMessageInfo(EepromWriteRequest),
        response_info=CipherMessageInfo(EepromWriteResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibCsPiRpc.ListFwFiles.value,
        type=CipherRpcType.UNARY,
        name="ListFwFiles",
        handler=MtibCsPi.ListFwFilesHandler,
        request_info=CipherMessageInfo(ListFwFilesRequest),
        response_info=CipherMessageInfo(ListFwFilesResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibCsPiRpc.UploadFwFile.value,
        type=CipherRpcType.UNARY,
        name="UploadFwFile",
        handler=MtibCsPi.UploadFwFileHandler,
        request_info=CipherMessageInfo(UploadFwFileRequest),
        response_info=CipherMessageInfo(UploadFwFileResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibCsPiRpc.DeleteFwFile.value,
        type=CipherRpcType.UNARY,
        name="DeleteFwFile",
        handler=MtibCsPi.DeleteFwFileHandler,
        request_info=CipherMessageInfo(DeleteFwFileRequest),
        response_info=CipherMessageInfo(DeleteFwFileResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibCsPiRpc.FlashHexFile.value,
        type=CipherRpcType.UNARY,
        name="FlashHexFile",
        handler=MtibCsPi.FlashHexFileHandler,
        request_info=CipherMessageInfo(FlashHexFileRequest),
        response_info=CipherMessageInfo(FlashHexFileResponse),
        supports_parallelism=True
    ),
]

# MtibCsPi Service Definition
mtibcspi_service_info = CipherServiceInfo(
    id=MTIBCSPI_SERVICE_ID,
    name="MtibCsPi",
    num_allowed_hops=1,
    rpcs=mtibcspi_service_rpcs
)
