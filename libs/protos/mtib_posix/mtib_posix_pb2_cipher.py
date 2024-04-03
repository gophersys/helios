# python_service_template.tmpl
from enum import Enum
from protos.mtib_posix.mtib_posix_pb2 import * 
from cipher import *

# -----------------------------------------------------------------------------------------------------
#                                                                                                 Types
# -----------------------------------------------------------------------------------------------------
MTIBPOSIX_SERVICE_ID = 1

class MtibPosixRpc(Enum):
    HealthCheck = 1
    GpioConfig = 2
    GpioWrite = 3
    GpioRead = 4
    AdcRead = 5
    AdcReadAll = 6
    DutPowerEnable = 7
    DutChargePowerEnable = 8
    DutVoltageSet = 9
    DutCurrentRead = 10
    DutVoltageRead = 11
    DutPowerRead = 12
    AltimeterRead = 13
    AccelRead = 14
    AccelReadMaxForce = 15
    EepromRead = 16
    EepromWrite = 17
    ListFwFiles = 18
    UploadFwFile = 19
    DeleteFwFile = 20
    FlashHexFile = 21
    
class MtibPosix:
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.HealthCheck.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.GpioConfig.value,
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.GpioWrite.value,
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.GpioRead.value,
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.AdcRead.value,
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.AdcReadAll.value,
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.DutPowerEnable.value,
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.DutChargePowerEnable.value,
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.DutVoltageSet.value,
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.DutCurrentRead.value,
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.DutVoltageRead.value,
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.DutPowerRead.value,
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.AltimeterRead.value,
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.AccelRead.value,
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.AccelReadMaxForce.value,
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.EepromRead.value,
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.EepromWrite.value,
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.ListFwFiles.value,
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.UploadFwFile.value,
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.DeleteFwFile.value,
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
            service_id=MTIBPOSIX_SERVICE_ID,
            rpc_id=MtibPosixRpc.FlashHexFile.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error

