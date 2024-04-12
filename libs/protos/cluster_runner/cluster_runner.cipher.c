#include "cluster_runner.cipher.h"

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/iface/iface.h>
#include <corekinect/cipher/cipher.h>

// Protobuf includes
#include "cluster_runner.pb.h"

LOG_MODULE_REGISTER(clusterrunner);

#define CLUSTERRUNNER_SERVICE_ID 1

typedef enum
{
    rpc_HealthCheck = 1,
    rpc_GetRunnerInfo = 2,
    rpc_Reset = 3,
    rpc_GpioConfig = 4,
    rpc_GpioWrite = 5,
    rpc_GpioRead = 6,
    rpc_AdcRead = 7,
    rpc_AdcReadAll = 8,
    rpc_DutPowerEnable = 9,
    rpc_DutChargePowerEnable = 10,
    rpc_DutVoltageSet = 11,
    rpc_DutCurrentRead = 12,
    rpc_DutVoltageRead = 13,
    rpc_DutPowerRead = 14,
    rpc_AltimeterRead = 15,
    rpc_AccelRead = 16,
    rpc_AccelReadMaxForce = 17,
    rpc_EepromRead = 18,
    rpc_EepromWrite = 19,
    rpc_ListFwFiles = 20,
    rpc_UploadFwFile = 21,
    rpc_DeleteFwFile = 22,
    rpc_FlashHexFile = 23,
} ClusterRunner_rpc;

// Server side
static bool ClusterRunner_HealthCheckHandlerImplemented = true;
__attribute__((weak)) HealthCheckResponse ClusterRunner_HealthCheckHandler(HealthCheckRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_HealthCheckHandlerImplemented = false;
    HealthCheckResponse response  = {0};
    return response ;
}

cipher_rpc_err_t HealthCheckRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((HealthCheckResponse *)response ) = ClusterRunner_HealthCheckHandler(*((HealthCheckRequest *)request));
    return ClusterRunner_HealthCheckHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_GetRunnerInfoHandlerImplemented = true;
__attribute__((weak)) GetRunnerInfoResponse ClusterRunner_GetRunnerInfoHandler(GetRunnerInfoRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_GetRunnerInfoHandlerImplemented = false;
    GetRunnerInfoResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GetRunnerInfoRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GetRunnerInfoResponse *)response ) = ClusterRunner_GetRunnerInfoHandler(*((GetRunnerInfoRequest *)request));
    return ClusterRunner_GetRunnerInfoHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_ResetHandlerImplemented = true;
__attribute__((weak)) ResetResponse ClusterRunner_ResetHandler(ResetRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_ResetHandlerImplemented = false;
    ResetResponse response  = {0};
    return response ;
}

cipher_rpc_err_t ResetRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((ResetResponse *)response ) = ClusterRunner_ResetHandler(*((ResetRequest *)request));
    return ClusterRunner_ResetHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_GpioConfigHandlerImplemented = true;
__attribute__((weak)) GpioConfigResponse ClusterRunner_GpioConfigHandler(GpioConfigRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_GpioConfigHandlerImplemented = false;
    GpioConfigResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GpioConfigRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GpioConfigResponse *)response ) = ClusterRunner_GpioConfigHandler(*((GpioConfigRequest *)request));
    return ClusterRunner_GpioConfigHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_GpioWriteHandlerImplemented = true;
__attribute__((weak)) GpioWriteResponse ClusterRunner_GpioWriteHandler(GpioWriteRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_GpioWriteHandlerImplemented = false;
    GpioWriteResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GpioWriteRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GpioWriteResponse *)response ) = ClusterRunner_GpioWriteHandler(*((GpioWriteRequest *)request));
    return ClusterRunner_GpioWriteHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_GpioReadHandlerImplemented = true;
__attribute__((weak)) GpioReadResponse ClusterRunner_GpioReadHandler(GpioReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_GpioReadHandlerImplemented = false;
    GpioReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GpioReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GpioReadResponse *)response ) = ClusterRunner_GpioReadHandler(*((GpioReadRequest *)request));
    return ClusterRunner_GpioReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_AdcReadHandlerImplemented = true;
