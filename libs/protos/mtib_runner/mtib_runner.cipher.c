#include "mtib_runner.cipher.h"

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/iface/iface.h>
#include <corekinect/cipher/cipher.h>

// Protobuf includes
#include "mtib_runner.pb.h"

LOG_MODULE_REGISTER(mtibrunnerv1);

#define MTIBRUNNERV1_SERVICE_ID 1

typedef enum
{
    rpc_HealthCheck = 1,
    rpc_GetRunnerInfo = 2,
    rpc_GpioConfig = 3,
    rpc_GpioWrite = 4,
    rpc_GpioRead = 5,
    rpc_AdcRead = 6,
    rpc_AdcReadAll = 7,
    rpc_DutPowerEnable = 8,
    rpc_DutPowerDisable = 9,
    rpc_DutChargePowerEnable = 10,
    rpc_DutChargePowerDisable = 11,
    rpc_DutPowerRead = 12,
    rpc_AltimeterRead = 13,
    rpc_AccelRead = 14,
    rpc_GetMotionStatus = 15,
    rpc_MotionHome = 16,
    rpc_MotionTrigger = 17,
    rpc_MotionContinuous = 18,
    rpc_MotionStop = 19,
    rpc_ListFwFiles = 20,
    rpc_UploadFwFile = 21,
    rpc_DeleteFwFile = 22,
    rpc_FlashFwFile = 23,
    rpc_UartStream = 24,
} MtibRunnerV1_rpc;

// Server side
static bool MtibRunnerV1_HealthCheckHandlerImplemented = true;
__attribute__((weak)) HealthCheckResponse MtibRunnerV1_HealthCheckHandler(Empty request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_HealthCheckHandlerImplemented = false;
    HealthCheckResponse response  = {0};
    return response ;
}

cipher_rpc_err_t HealthCheckRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((HealthCheckResponse *)response ) = MtibRunnerV1_HealthCheckHandler(*((Empty *)request));
    return MtibRunnerV1_HealthCheckHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_GetRunnerInfoHandlerImplemented = true;
__attribute__((weak)) GetRunnerInfoResponse MtibRunnerV1_GetRunnerInfoHandler(Empty request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_GetRunnerInfoHandlerImplemented = false;
    GetRunnerInfoResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GetRunnerInfoRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GetRunnerInfoResponse *)response ) = MtibRunnerV1_GetRunnerInfoHandler(*((Empty *)request));
    return MtibRunnerV1_GetRunnerInfoHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_GpioConfigHandlerImplemented = true;
__attribute__((weak)) GpioConfigResponse MtibRunnerV1_GpioConfigHandler(GpioConfigRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_GpioConfigHandlerImplemented = false;
    GpioConfigResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GpioConfigRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GpioConfigResponse *)response ) = MtibRunnerV1_GpioConfigHandler(*((GpioConfigRequest *)request));
    return MtibRunnerV1_GpioConfigHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_GpioWriteHandlerImplemented = true;
__attribute__((weak)) GpioWriteResponse MtibRunnerV1_GpioWriteHandler(GpioWriteRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_GpioWriteHandlerImplemented = false;
    GpioWriteResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GpioWriteRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GpioWriteResponse *)response ) = MtibRunnerV1_GpioWriteHandler(*((GpioWriteRequest *)request));
    return MtibRunnerV1_GpioWriteHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_GpioReadHandlerImplemented = true;
__attribute__((weak)) GpioReadResponse MtibRunnerV1_GpioReadHandler(GpioReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_GpioReadHandlerImplemented = false;
    GpioReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GpioReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GpioReadResponse *)response ) = MtibRunnerV1_GpioReadHandler(*((GpioReadRequest *)request));
    return MtibRunnerV1_GpioReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_AdcReadHandlerImplemented = true;
__attribute__((weak)) AdcReadResponse MtibRunnerV1_AdcReadHandler(AdcReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_AdcReadHandlerImplemented = false;
    AdcReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AdcReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AdcReadResponse *)response ) = MtibRunnerV1_AdcReadHandler(*((AdcReadRequest *)request));
    return MtibRunnerV1_AdcReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_AdcReadAllHandlerImplemented = true;