# MtibPosix RPCs
mtibposix_service_rpcs = [
    CipherRpcInfo(
        id=MtibPosixRpc.HealthCheck.value,
        type=CipherRpcType.UNARY,
        name="HealthCheck",
        handler=MtibPosix.HealthCheckHandler,
        request_info=CipherMessageInfo(HealthCheckRequest),
        response_info=CipherMessageInfo(HealthCheckResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.GpioConfig.value,
        type=CipherRpcType.UNARY,
        name="GpioConfig",
        handler=MtibPosix.GpioConfigHandler,
        request_info=CipherMessageInfo(GpioConfigRequest),
        response_info=CipherMessageInfo(GpioConfigResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.GpioWrite.value,
        type=CipherRpcType.UNARY,
        name="GpioWrite",
        handler=MtibPosix.GpioWriteHandler,
        request_info=CipherMessageInfo(GpioWriteRequest),
        response_info=CipherMessageInfo(GpioWriteResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.GpioRead.value,
        type=CipherRpcType.UNARY,
        name="GpioRead",
        handler=MtibPosix.GpioReadHandler,
        request_info=CipherMessageInfo(GpioReadRequest),
        response_info=CipherMessageInfo(GpioReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.AdcRead.value,
        type=CipherRpcType.UNARY,
        name="AdcRead",
        handler=MtibPosix.AdcReadHandler,
        request_info=CipherMessageInfo(AdcReadRequest),
        response_info=CipherMessageInfo(AdcReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.AdcReadAll.value,
        type=CipherRpcType.UNARY,
        name="AdcReadAll",
        handler=MtibPosix.AdcReadAllHandler,
        request_info=CipherMessageInfo(AdcReadAllRequest),
        response_info=CipherMessageInfo(AdcReadAllResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.DutPowerEnable.value,
        type=CipherRpcType.UNARY,
        name="DutPowerEnable",
        handler=MtibPosix.DutPowerEnableHandler,
        request_info=CipherMessageInfo(DutPowerEnableRequest),
        response_info=CipherMessageInfo(DutPowerEnableResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.DutChargePowerEnable.value,
        type=CipherRpcType.UNARY,
        name="DutChargePowerEnable",
        handler=MtibPosix.DutChargePowerEnableHandler,
        request_info=CipherMessageInfo(DutPowerEnableRequest),
        response_info=CipherMessageInfo(DutPowerEnableResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.DutVoltageSet.value,
        type=CipherRpcType.UNARY,
        name="DutVoltageSet",
        handler=MtibPosix.DutVoltageSetHandler,
        request_info=CipherMessageInfo(DutVoltageSetRequest),
        response_info=CipherMessageInfo(DutVoltageSetResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.DutCurrentRead.value,
        type=CipherRpcType.UNARY,
        name="DutCurrentRead",
        handler=MtibPosix.DutCurrentReadHandler,
        request_info=CipherMessageInfo(DutCurrentReadRequest),
        response_info=CipherMessageInfo(DutCurrentReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.DutVoltageRead.value,
        type=CipherRpcType.UNARY,
        name="DutVoltageRead",
        handler=MtibPosix.DutVoltageReadHandler,
        request_info=CipherMessageInfo(DutVoltageReadRequest),
        response_info=CipherMessageInfo(DutVoltageReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.DutPowerRead.value,
        type=CipherRpcType.UNARY,
        name="DutPowerRead",
        handler=MtibPosix.DutPowerReadHandler,
        request_info=CipherMessageInfo(DutPowerReadRequest),
        response_info=CipherMessageInfo(DutPowerReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.AltimeterRead.value,
        type=CipherRpcType.UNARY,
        name="AltimeterRead",
        handler=MtibPosix.AltimeterReadHandler,
        request_info=CipherMessageInfo(AltimeterReadRequest),
        response_info=CipherMessageInfo(AltimeterReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.AccelRead.value,
        type=CipherRpcType.UNARY,
        name="AccelRead",
        handler=MtibPosix.AccelReadHandler,
        request_info=CipherMessageInfo(AccelReadRequest),
        response_info=CipherMessageInfo(AccelReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.AccelReadMaxForce.value,
        type=CipherRpcType.UNARY,
        name="AccelReadMaxForce",
        handler=MtibPosix.AccelReadMaxForceHandler,
        request_info=CipherMessageInfo(AccelReadMaxRequest),
        response_info=CipherMessageInfo(AccelReadMaxResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.EepromRead.value,
        type=CipherRpcType.UNARY,
        name="EepromRead",
        handler=MtibPosix.EepromReadHandler,
        request_info=CipherMessageInfo(EepromReadRequest),
        response_info=CipherMessageInfo(EepromReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.EepromWrite.value,
        type=CipherRpcType.UNARY,
        name="EepromWrite",
        handler=MtibPosix.EepromWriteHandler,
        request_info=CipherMessageInfo(EepromWriteRequest),
        response_info=CipherMessageInfo(EepromWriteResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.ListFwFiles.value,
        type=CipherRpcType.UNARY,
        name="ListFwFiles",
        handler=MtibPosix.ListFwFilesHandler,
        request_info=CipherMessageInfo(ListFwFilesRequest),
        response_info=CipherMessageInfo(ListFwFilesResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.UploadFwFile.value,
        type=CipherRpcType.UNARY,
        name="UploadFwFile",
        handler=MtibPosix.UploadFwFileHandler,
        request_info=CipherMessageInfo(UploadFwFileRequest),
        response_info=CipherMessageInfo(UploadFwFileResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.DeleteFwFile.value,
        type=CipherRpcType.UNARY,
        name="DeleteFwFile",
        handler=MtibPosix.DeleteFwFileHandler,
        request_info=CipherMessageInfo(DeleteFwFileRequest),
        response_info=CipherMessageInfo(DeleteFwFileResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibPosixRpc.FlashHexFile.value,
        type=CipherRpcType.UNARY,
        name="FlashHexFile",
        handler=MtibPosix.FlashHexFileHandler,
        request_info=CipherMessageInfo(FlashHexFileRequest),
        response_info=CipherMessageInfo(FlashHexFileResponse),
        supports_parallelism=True
    ),
]

# MtibPosix Service Definition
mtibposix_service_info = CipherServiceInfo(
    id=MTIBPOSIX_SERVICE_ID,
    name="MtibPosix",
    num_allowed_hops=1,
    rpcs=mtibposix_service_rpcs
)
