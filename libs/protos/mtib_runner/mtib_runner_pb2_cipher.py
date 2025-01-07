# python_service_template.tmpl
from enum import Enum
from protos.mtib_runner.mtib_runner_pb2 import * 
from corekinect.cipher.cipher import *

# -----------------------------------------------------------------------------------------------------
#                                                                                                 Types
# -----------------------------------------------------------------------------------------------------
MTIBRUNNERV1_SERVICE_ID = 1

class MtibRunnerV1Rpc(Enum):
    HealthCheck = 1
    GetRunnerInfo = 2
    GpioConfig = 3
    GpioWrite = 4
    GpioRead = 5
    AdcRead = 6
    AdcReadAll = 7
    DutPowerEnable = 8
    DutPowerDisable = 9
    DutChargePowerEnable = 10
    DutChargePowerDisable = 11
    DutPowerRead = 12
    AltimeterRead = 13
    AccelRead = 14
    GetMotionStatus = 15
    MotionHome = 16
    MotionTrigger = 17
    MotionContinuous = 18
    MotionStop = 19
    ListFwFiles = 20
    UploadFwFile = 21
    DeleteFwFile = 22
    FlashFwFile = 23
    UartStream = 24
    
class MtibRunnerV1:
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
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.HealthCheck.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def GetRunnerInfoHandler(self, request:Empty) -> Tuple[GetRunnerInfoResponse, CipherRpcErr]:
        print("Default GetRunnerInfo handler called")
        response: GetRunnerInfoResponse = GetRunnerInfoResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def GetRunnerInfoRpc(self, info:CipherUnaryRpcUserInfo, request:Empty) -> Tuple[Optional[GetRunnerInfoResponse], CipherRpcErr]:
        response: GetRunnerInfoResponse = GetRunnerInfoResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.GetRunnerInfo.value,
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
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.GpioConfig.value,
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
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.GpioWrite.value,
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
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.GpioRead.value,
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
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.AdcRead.value,
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
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.AdcReadAll.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def DutPowerEnableHandler(self, request:DutPowerRequest) -> Tuple[DutPowerResponse, CipherRpcErr]:
        print("Default DutPowerEnable handler called")
        response: DutPowerResponse = DutPowerResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def DutPowerEnableRpc(self, info:CipherUnaryRpcUserInfo, request:DutPowerRequest) -> Tuple[Optional[DutPowerResponse], CipherRpcErr]:
        response: DutPowerResponse = DutPowerResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.DutPowerEnable.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def DutPowerDisableHandler(self, request:Empty) -> Tuple[DutPowerResponse, CipherRpcErr]:
        print("Default DutPowerDisable handler called")
        response: DutPowerResponse = DutPowerResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def DutPowerDisableRpc(self, info:CipherUnaryRpcUserInfo, request:Empty) -> Tuple[Optional[DutPowerResponse], CipherRpcErr]:
        response: DutPowerResponse = DutPowerResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.DutPowerDisable.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def DutChargePowerEnableHandler(self, request:DutPowerRequest) -> Tuple[DutPowerResponse, CipherRpcErr]:
        print("Default DutChargePowerEnable handler called")
        response: DutPowerResponse = DutPowerResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def DutChargePowerEnableRpc(self, info:CipherUnaryRpcUserInfo, request:DutPowerRequest) -> Tuple[Optional[DutPowerResponse], CipherRpcErr]:
        response: DutPowerResponse = DutPowerResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.DutChargePowerEnable.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def DutChargePowerDisableHandler(self, request:Empty) -> Tuple[DutPowerResponse, CipherRpcErr]:
        print("Default DutChargePowerDisable handler called")
        response: DutPowerResponse = DutPowerResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def DutChargePowerDisableRpc(self, info:CipherUnaryRpcUserInfo, request:Empty) -> Tuple[Optional[DutPowerResponse], CipherRpcErr]:
        response: DutPowerResponse = DutPowerResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.DutChargePowerDisable.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def DutPowerReadHandler(self, request:Empty) -> Tuple[DutPowerReadResponse, CipherRpcErr]:
        print("Default DutPowerRead handler called")
        response: DutPowerReadResponse = DutPowerReadResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def DutPowerReadRpc(self, info:CipherUnaryRpcUserInfo, request:Empty) -> Tuple[Optional[DutPowerReadResponse], CipherRpcErr]:
        response: DutPowerReadResponse = DutPowerReadResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.DutPowerRead.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def AltimeterReadHandler(self, request:Empty) -> Tuple[AltimeterReadResponse, CipherRpcErr]:
        print("Default AltimeterRead handler called")
        response: AltimeterReadResponse = AltimeterReadResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def AltimeterReadRpc(self, info:CipherUnaryRpcUserInfo, request:Empty) -> Tuple[Optional[AltimeterReadResponse], CipherRpcErr]:
        response: AltimeterReadResponse = AltimeterReadResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.AltimeterRead.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def AccelReadHandler(self, request:Empty) -> Tuple[AccelReadResponse, CipherRpcErr]:
        print("Default AccelRead handler called")
        response: AccelReadResponse = AccelReadResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def AccelReadRpc(self, info:CipherUnaryRpcUserInfo, request:Empty) -> Tuple[Optional[AccelReadResponse], CipherRpcErr]:
        response: AccelReadResponse = AccelReadResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.AccelRead.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def GetMotionStatusHandler(self, request:Empty) -> Tuple[GetMotionStatusResponse, CipherRpcErr]:
        print("Default GetMotionStatus handler called")
        response: GetMotionStatusResponse = GetMotionStatusResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def GetMotionStatusRpc(self, info:CipherUnaryRpcUserInfo, request:Empty) -> Tuple[Optional[GetMotionStatusResponse], CipherRpcErr]:
        response: GetMotionStatusResponse = GetMotionStatusResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.GetMotionStatus.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def MotionHomeHandler(self, request:Empty) -> Tuple[MotionHomeResponse, CipherRpcErr]:
        print("Default MotionHome handler called")
        response: MotionHomeResponse = MotionHomeResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def MotionHomeRpc(self, info:CipherUnaryRpcUserInfo, request:Empty) -> Tuple[Optional[MotionHomeResponse], CipherRpcErr]:
        response: MotionHomeResponse = MotionHomeResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.MotionHome.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def MotionTriggerHandler(self, request:MotionTriggerRequest) -> Tuple[MotionTriggerResponse, CipherRpcErr]:
        print("Default MotionTrigger handler called")
        response: MotionTriggerResponse = MotionTriggerResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def MotionTriggerRpc(self, info:CipherUnaryRpcUserInfo, request:MotionTriggerRequest) -> Tuple[Optional[MotionTriggerResponse], CipherRpcErr]:
        response: MotionTriggerResponse = MotionTriggerResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.MotionTrigger.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def MotionContinuousHandler(self, request:MotionContinuousRequest) -> Tuple[MotionContinuousResponse, CipherRpcErr]:
        print("Default MotionContinuous handler called")
        response: MotionContinuousResponse = MotionContinuousResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def MotionContinuousRpc(self, info:CipherUnaryRpcUserInfo, request:MotionContinuousRequest) -> Tuple[Optional[MotionContinuousResponse], CipherRpcErr]:
        response: MotionContinuousResponse = MotionContinuousResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.MotionContinuous.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def MotionStopHandler(self, request:Empty) -> Tuple[MotionStopResponse, CipherRpcErr]:
        print("Default MotionStop handler called")
        response: MotionStopResponse = MotionStopResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def MotionStopRpc(self, info:CipherUnaryRpcUserInfo, request:Empty) -> Tuple[Optional[MotionStopResponse], CipherRpcErr]:
        response: MotionStopResponse = MotionStopResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.MotionStop.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def ListFwFilesHandler(self, request:Empty) -> Tuple[ListFwFilesResponse, CipherRpcErr]:
        print("Default ListFwFiles handler called")
        response: ListFwFilesResponse = ListFwFilesResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def ListFwFilesRpc(self, info:CipherUnaryRpcUserInfo, request:Empty) -> Tuple[Optional[ListFwFilesResponse], CipherRpcErr]:
        response: ListFwFilesResponse = ListFwFilesResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.ListFwFiles.value,
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
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.UploadFwFile.value,
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
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.DeleteFwFile.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def FlashFwFileHandler(self, request:FlashFwFileRequest) -> Tuple[FlashFwFileResponse, CipherRpcErr]:
        print("Default FlashFwFile handler called")
        response: FlashFwFileResponse = FlashFwFileResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def FlashFwFileRpc(self, info:CipherUnaryRpcUserInfo, request:FlashFwFileRequest) -> Tuple[Optional[FlashFwFileResponse], CipherRpcErr]:
        response: FlashFwFileResponse = FlashFwFileResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.FlashFwFile.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error
    # Server side handlers
    def UartStreamHandler(self, request:UartStreamRequest) -> Tuple[UartStreamResponse, CipherRpcErr]:
        print("Default UartStream handler called")
        response: UartStreamResponse = UartStreamResponse()
        return response, CipherRpcErr.NOT_IMPLEMENTED
        
    # Client side 
    def UartStreamRpc(self, info:CipherUnaryRpcUserInfo, request:UartStreamRequest) -> Tuple[Optional[UartStreamResponse], CipherRpcErr]:
        response: UartStreamResponse = UartStreamResponse()
        context: CipherDaemonRpcContext = CipherDaemonRpcContext(
            local=True,
            user_info=info,
            service_id=MTIBRUNNERV1_SERVICE_ID,
            rpc_id=MtibRunnerV1Rpc.UartStream.value,
            request_struct=request,
            response_struct=response,            
        )
        
        self.daemon.execute_remote_rpc(context)
        
        return context.response_struct, context.user_info.error

