# python_service_template.tmpl
from enum import Enum
from protos.mtib_runner.mtib_runner_pb2 import * 
from cipher import *

# -----------------------------------------------------------------------------------------------------
#                                                                                                 Types
# -----------------------------------------------------------------------------------------------------
MTIBRUNNER_SERVICE_ID = 1

class MtibRunnerRpc(Enum):
    HealthCheck = 1
    GetRunnerInfo = 2
    Reset = 3
    GpioConfig = 4
    GpioWrite = 5
    GpioRead = 6
    AdcRead = 7
    AdcReadAll = 8
    DutPowerEnable = 9
    DutChargePowerEnable = 10
    DutVoltageSet = 11
    DutCurrentRead = 12
    DutVoltageRead = 13
    DutPowerRead = 14
    AltimeterRead = 15
    AccelRead = 16
    AccelReadMaxForce = 17
    EepromRead = 18
    EepromWrite = 19
    ListFwFiles = 20
    UploadFwFile = 21
    DeleteFwFile = 22
    FlashHexFile = 23
    
class MtibRunner:
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.HealthCheck.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def GetRunnerInfoHandler(self, request:GetRunnerInfoRequest) -> Tuple[GetRunnerInfoResponse, CipherRpcErr]:
        print("Default GetRunnerInfo handler called")
        response: GetRunnerInfoResponse = GetRunnerInfoResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def GetRunnerInfoRpc(self, info:CipherUnaryRpcUserInfo, request:GetRunnerInfoRequest) -> Tuple[Optional[GetRunnerInfoResponse], CipherRpcErr]:
        response: GetRunnerInfoResponse = GetRunnerInfoResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.GetRunnerInfo.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.Reset.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.GpioConfig.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.GpioWrite.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.GpioRead.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.AdcRead.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.AdcReadAll.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.DutPowerEnable.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.DutChargePowerEnable.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.DutVoltageSet.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.DutCurrentRead.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.DutVoltageRead.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.DutPowerRead.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.AltimeterRead.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.AccelRead.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.AccelReadMaxForce.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.EepromRead.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.EepromWrite.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.ListFwFiles.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.UploadFwFile.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.DeleteFwFile.value,
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
            service_id=MTIBRUNNER_SERVICE_ID,
            rpc_id=MtibRunnerRpc.FlashHexFile.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error