__attribute__((weak)) AdcReadAllResponse MtibRunnerV1_AdcReadAllHandler(AdcReadAllRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_AdcReadAllHandlerImplemented = false;
    AdcReadAllResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AdcReadAllRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AdcReadAllResponse *)response ) = MtibRunnerV1_AdcReadAllHandler(*((AdcReadAllRequest *)request));
    return MtibRunnerV1_AdcReadAllHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_DutPowerEnableHandlerImplemented = true;
__attribute__((weak)) DutPowerResponse MtibRunnerV1_DutPowerEnableHandler(DutPowerRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_DutPowerEnableHandlerImplemented = false;
    DutPowerResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutPowerEnableRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutPowerResponse *)response ) = MtibRunnerV1_DutPowerEnableHandler(*((DutPowerRequest *)request));
    return MtibRunnerV1_DutPowerEnableHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_DutPowerDisableHandlerImplemented = true;
__attribute__((weak)) DutPowerResponse MtibRunnerV1_DutPowerDisableHandler(Empty request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_DutPowerDisableHandlerImplemented = false;
    DutPowerResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutPowerDisableRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutPowerResponse *)response ) = MtibRunnerV1_DutPowerDisableHandler(*((Empty *)request));
    return MtibRunnerV1_DutPowerDisableHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_DutChargePowerEnableHandlerImplemented = true;
__attribute__((weak)) DutPowerResponse MtibRunnerV1_DutChargePowerEnableHandler(DutPowerRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_DutChargePowerEnableHandlerImplemented = false;
    DutPowerResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutChargePowerEnableRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutPowerResponse *)response ) = MtibRunnerV1_DutChargePowerEnableHandler(*((DutPowerRequest *)request));
    return MtibRunnerV1_DutChargePowerEnableHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_DutChargePowerDisableHandlerImplemented = true;
__attribute__((weak)) DutPowerResponse MtibRunnerV1_DutChargePowerDisableHandler(Empty request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_DutChargePowerDisableHandlerImplemented = false;
    DutPowerResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutChargePowerDisableRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutPowerResponse *)response ) = MtibRunnerV1_DutChargePowerDisableHandler(*((Empty *)request));
    return MtibRunnerV1_DutChargePowerDisableHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_DutPowerReadHandlerImplemented = true;
__attribute__((weak)) DutPowerReadResponse MtibRunnerV1_DutPowerReadHandler(Empty request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_DutPowerReadHandlerImplemented = false;
    DutPowerReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutPowerReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutPowerReadResponse *)response ) = MtibRunnerV1_DutPowerReadHandler(*((Empty *)request));
    return MtibRunnerV1_DutPowerReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_AltimeterReadHandlerImplemented = true;
__attribute__((weak)) AltimeterReadResponse MtibRunnerV1_AltimeterReadHandler(Empty request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_AltimeterReadHandlerImplemented = false;
    AltimeterReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AltimeterReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AltimeterReadResponse *)response ) = MtibRunnerV1_AltimeterReadHandler(*((Empty *)request));
    return MtibRunnerV1_AltimeterReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_AccelReadHandlerImplemented = true;
__attribute__((weak)) AccelReadResponse MtibRunnerV1_AccelReadHandler(Empty request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_AccelReadHandlerImplemented = false;
    AccelReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AccelReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AccelReadResponse *)response ) = MtibRunnerV1_AccelReadHandler(*((Empty *)request));
    return MtibRunnerV1_AccelReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_GetMotionStatusHandlerImplemented = true;
__attribute__((weak)) GetMotionStatusResponse MtibRunnerV1_GetMotionStatusHandler(Empty request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_GetMotionStatusHandlerImplemented = false;
    GetMotionStatusResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GetMotionStatusRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GetMotionStatusResponse *)response ) = MtibRunnerV1_GetMotionStatusHandler(*((Empty *)request));
    return MtibRunnerV1_GetMotionStatusHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_MotionHomeHandlerImplemented = true;
__attribute__((weak)) MotionHomeResponse MtibRunnerV1_MotionHomeHandler(Empty request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_MotionHomeHandlerImplemented = false;
    MotionHomeResponse response  = {0};
    return response ;
}