# MtibRunnerV1 RPCs
mtibrunnerv1_service_rpcs = [
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.HealthCheck.value,
        type=CipherRpcType.UNARY,
        name="HealthCheck",
        handler=MtibRunnerV1.HealthCheckHandler,
        request_info=CipherMessageInfo(Empty),
        response_info=CipherMessageInfo(HealthCheckResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.GetRunnerInfo.value,
        type=CipherRpcType.UNARY,
        name="GetRunnerInfo",
        handler=MtibRunnerV1.GetRunnerInfoHandler,
        request_info=CipherMessageInfo(Empty),
        response_info=CipherMessageInfo(GetRunnerInfoResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.GpioConfig.value,
        type=CipherRpcType.UNARY,
        name="GpioConfig",
        handler=MtibRunnerV1.GpioConfigHandler,
        request_info=CipherMessageInfo(GpioConfigRequest),
        response_info=CipherMessageInfo(GpioConfigResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.GpioWrite.value,
        type=CipherRpcType.UNARY,
        name="GpioWrite",
        handler=MtibRunnerV1.GpioWriteHandler,
        request_info=CipherMessageInfo(GpioWriteRequest),
        response_info=CipherMessageInfo(GpioWriteResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.GpioRead.value,
        type=CipherRpcType.UNARY,
        name="GpioRead",
        handler=MtibRunnerV1.GpioReadHandler,
        request_info=CipherMessageInfo(GpioReadRequest),
        response_info=CipherMessageInfo(GpioReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.AdcRead.value,
        type=CipherRpcType.UNARY,
        name="AdcRead",
        handler=MtibRunnerV1.AdcReadHandler,
        request_info=CipherMessageInfo(AdcReadRequest),
        response_info=CipherMessageInfo(AdcReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.AdcReadAll.value,
        type=CipherRpcType.UNARY,
        name="AdcReadAll",
        handler=MtibRunnerV1.AdcReadAllHandler,
        request_info=CipherMessageInfo(AdcReadAllRequest),
        response_info=CipherMessageInfo(AdcReadAllResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.DutPowerEnable.value,
        type=CipherRpcType.UNARY,
        name="DutPowerEnable",
        handler=MtibRunnerV1.DutPowerEnableHandler,
        request_info=CipherMessageInfo(DutPowerRequest),
        response_info=CipherMessageInfo(DutPowerResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.DutPowerDisable.value,
        type=CipherRpcType.UNARY,
        name="DutPowerDisable",
        handler=MtibRunnerV1.DutPowerDisableHandler,
        request_info=CipherMessageInfo(Empty),
        response_info=CipherMessageInfo(DutPowerResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.DutChargePowerEnable.value,
        type=CipherRpcType.UNARY,
        name="DutChargePowerEnable",
        handler=MtibRunnerV1.DutChargePowerEnableHandler,
        request_info=CipherMessageInfo(DutPowerRequest),
        response_info=CipherMessageInfo(DutPowerResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.DutChargePowerDisable.value,
        type=CipherRpcType.UNARY,
        name="DutChargePowerDisable",
        handler=MtibRunnerV1.DutChargePowerDisableHandler,
        request_info=CipherMessageInfo(Empty),
        response_info=CipherMessageInfo(DutPowerResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.DutPowerRead.value,
        type=CipherRpcType.UNARY,
        name="DutPowerRead",
        handler=MtibRunnerV1.DutPowerReadHandler,
        request_info=CipherMessageInfo(Empty),
        response_info=CipherMessageInfo(DutPowerReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.AltimeterRead.value,
        type=CipherRpcType.UNARY,
        name="AltimeterRead",
        handler=MtibRunnerV1.AltimeterReadHandler,
        request_info=CipherMessageInfo(Empty),
        response_info=CipherMessageInfo(AltimeterReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.AccelRead.value,
        type=CipherRpcType.UNARY,
        name="AccelRead",
        handler=MtibRunnerV1.AccelReadHandler,
        request_info=CipherMessageInfo(Empty),
        response_info=CipherMessageInfo(AccelReadResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.GetMotionStatus.value,
        type=CipherRpcType.UNARY,
        name="GetMotionStatus",
        handler=MtibRunnerV1.GetMotionStatusHandler,
        request_info=CipherMessageInfo(Empty),
        response_info=CipherMessageInfo(GetMotionStatusResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.MotionHome.value,
        type=CipherRpcType.UNARY,
        name="MotionHome",
        handler=MtibRunnerV1.MotionHomeHandler,
        request_info=CipherMessageInfo(Empty),
        response_info=CipherMessageInfo(MotionHomeResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.MotionTrigger.value,
        type=CipherRpcType.UNARY,
        name="MotionTrigger",
        handler=MtibRunnerV1.MotionTriggerHandler,
        request_info=CipherMessageInfo(MotionTriggerRequest),
        response_info=CipherMessageInfo(MotionTriggerResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.MotionContinuous.value,
        type=CipherRpcType.UNARY,
        name="MotionContinuous",
        handler=MtibRunnerV1.MotionContinuousHandler,
        request_info=CipherMessageInfo(MotionContinuousRequest),
        response_info=CipherMessageInfo(MotionContinuousResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.MotionStop.value,
        type=CipherRpcType.UNARY,
        name="MotionStop",
        handler=MtibRunnerV1.MotionStopHandler,
        request_info=CipherMessageInfo(Empty),
        response_info=CipherMessageInfo(MotionStopResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.ListFwFiles.value,
        type=CipherRpcType.UNARY,
        name="ListFwFiles",
        handler=MtibRunnerV1.ListFwFilesHandler,
        request_info=CipherMessageInfo(Empty),
        response_info=CipherMessageInfo(ListFwFilesResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.UploadFwFile.value,
        type=CipherRpcType.UNARY,
        name="UploadFwFile",
        handler=MtibRunnerV1.UploadFwFileHandler,
        request_info=CipherMessageInfo(UploadFwFileRequest),
        response_info=CipherMessageInfo(UploadFwFileResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.DeleteFwFile.value,
        type=CipherRpcType.UNARY,
        name="DeleteFwFile",
        handler=MtibRunnerV1.DeleteFwFileHandler,
        request_info=CipherMessageInfo(DeleteFwFileRequest),
        response_info=CipherMessageInfo(DeleteFwFileResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.FlashFwFile.value,
        type=CipherRpcType.UNARY,
        name="FlashFwFile",
        handler=MtibRunnerV1.FlashFwFileHandler,
        request_info=CipherMessageInfo(FlashFwFileRequest),
        response_info=CipherMessageInfo(FlashFwFileResponse),
        supports_parallelism=True
    ),
    CipherRpcInfo(
        id=MtibRunnerV1Rpc.UartStream.value,
        type=CipherRpcType.UNARY,
        name="UartStream",
        handler=MtibRunnerV1.UartStreamHandler,
        request_info=CipherMessageInfo(UartStreamRequest),
        response_info=CipherMessageInfo(UartStreamResponse),
        supports_parallelism=True
    ),
]

# MtibRunnerV1 Service Definition
mtibrunnerv1_service_info = CipherServiceInfo(
    id=MTIBRUNNERV1_SERVICE_ID,
    name="MtibRunnerV1",
    num_allowed_hops=1,
    rpcs=mtibrunnerv1_service_rpcs
)