# MtibRunner RPCs
mtibrunner_service_rpcs = [
    CipherRpcInfo(
        id=MtibRunnerRpc.HealthCheck.value,
        type=CipherRpcType.UNARY,
        name="HealthCheck",
        handler=MtibRunner.HealthCheckHandler,
        request_info=CipherMessageInfo(HealthCheckRequest),
        response_info=CipherMessageInfo(HealthCheckResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.GetRunnerInfo.value,
        type=CipherRpcType.UNARY,
        name="GetRunnerInfo",
        handler=MtibRunner.GetRunnerInfoHandler,
        request_info=CipherMessageInfo(GetRunnerInfoRequest),
        response_info=CipherMessageInfo(GetRunnerInfoResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.Reset.value,
        type=CipherRpcType.UNARY,
        name="Reset",
        handler=MtibRunner.ResetHandler,
        request_info=CipherMessageInfo(ResetRequest),
        response_info=CipherMessageInfo(ResetResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.GpioConfig.value,
        type=CipherRpcType.UNARY,
        name="GpioConfig",
        handler=MtibRunner.GpioConfigHandler,
        request_info=CipherMessageInfo(GpioConfigRequest),
        response_info=CipherMessageInfo(GpioConfigResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.GpioWrite.value,
        type=CipherRpcType.UNARY,
        name="GpioWrite",
        handler=MtibRunner.GpioWriteHandler,
        request_info=CipherMessageInfo(GpioWriteRequest),
        response_info=CipherMessageInfo(GpioWriteResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.GpioRead.value,
        type=CipherRpcType.UNARY,
        name="GpioRead",
        handler=MtibRunner.GpioReadHandler,
        request_info=CipherMessageInfo(GpioReadRequest),
        response_info=CipherMessageInfo(GpioReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.AdcRead.value,
        type=CipherRpcType.UNARY,
        name="AdcRead",
        handler=MtibRunner.AdcReadHandler,
        request_info=CipherMessageInfo(AdcReadRequest),
        response_info=CipherMessageInfo(AdcReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.AdcReadAll.value,
        type=CipherRpcType.UNARY,
        name="AdcReadAll",
        handler=MtibRunner.AdcReadAllHandler,
        request_info=CipherMessageInfo(AdcReadAllRequest),
        response_info=CipherMessageInfo(AdcReadAllResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.DutPowerEnable.value,
        type=CipherRpcType.UNARY,
        name="DutPowerEnable",
        handler=MtibRunner.DutPowerEnableHandler,
        request_info=CipherMessageInfo(DutPowerEnableRequest),
        response_info=CipherMessageInfo(DutPowerEnableResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.DutChargePowerEnable.value,
        type=CipherRpcType.UNARY,
        name="DutChargePowerEnable",
        handler=MtibRunner.DutChargePowerEnableHandler,
        request_info=CipherMessageInfo(DutPowerEnableRequest),
        response_info=CipherMessageInfo(DutPowerEnableResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.DutVoltageSet.value,
        type=CipherRpcType.UNARY,
        name="DutVoltageSet",
        handler=MtibRunner.DutVoltageSetHandler,
        request_info=CipherMessageInfo(DutVoltageSetRequest),
        response_info=CipherMessageInfo(DutVoltageSetResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.DutCurrentRead.value,
        type=CipherRpcType.UNARY,
        name="DutCurrentRead",
        handler=MtibRunner.DutCurrentReadHandler,
        request_info=CipherMessageInfo(DutCurrentReadRequest),
        response_info=CipherMessageInfo(DutCurrentReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.DutVoltageRead.value,
        type=CipherRpcType.UNARY,
        name="DutVoltageRead",
        handler=MtibRunner.DutVoltageReadHandler,
        request_info=CipherMessageInfo(DutVoltageReadRequest),
        response_info=CipherMessageInfo(DutVoltageReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.DutPowerRead.value,
        type=CipherRpcType.UNARY,
        name="DutPowerRead",
        handler=MtibRunner.DutPowerReadHandler,
        request_info=CipherMessageInfo(DutPowerReadRequest),
        response_info=CipherMessageInfo(DutPowerReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.AltimeterRead.value,
        type=CipherRpcType.UNARY,
        name="AltimeterRead",
        handler=MtibRunner.AltimeterReadHandler,
        request_info=CipherMessageInfo(AltimeterReadRequest),
        response_info=CipherMessageInfo(AltimeterReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.AccelRead.value,
        type=CipherRpcType.UNARY,
        name="AccelRead",
        handler=MtibRunner.AccelReadHandler,
        request_info=CipherMessageInfo(AccelReadRequest),
        response_info=CipherMessageInfo(AccelReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.AccelReadMaxForce.value,
        type=CipherRpcType.UNARY,
        name="AccelReadMaxForce",
        handler=MtibRunner.AccelReadMaxForceHandler,
        request_info=CipherMessageInfo(AccelReadMaxRequest),
        response_info=CipherMessageInfo(AccelReadMaxResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.EepromRead.value,
        type=CipherRpcType.UNARY,
        name="EepromRead",
        handler=MtibRunner.EepromReadHandler,
        request_info=CipherMessageInfo(EepromReadRequest),
        response_info=CipherMessageInfo(EepromReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.EepromWrite.value,
        type=CipherRpcType.UNARY,
        name="EepromWrite",
        handler=MtibRunner.EepromWriteHandler,
        request_info=CipherMessageInfo(EepromWriteRequest),
        response_info=CipherMessageInfo(EepromWriteResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.ListFwFiles.value,
        type=CipherRpcType.UNARY,
        name="ListFwFiles",
        handler=MtibRunner.ListFwFilesHandler,
        request_info=CipherMessageInfo(ListFwFilesRequest),
        response_info=CipherMessageInfo(ListFwFilesResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.UploadFwFile.value,
        type=CipherRpcType.UNARY,
        name="UploadFwFile",
        handler=MtibRunner.UploadFwFileHandler,
        request_info=CipherMessageInfo(UploadFwFileRequest),
        response_info=CipherMessageInfo(UploadFwFileResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.DeleteFwFile.value,
        type=CipherRpcType.UNARY,
        name="DeleteFwFile",
        handler=MtibRunner.DeleteFwFileHandler,
        request_info=CipherMessageInfo(DeleteFwFileRequest),
        response_info=CipherMessageInfo(DeleteFwFileResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerRpc.FlashHexFile.value,
        type=CipherRpcType.UNARY,
        name="FlashHexFile",
        handler=MtibRunner.FlashHexFileHandler,
        request_info=CipherMessageInfo(FlashHexFileRequest),
        response_info=CipherMessageInfo(FlashHexFileResponse),
        supports_parallelism=True
    ),
]

# MtibRunner Service Definition
mtibrunner_service_info = CipherServiceInfo(
    id=MTIBRUNNER_SERVICE_ID,
    name="MtibRunner",
    num_allowed_hops=1,
    rpcs=mtibrunner_service_rpcs
)