cipher_rpc_err_t MotionHomeRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((MotionHomeResponse *)response ) = MtibRunnerV1_MotionHomeHandler(*((Empty *)request));
    return MtibRunnerV1_MotionHomeHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_MotionTriggerHandlerImplemented = true;
__attribute__((weak)) MotionTriggerResponse MtibRunnerV1_MotionTriggerHandler(MotionTriggerRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_MotionTriggerHandlerImplemented = false;
    MotionTriggerResponse response  = {0};
    return response ;
}

cipher_rpc_err_t MotionTriggerRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((MotionTriggerResponse *)response ) = MtibRunnerV1_MotionTriggerHandler(*((MotionTriggerRequest *)request));
    return MtibRunnerV1_MotionTriggerHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_MotionContinuousHandlerImplemented = true;
__attribute__((weak)) MotionContinuousResponse MtibRunnerV1_MotionContinuousHandler(MotionContinuousRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_MotionContinuousHandlerImplemented = false;
    MotionContinuousResponse response  = {0};
    return response ;
}

cipher_rpc_err_t MotionContinuousRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((MotionContinuousResponse *)response ) = MtibRunnerV1_MotionContinuousHandler(*((MotionContinuousRequest *)request));
    return MtibRunnerV1_MotionContinuousHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_MotionStopHandlerImplemented = true;
__attribute__((weak)) MotionStopResponse MtibRunnerV1_MotionStopHandler(Empty request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_MotionStopHandlerImplemented = false;
    MotionStopResponse response  = {0};
    return response ;
}

cipher_rpc_err_t MotionStopRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((MotionStopResponse *)response ) = MtibRunnerV1_MotionStopHandler(*((Empty *)request));
    return MtibRunnerV1_MotionStopHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_ListFwFilesHandlerImplemented = true;
__attribute__((weak)) ListFwFilesResponse MtibRunnerV1_ListFwFilesHandler(Empty request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_ListFwFilesHandlerImplemented = false;
    ListFwFilesResponse response  = {0};
    return response ;
}

cipher_rpc_err_t ListFwFilesRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((ListFwFilesResponse *)response ) = MtibRunnerV1_ListFwFilesHandler(*((Empty *)request));
    return MtibRunnerV1_ListFwFilesHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_UploadFwFileHandlerImplemented = true;
__attribute__((weak)) UploadFwFileResponse MtibRunnerV1_UploadFwFileHandler(UploadFwFileRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_UploadFwFileHandlerImplemented = false;
    UploadFwFileResponse response  = {0};
    return response ;
}

cipher_rpc_err_t UploadFwFileRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((UploadFwFileResponse *)response ) = MtibRunnerV1_UploadFwFileHandler(*((UploadFwFileRequest *)request));
    return MtibRunnerV1_UploadFwFileHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_DeleteFwFileHandlerImplemented = true;
__attribute__((weak)) DeleteFwFileResponse MtibRunnerV1_DeleteFwFileHandler(DeleteFwFileRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_DeleteFwFileHandlerImplemented = false;
    DeleteFwFileResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DeleteFwFileRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DeleteFwFileResponse *)response ) = MtibRunnerV1_DeleteFwFileHandler(*((DeleteFwFileRequest *)request));
    return MtibRunnerV1_DeleteFwFileHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_FlashFwFileHandlerImplemented = true;
__attribute__((weak)) FlashFwFileResponse MtibRunnerV1_FlashFwFileHandler(FlashFwFileRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_FlashFwFileHandlerImplemented = false;
    FlashFwFileResponse response  = {0};
    return response ;
}

cipher_rpc_err_t FlashFwFileRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((FlashFwFileResponse *)response ) = MtibRunnerV1_FlashFwFileHandler(*((FlashFwFileRequest *)request));
    return MtibRunnerV1_FlashFwFileHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerV1_UartStreamHandlerImplemented = true;
__attribute__((weak)) UartStreamResponse MtibRunnerV1_UartStreamHandler(UartStreamRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerV1_UartStreamHandlerImplemented = false;
    UartStreamResponse response  = {0};
    return response ;
}