__attribute__((weak)) AdcReadResponse ClusterRunner_AdcReadHandler(AdcReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_AdcReadHandlerImplemented = false;
    AdcReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AdcReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AdcReadResponse *)response ) = ClusterRunner_AdcReadHandler(*((AdcReadRequest *)request));
    return ClusterRunner_AdcReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_AdcReadAllHandlerImplemented = true;
__attribute__((weak)) AdcReadAllResponse ClusterRunner_AdcReadAllHandler(AdcReadAllRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_AdcReadAllHandlerImplemented = false;
    AdcReadAllResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AdcReadAllRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AdcReadAllResponse *)response ) = ClusterRunner_AdcReadAllHandler(*((AdcReadAllRequest *)request));
    return ClusterRunner_AdcReadAllHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_DutPowerEnableHandlerImplemented = true;
__attribute__((weak)) DutPowerEnableResponse ClusterRunner_DutPowerEnableHandler(DutPowerEnableRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_DutPowerEnableHandlerImplemented = false;
    DutPowerEnableResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutPowerEnableRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutPowerEnableResponse *)response ) = ClusterRunner_DutPowerEnableHandler(*((DutPowerEnableRequest *)request));
    return ClusterRunner_DutPowerEnableHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_DutChargePowerEnableHandlerImplemented = true;
__attribute__((weak)) DutPowerEnableResponse ClusterRunner_DutChargePowerEnableHandler(DutPowerEnableRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_DutChargePowerEnableHandlerImplemented = false;
    DutPowerEnableResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutChargePowerEnableRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutPowerEnableResponse *)response ) = ClusterRunner_DutChargePowerEnableHandler(*((DutPowerEnableRequest *)request));
    return ClusterRunner_DutChargePowerEnableHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_DutVoltageSetHandlerImplemented = true;
__attribute__((weak)) DutVoltageSetResponse ClusterRunner_DutVoltageSetHandler(DutVoltageSetRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_DutVoltageSetHandlerImplemented = false;
    DutVoltageSetResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutVoltageSetRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutVoltageSetResponse *)response ) = ClusterRunner_DutVoltageSetHandler(*((DutVoltageSetRequest *)request));
    return ClusterRunner_DutVoltageSetHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_DutCurrentReadHandlerImplemented = true;
__attribute__((weak)) DutCurrentReadResponse ClusterRunner_DutCurrentReadHandler(DutCurrentReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_DutCurrentReadHandlerImplemented = false;
    DutCurrentReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutCurrentReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutCurrentReadResponse *)response ) = ClusterRunner_DutCurrentReadHandler(*((DutCurrentReadRequest *)request));
    return ClusterRunner_DutCurrentReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_DutVoltageReadHandlerImplemented = true;
__attribute__((weak)) DutVoltageReadResponse ClusterRunner_DutVoltageReadHandler(DutVoltageReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_DutVoltageReadHandlerImplemented = false;
    DutVoltageReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutVoltageReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutVoltageReadResponse *)response ) = ClusterRunner_DutVoltageReadHandler(*((DutVoltageReadRequest *)request));
    return ClusterRunner_DutVoltageReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_DutPowerReadHandlerImplemented = true;
__attribute__((weak)) DutPowerReadResponse ClusterRunner_DutPowerReadHandler(DutPowerReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_DutPowerReadHandlerImplemented = false;
    DutPowerReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutPowerReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutPowerReadResponse *)response ) = ClusterRunner_DutPowerReadHandler(*((DutPowerReadRequest *)request));
    return ClusterRunner_DutPowerReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_AltimeterReadHandlerImplemented = true;