cipher_rpc_err_t UartStreamRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((UartStreamResponse *)response ) = MtibRunnerV1_UartStreamHandler(*((UartStreamRequest *)request));
    return MtibRunnerV1_UartStreamHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Client side
HealthCheckResponse MtibRunnerV1_HealthCheckRpc(cipher_unary_rpc_user_info_t *info, Empty request)
{
    HealthCheckResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_HealthCheck,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GetRunnerInfoResponse MtibRunnerV1_GetRunnerInfoRpc(cipher_unary_rpc_user_info_t *info, Empty request)
{
    GetRunnerInfoResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_GetRunnerInfo,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GpioConfigResponse MtibRunnerV1_GpioConfigRpc(cipher_unary_rpc_user_info_t *info, GpioConfigRequest request)
{
    GpioConfigResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_GpioConfig,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GpioWriteResponse MtibRunnerV1_GpioWriteRpc(cipher_unary_rpc_user_info_t *info, GpioWriteRequest request)
{
    GpioWriteResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_GpioWrite,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GpioReadResponse MtibRunnerV1_GpioReadRpc(cipher_unary_rpc_user_info_t *info, GpioReadRequest request)
{
    GpioReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_GpioRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AdcReadResponse MtibRunnerV1_AdcReadRpc(cipher_unary_rpc_user_info_t *info, AdcReadRequest request)
{
    AdcReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_AdcRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AdcReadAllResponse MtibRunnerV1_AdcReadAllRpc(cipher_unary_rpc_user_info_t *info, AdcReadAllRequest request)
{
    AdcReadAllResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_AdcReadAll,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutPowerResponse MtibRunnerV1_DutPowerEnableRpc(cipher_unary_rpc_user_info_t *info, DutPowerRequest request)
{
    DutPowerResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_DutPowerEnable,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutPowerResponse MtibRunnerV1_DutPowerDisableRpc(cipher_unary_rpc_user_info_t *info, Empty request)
{
    DutPowerResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_DutPowerDisable,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutPowerResponse MtibRunnerV1_DutChargePowerEnableRpc(cipher_unary_rpc_user_info_t *info, DutPowerRequest request)
{
    DutPowerResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_DutChargePowerEnable,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutPowerResponse MtibRunnerV1_DutChargePowerDisableRpc(cipher_unary_rpc_user_info_t *info, Empty request)
{
    DutPowerResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_DutChargePowerDisable,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutPowerReadResponse MtibRunnerV1_DutPowerReadRpc(cipher_unary_rpc_user_info_t *info, Empty request)
{
    DutPowerReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_DutPowerRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AltimeterReadResponse MtibRunnerV1_AltimeterReadRpc(cipher_unary_rpc_user_info_t *info, Empty request)
{
    AltimeterReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_AltimeterRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AccelReadResponse MtibRunnerV1_AccelReadRpc(cipher_unary_rpc_user_info_t *info, Empty request)
{
    AccelReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_AccelRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GetMotionStatusResponse MtibRunnerV1_GetMotionStatusRpc(cipher_unary_rpc_user_info_t *info, Empty request)
{
    GetMotionStatusResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_GetMotionStatus,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
MotionHomeResponse MtibRunnerV1_MotionHomeRpc(cipher_unary_rpc_user_info_t *info, Empty request)
{
    MotionHomeResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_MotionHome,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
MotionTriggerResponse MtibRunnerV1_MotionTriggerRpc(cipher_unary_rpc_user_info_t *info, MotionTriggerRequest request)
{
    MotionTriggerResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_MotionTrigger,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
MotionContinuousResponse MtibRunnerV1_MotionContinuousRpc(cipher_unary_rpc_user_info_t *info, MotionContinuousRequest request)
{
    MotionContinuousResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_MotionContinuous,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
MotionStopResponse MtibRunnerV1_MotionStopRpc(cipher_unary_rpc_user_info_t *info, Empty request)
{
    MotionStopResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_MotionStop,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
ListFwFilesResponse MtibRunnerV1_ListFwFilesRpc(cipher_unary_rpc_user_info_t *info, Empty request)
{
    ListFwFilesResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_ListFwFiles,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
UploadFwFileResponse MtibRunnerV1_UploadFwFileRpc(cipher_unary_rpc_user_info_t *info, UploadFwFileRequest request)
{
    UploadFwFileResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_UploadFwFile,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DeleteFwFileResponse MtibRunnerV1_DeleteFwFileRpc(cipher_unary_rpc_user_info_t *info, DeleteFwFileRequest request)
{
    DeleteFwFileResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_DeleteFwFile,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
FlashFwFileResponse MtibRunnerV1_FlashFwFileRpc(cipher_unary_rpc_user_info_t *info, FlashFwFileRequest request)
{
    FlashFwFileResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_FlashFwFile,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
UartStreamResponse MtibRunnerV1_UartStreamRpc(cipher_unary_rpc_user_info_t *info, UartStreamRequest request)
{
    UartStreamResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERV1_SERVICE_ID,
        .rpc_id = rpc_UartStream,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}

static cipher_rpc_info_t mtibrunnerv1_rpcs[] =
{
    {
        .id = rpc_HealthCheck,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "HealthCheck",
        .handler = HealthCheckRpcPrvHandler,
        .request_info = {
            .fields = Empty_fields,
            .encoded_size = Empty_size,
            .decoded_size = sizeof(Empty)
        },
        .response_info = {
            .fields = HealthCheckResponse_fields,
            .encoded_size = HealthCheckResponse_size,
            .decoded_size = sizeof(HealthCheckResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_GetRunnerInfo,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "GetRunnerInfo",
        .handler = GetRunnerInfoRpcPrvHandler,
        .request_info = {
            .fields = Empty_fields,
            .encoded_size = Empty_size,
            .decoded_size = sizeof(Empty)
        },
        .response_info = {
            .fields = GetRunnerInfoResponse_fields,
            .encoded_size = GetRunnerInfoResponse_size,
            .decoded_size = sizeof(GetRunnerInfoResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_GpioConfig,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "GpioConfig",
        .handler = GpioConfigRpcPrvHandler,
        .request_info = {
            .fields = GpioConfigRequest_fields,
            .encoded_size = GpioConfigRequest_size,
            .decoded_size = sizeof(GpioConfigRequest)
        },
        .response_info = {
            .fields = GpioConfigResponse_fields,
            .encoded_size = GpioConfigResponse_size,
            .decoded_size = sizeof(GpioConfigResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_GpioWrite,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "GpioWrite",
        .handler = GpioWriteRpcPrvHandler,
        .request_info = {
            .fields = GpioWriteRequest_fields,
            .encoded_size = GpioWriteRequest_size,
            .decoded_size = sizeof(GpioWriteRequest)
        },
        .response_info = {
            .fields = GpioWriteResponse_fields,
            .encoded_size = GpioWriteResponse_size,
            .decoded_size = sizeof(GpioWriteResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_GpioRead,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "GpioRead",
        .handler = GpioReadRpcPrvHandler,
        .request_info = {
            .fields = GpioReadRequest_fields,
            .encoded_size = GpioReadRequest_size,
            .decoded_size = sizeof(GpioReadRequest)
        },
        .response_info = {
            .fields = GpioReadResponse_fields,
            .encoded_size = GpioReadResponse_size,
            .decoded_size = sizeof(GpioReadResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_AdcRead,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "AdcRead",
        .handler = AdcReadRpcPrvHandler,
        .request_info = {
            .fields = AdcReadRequest_fields,
            .encoded_size = AdcReadRequest_size,
            .decoded_size = sizeof(AdcReadRequest)
        },
        .response_info = {
            .fields = AdcReadResponse_fields,
            .encoded_size = AdcReadResponse_size,
            .decoded_size = sizeof(AdcReadResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_AdcReadAll,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "AdcReadAll",
        .handler = AdcReadAllRpcPrvHandler,
        .request_info = {
            .fields = AdcReadAllRequest_fields,
            .encoded_size = AdcReadAllRequest_size,
            .decoded_size = sizeof(AdcReadAllRequest)
        },
        .response_info = {
            .fields = AdcReadAllResponse_fields,
            .encoded_size = AdcReadAllResponse_size,
            .decoded_size = sizeof(AdcReadAllResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_DutPowerEnable,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "DutPowerEnable",
        .handler = DutPowerEnableRpcPrvHandler,
        .request_info = {
            .fields = DutPowerRequest_fields,
            .encoded_size = DutPowerRequest_size,
            .decoded_size = sizeof(DutPowerRequest)
        },
        .response_info = {
            .fields = DutPowerResponse_fields,
            .encoded_size = DutPowerResponse_size,
            .decoded_size = sizeof(DutPowerResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_DutPowerDisable,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "DutPowerDisable",
        .handler = DutPowerDisableRpcPrvHandler,
        .request_info = {
            .fields = Empty_fields,
            .encoded_size = Empty_size,
            .decoded_size = sizeof(Empty)
        },
        .response_info = {
            .fields = DutPowerResponse_fields,
            .encoded_size = DutPowerResponse_size,
            .decoded_size = sizeof(DutPowerResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_DutChargePowerEnable,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "DutChargePowerEnable",
        .handler = DutChargePowerEnableRpcPrvHandler,
        .request_info = {
            .fields = DutPowerRequest_fields,
            .encoded_size = DutPowerRequest_size,
            .decoded_size = sizeof(DutPowerRequest)
        },
        .response_info = {
            .fields = DutPowerResponse_fields,
            .encoded_size = DutPowerResponse_size,
            .decoded_size = sizeof(DutPowerResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_DutChargePowerDisable,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "DutChargePowerDisable",
        .handler = DutChargePowerDisableRpcPrvHandler,
        .request_info = {
            .fields = Empty_fields,
            .encoded_size = Empty_size,
            .decoded_size = sizeof(Empty)
        },
        .response_info = {
            .fields = DutPowerResponse_fields,
            .encoded_size = DutPowerResponse_size,
            .decoded_size = sizeof(DutPowerResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_DutPowerRead,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "DutPowerRead",
        .handler = DutPowerReadRpcPrvHandler,
        .request_info = {
            .fields = Empty_fields,
            .encoded_size = Empty_size,
            .decoded_size = sizeof(Empty)
        },
        .response_info = {
            .fields = DutPowerReadResponse_fields,
            .encoded_size = DutPowerReadResponse_size,
            .decoded_size = sizeof(DutPowerReadResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_AltimeterRead,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "AltimeterRead",
        .handler = AltimeterReadRpcPrvHandler,
        .request_info = {
            .fields = Empty_fields,
            .encoded_size = Empty_size,
            .decoded_size = sizeof(Empty)
        },
        .response_info = {
            .fields = AltimeterReadResponse_fields,
            .encoded_size = AltimeterReadResponse_size,
            .decoded_size = sizeof(AltimeterReadResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_AccelRead,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "AccelRead",
        .handler = AccelReadRpcPrvHandler,
        .request_info = {
            .fields = Empty_fields,
            .encoded_size = Empty_size,
            .decoded_size = sizeof(Empty)
        },
        .response_info = {
            .fields = AccelReadResponse_fields,
            .encoded_size = AccelReadResponse_size,
            .decoded_size = sizeof(AccelReadResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_GetMotionStatus,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "GetMotionStatus",
        .handler = GetMotionStatusRpcPrvHandler,
        .request_info = {
            .fields = Empty_fields,
            .encoded_size = Empty_size,
            .decoded_size = sizeof(Empty)
        },
        .response_info = {
            .fields = GetMotionStatusResponse_fields,
            .encoded_size = GetMotionStatusResponse_size,
            .decoded_size = sizeof(GetMotionStatusResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_MotionHome,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "MotionHome",
        .handler = MotionHomeRpcPrvHandler,
        .request_info = {
            .fields = Empty_fields,
            .encoded_size = Empty_size,
            .decoded_size = sizeof(Empty)
        },
        .response_info = {
            .fields = MotionHomeResponse_fields,
            .encoded_size = MotionHomeResponse_size,
            .decoded_size = sizeof(MotionHomeResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_MotionTrigger,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "MotionTrigger",
        .handler = MotionTriggerRpcPrvHandler,
        .request_info = {
            .fields = MotionTriggerRequest_fields,
            .encoded_size = MotionTriggerRequest_size,
            .decoded_size = sizeof(MotionTriggerRequest)
        },
        .response_info = {
            .fields = MotionTriggerResponse_fields,
            .encoded_size = MotionTriggerResponse_size,
            .decoded_size = sizeof(MotionTriggerResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_MotionContinuous,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "MotionContinuous",
        .handler = MotionContinuousRpcPrvHandler,
        .request_info = {
            .fields = MotionContinuousRequest_fields,
            .encoded_size = MotionContinuousRequest_size,
            .decoded_size = sizeof(MotionContinuousRequest)
        },
        .response_info = {
            .fields = MotionContinuousResponse_fields,
            .encoded_size = MotionContinuousResponse_size,
            .decoded_size = sizeof(MotionContinuousResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_MotionStop,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "MotionStop",
        .handler = MotionStopRpcPrvHandler,
        .request_info = {
            .fields = Empty_fields,
            .encoded_size = Empty_size,
            .decoded_size = sizeof(Empty)
        },
        .response_info = {
            .fields = MotionStopResponse_fields,
            .encoded_size = MotionStopResponse_size,
            .decoded_size = sizeof(MotionStopResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_ListFwFiles,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "ListFwFiles",
        .handler = ListFwFilesRpcPrvHandler,
        .request_info = {
            .fields = Empty_fields,
            .encoded_size = Empty_size,
            .decoded_size = sizeof(Empty)
        },
        .response_info = {
            .fields = ListFwFilesResponse_fields,
            .encoded_size = ListFwFilesResponse_size,
            .decoded_size = sizeof(ListFwFilesResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_UploadFwFile,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "UploadFwFile",
        .handler = UploadFwFileRpcPrvHandler,
        .request_info = {
            .fields = UploadFwFileRequest_fields,
            .encoded_size = UploadFwFileRequest_size,
            .decoded_size = sizeof(UploadFwFileRequest)
        },
        .response_info = {
            .fields = UploadFwFileResponse_fields,
            .encoded_size = UploadFwFileResponse_size,
            .decoded_size = sizeof(UploadFwFileResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_DeleteFwFile,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "DeleteFwFile",
        .handler = DeleteFwFileRpcPrvHandler,
        .request_info = {
            .fields = DeleteFwFileRequest_fields,
            .encoded_size = DeleteFwFileRequest_size,
            .decoded_size = sizeof(DeleteFwFileRequest)
        },
        .response_info = {
            .fields = DeleteFwFileResponse_fields,
            .encoded_size = DeleteFwFileResponse_size,
            .decoded_size = sizeof(DeleteFwFileResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_FlashFwFile,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "FlashFwFile",
        .handler = FlashFwFileRpcPrvHandler,
        .request_info = {
            .fields = FlashFwFileRequest_fields,
            .encoded_size = FlashFwFileRequest_size,
            .decoded_size = sizeof(FlashFwFileRequest)
        },
        .response_info = {
            .fields = FlashFwFileResponse_fields,
            .encoded_size = FlashFwFileResponse_size,
            .decoded_size = sizeof(FlashFwFileResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_UartStream,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "UartStream",
        .handler = UartStreamRpcPrvHandler,
        .request_info = {
            .fields = UartStreamRequest_fields,
            .encoded_size = UartStreamRequest_size,
            .decoded_size = sizeof(UartStreamRequest)
        },
        .response_info = {
            .fields = UartStreamResponse_fields,
            .encoded_size = UartStreamResponse_size,
            .decoded_size = sizeof(UartStreamResponse)
        },
        .supports_parallelism = true,
    },
};

static cipher_service_info_t mtibrunnerv1_service =
{
    .id = MTIBRUNNERV1_SERVICE_ID,
    .name = "MtibRunnerV1",
    .max_hops = 1,
    .rpcs = mtibrunnerv1_rpcs,
    .num_rpcs = ARRAY_SIZE(mtibrunnerv1_rpcs),
};

cipher_service_info_t *get_mtibrunnerv1service_info(void)
{
    return &mtibrunnerv1_service;
}