__attribute__((weak)) AltimeterReadResponse ClusterRunner_AltimeterReadHandler(AltimeterReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_AltimeterReadHandlerImplemented = false;
    AltimeterReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AltimeterReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AltimeterReadResponse *)response ) = ClusterRunner_AltimeterReadHandler(*((AltimeterReadRequest *)request));
    return ClusterRunner_AltimeterReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_AccelReadHandlerImplemented = true;
__attribute__((weak)) AccelReadResponse ClusterRunner_AccelReadHandler(AccelReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_AccelReadHandlerImplemented = false;
    AccelReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AccelReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AccelReadResponse *)response ) = ClusterRunner_AccelReadHandler(*((AccelReadRequest *)request));
    return ClusterRunner_AccelReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_AccelReadMaxForceHandlerImplemented = true;
__attribute__((weak)) AccelReadMaxResponse ClusterRunner_AccelReadMaxForceHandler(AccelReadMaxRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_AccelReadMaxForceHandlerImplemented = false;
    AccelReadMaxResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AccelReadMaxForceRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AccelReadMaxResponse *)response ) = ClusterRunner_AccelReadMaxForceHandler(*((AccelReadMaxRequest *)request));
    return ClusterRunner_AccelReadMaxForceHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_EepromReadHandlerImplemented = true;
__attribute__((weak)) EepromReadResponse ClusterRunner_EepromReadHandler(EepromReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_EepromReadHandlerImplemented = false;
    EepromReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t EepromReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((EepromReadResponse *)response ) = ClusterRunner_EepromReadHandler(*((EepromReadRequest *)request));
    return ClusterRunner_EepromReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_EepromWriteHandlerImplemented = true;
__attribute__((weak)) EepromWriteResponse ClusterRunner_EepromWriteHandler(EepromWriteRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_EepromWriteHandlerImplemented = false;
    EepromWriteResponse response  = {0};
    return response ;
}

cipher_rpc_err_t EepromWriteRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((EepromWriteResponse *)response ) = ClusterRunner_EepromWriteHandler(*((EepromWriteRequest *)request));
    return ClusterRunner_EepromWriteHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_ListFwFilesHandlerImplemented = true;
__attribute__((weak)) ListFwFilesResponse ClusterRunner_ListFwFilesHandler(ListFwFilesRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_ListFwFilesHandlerImplemented = false;
    ListFwFilesResponse response  = {0};
    return response ;
}

cipher_rpc_err_t ListFwFilesRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((ListFwFilesResponse *)response ) = ClusterRunner_ListFwFilesHandler(*((ListFwFilesRequest *)request));
    return ClusterRunner_ListFwFilesHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_UploadFwFileHandlerImplemented = true;
__attribute__((weak)) UploadFwFileResponse ClusterRunner_UploadFwFileHandler(UploadFwFileRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_UploadFwFileHandlerImplemented = false;
    UploadFwFileResponse response  = {0};
    return response ;
}

cipher_rpc_err_t UploadFwFileRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((UploadFwFileResponse *)response ) = ClusterRunner_UploadFwFileHandler(*((UploadFwFileRequest *)request));
    return ClusterRunner_UploadFwFileHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_DeleteFwFileHandlerImplemented = true;
__attribute__((weak)) DeleteFwFileResponse ClusterRunner_DeleteFwFileHandler(DeleteFwFileRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_DeleteFwFileHandlerImplemented = false;
    DeleteFwFileResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DeleteFwFileRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DeleteFwFileResponse *)response ) = ClusterRunner_DeleteFwFileHandler(*((DeleteFwFileRequest *)request));
    return ClusterRunner_DeleteFwFileHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterRunner_FlashHexFileHandlerImplemented = true;
__attribute__((weak)) FlashHexFileResponse ClusterRunner_FlashHexFileHandler(FlashHexFileRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterRunner_FlashHexFileHandlerImplemented = false;
    FlashHexFileResponse response  = {0};
    return response ;
}

cipher_rpc_err_t FlashHexFileRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((FlashHexFileResponse *)response ) = ClusterRunner_FlashHexFileHandler(*((FlashHexFileRequest *)request));
    return ClusterRunner_FlashHexFileHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Client side
HealthCheckResponse ClusterRunner_HealthCheckRpc(cipher_unary_rpc_user_info_t *info, HealthCheckRequest request)
{
    HealthCheckResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_HealthCheck,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GetRunnerInfoResponse ClusterRunner_GetRunnerInfoRpc(cipher_unary_rpc_user_info_t *info, GetRunnerInfoRequest request)
{
    GetRunnerInfoResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_GetRunnerInfo,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
ResetResponse ClusterRunner_ResetRpc(cipher_unary_rpc_user_info_t *info, ResetRequest request)
{
    ResetResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_Reset,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GpioConfigResponse ClusterRunner_GpioConfigRpc(cipher_unary_rpc_user_info_t *info, GpioConfigRequest request)
{
    GpioConfigResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_GpioConfig,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GpioWriteResponse ClusterRunner_GpioWriteRpc(cipher_unary_rpc_user_info_t *info, GpioWriteRequest request)
{
    GpioWriteResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_GpioWrite,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GpioReadResponse ClusterRunner_GpioReadRpc(cipher_unary_rpc_user_info_t *info, GpioReadRequest request)
{
    GpioReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_GpioRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AdcReadResponse ClusterRunner_AdcReadRpc(cipher_unary_rpc_user_info_t *info, AdcReadRequest request)
{
    AdcReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_AdcRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AdcReadAllResponse ClusterRunner_AdcReadAllRpc(cipher_unary_rpc_user_info_t *info, AdcReadAllRequest request)
{
    AdcReadAllResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_AdcReadAll,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutPowerEnableResponse ClusterRunner_DutPowerEnableRpc(cipher_unary_rpc_user_info_t *info, DutPowerEnableRequest request)
{
    DutPowerEnableResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_DutPowerEnable,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutPowerEnableResponse ClusterRunner_DutChargePowerEnableRpc(cipher_unary_rpc_user_info_t *info, DutPowerEnableRequest request)
{
    DutPowerEnableResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_DutChargePowerEnable,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutVoltageSetResponse ClusterRunner_DutVoltageSetRpc(cipher_unary_rpc_user_info_t *info, DutVoltageSetRequest request)
{
    DutVoltageSetResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_DutVoltageSet,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutCurrentReadResponse ClusterRunner_DutCurrentReadRpc(cipher_unary_rpc_user_info_t *info, DutCurrentReadRequest request)
{
    DutCurrentReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_DutCurrentRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutVoltageReadResponse ClusterRunner_DutVoltageReadRpc(cipher_unary_rpc_user_info_t *info, DutVoltageReadRequest request)
{
    DutVoltageReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_DutVoltageRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutPowerReadResponse ClusterRunner_DutPowerReadRpc(cipher_unary_rpc_user_info_t *info, DutPowerReadRequest request)
{
    DutPowerReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_DutPowerRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AltimeterReadResponse ClusterRunner_AltimeterReadRpc(cipher_unary_rpc_user_info_t *info, AltimeterReadRequest request)
{
    AltimeterReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_AltimeterRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AccelReadResponse ClusterRunner_AccelReadRpc(cipher_unary_rpc_user_info_t *info, AccelReadRequest request)
{
    AccelReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_AccelRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AccelReadMaxResponse ClusterRunner_AccelReadMaxForceRpc(cipher_unary_rpc_user_info_t *info, AccelReadMaxRequest request)
{
    AccelReadMaxResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_AccelReadMaxForce,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
EepromReadResponse ClusterRunner_EepromReadRpc(cipher_unary_rpc_user_info_t *info, EepromReadRequest request)
{
    EepromReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_EepromRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
EepromWriteResponse ClusterRunner_EepromWriteRpc(cipher_unary_rpc_user_info_t *info, EepromWriteRequest request)
{
    EepromWriteResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_EepromWrite,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
ListFwFilesResponse ClusterRunner_ListFwFilesRpc(cipher_unary_rpc_user_info_t *info, ListFwFilesRequest request)
{
    ListFwFilesResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_ListFwFiles,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
UploadFwFileResponse ClusterRunner_UploadFwFileRpc(cipher_unary_rpc_user_info_t *info, UploadFwFileRequest request)
{
    UploadFwFileResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_UploadFwFile,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DeleteFwFileResponse ClusterRunner_DeleteFwFileRpc(cipher_unary_rpc_user_info_t *info, DeleteFwFileRequest request)
{
    DeleteFwFileResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_DeleteFwFile,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
FlashHexFileResponse ClusterRunner_FlashHexFileRpc(cipher_unary_rpc_user_info_t *info, FlashHexFileRequest request)
{
    FlashHexFileResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTERRUNNER_SERVICE_ID,
        .rpc_id = rpc_FlashHexFile,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}

static cipher_rpc_info_t clusterrunner_rpcs[] =
{
    {
        .id = rpc_HealthCheck,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "HealthCheck",
        .handler = HealthCheckRpcPrvHandler,
        .request_info = {
            .fields = HealthCheckRequest_fields,
            .encoded_size = HealthCheckRequest_size,
            .decoded_size = sizeof(HealthCheckRequest)
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
            .fields = GetRunnerInfoRequest_fields,
            .encoded_size = GetRunnerInfoRequest_size,
            .decoded_size = sizeof(GetRunnerInfoRequest)
        },
        .response_info = {
            .fields = GetRunnerInfoResponse_fields,
            .encoded_size = GetRunnerInfoResponse_size,
            .decoded_size = sizeof(GetRunnerInfoResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_Reset,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "Reset",
        .handler = ResetRpcPrvHandler,
        .request_info = {
            .fields = ResetRequest_fields,
            .encoded_size = ResetRequest_size,
            .decoded_size = sizeof(ResetRequest)
        },
        .response_info = {
            .fields = ResetResponse_fields,
            .encoded_size = ResetResponse_size,
            .decoded_size = sizeof(ResetResponse)
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
            .fields = DutPowerEnableRequest_fields,
            .encoded_size = DutPowerEnableRequest_size,
            .decoded_size = sizeof(DutPowerEnableRequest)
        },
        .response_info = {
            .fields = DutPowerEnableResponse_fields,
            .encoded_size = DutPowerEnableResponse_size,
            .decoded_size = sizeof(DutPowerEnableResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_DutChargePowerEnable,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "DutChargePowerEnable",
        .handler = DutChargePowerEnableRpcPrvHandler,
        .request_info = {
            .fields = DutPowerEnableRequest_fields,
            .encoded_size = DutPowerEnableRequest_size,
            .decoded_size = sizeof(DutPowerEnableRequest)
        },
        .response_info = {
            .fields = DutPowerEnableResponse_fields,
            .encoded_size = DutPowerEnableResponse_size,
            .decoded_size = sizeof(DutPowerEnableResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_DutVoltageSet,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "DutVoltageSet",
        .handler = DutVoltageSetRpcPrvHandler,
        .request_info = {
            .fields = DutVoltageSetRequest_fields,
            .encoded_size = DutVoltageSetRequest_size,
            .decoded_size = sizeof(DutVoltageSetRequest)
        },
        .response_info = {
            .fields = DutVoltageSetResponse_fields,
            .encoded_size = DutVoltageSetResponse_size,
            .decoded_size = sizeof(DutVoltageSetResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_DutCurrentRead,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "DutCurrentRead",
        .handler = DutCurrentReadRpcPrvHandler,
        .request_info = {
            .fields = DutCurrentReadRequest_fields,
            .encoded_size = DutCurrentReadRequest_size,
            .decoded_size = sizeof(DutCurrentReadRequest)
        },
        .response_info = {
            .fields = DutCurrentReadResponse_fields,
            .encoded_size = DutCurrentReadResponse_size,
            .decoded_size = sizeof(DutCurrentReadResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_DutVoltageRead,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "DutVoltageRead",
        .handler = DutVoltageReadRpcPrvHandler,
        .request_info = {
            .fields = DutVoltageReadRequest_fields,
            .encoded_size = DutVoltageReadRequest_size,
            .decoded_size = sizeof(DutVoltageReadRequest)
        },
        .response_info = {
            .fields = DutVoltageReadResponse_fields,
            .encoded_size = DutVoltageReadResponse_size,
            .decoded_size = sizeof(DutVoltageReadResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_DutPowerRead,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "DutPowerRead",
        .handler = DutPowerReadRpcPrvHandler,
        .request_info = {
            .fields = DutPowerReadRequest_fields,
            .encoded_size = DutPowerReadRequest_size,
            .decoded_size = sizeof(DutPowerReadRequest)
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
            .fields = AltimeterReadRequest_fields,
            .encoded_size = AltimeterReadRequest_size,
            .decoded_size = sizeof(AltimeterReadRequest)
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
            .fields = AccelReadRequest_fields,
            .encoded_size = AccelReadRequest_size,
            .decoded_size = sizeof(AccelReadRequest)
        },
        .response_info = {
            .fields = AccelReadResponse_fields,
            .encoded_size = AccelReadResponse_size,
            .decoded_size = sizeof(AccelReadResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_AccelReadMaxForce,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "AccelReadMaxForce",
        .handler = AccelReadMaxForceRpcPrvHandler,
        .request_info = {
            .fields = AccelReadMaxRequest_fields,
            .encoded_size = AccelReadMaxRequest_size,
            .decoded_size = sizeof(AccelReadMaxRequest)
        },
        .response_info = {
            .fields = AccelReadMaxResponse_fields,
            .encoded_size = AccelReadMaxResponse_size,
            .decoded_size = sizeof(AccelReadMaxResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_EepromRead,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "EepromRead",
        .handler = EepromReadRpcPrvHandler,
        .request_info = {
            .fields = EepromReadRequest_fields,
            .encoded_size = EepromReadRequest_size,
            .decoded_size = sizeof(EepromReadRequest)
        },
        .response_info = {
            .fields = EepromReadResponse_fields,
            .encoded_size = EepromReadResponse_size,
            .decoded_size = sizeof(EepromReadResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_EepromWrite,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "EepromWrite",
        .handler = EepromWriteRpcPrvHandler,
        .request_info = {
            .fields = EepromWriteRequest_fields,
            .encoded_size = EepromWriteRequest_size,
            .decoded_size = sizeof(EepromWriteRequest)
        },
        .response_info = {
            .fields = EepromWriteResponse_fields,
            .encoded_size = EepromWriteResponse_size,
            .decoded_size = sizeof(EepromWriteResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_ListFwFiles,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "ListFwFiles",
        .handler = ListFwFilesRpcPrvHandler,
        .request_info = {
            .fields = ListFwFilesRequest_fields,
            .encoded_size = ListFwFilesRequest_size,
            .decoded_size = sizeof(ListFwFilesRequest)
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
        .id = rpc_FlashHexFile,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "FlashHexFile",
        .handler = FlashHexFileRpcPrvHandler,
        .request_info = {
            .fields = FlashHexFileRequest_fields,
            .encoded_size = FlashHexFileRequest_size,
            .decoded_size = sizeof(FlashHexFileRequest)
        },
        .response_info = {
            .fields = FlashHexFileResponse_fields,
            .encoded_size = FlashHexFileResponse_size,
            .decoded_size = sizeof(FlashHexFileResponse)
        },
        .supports_parallelism = true,
    },
};

static cipher_service_info_t clusterrunner_service =
{
    .id = CLUSTERRUNNER_SERVICE_ID,
    .name = "ClusterRunner",
    .max_hops = 1,
    .rpcs = clusterrunner_rpcs,
    .num_rpcs = ARRAY_SIZE(clusterrunner_rpcs),
};

cipher_service_info_t *get_clusterrunnerservice_info(void)
{
    return &clusterrunner_service;
}
