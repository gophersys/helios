#include "mtib_posix.cipher.h"

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/iface/iface.h>
#include <corekinect/cipher/cipher.h>

// Protobuf includes
#include "mtib_posix.pb.h"

LOG_MODULE_REGISTER(mtibposix);

#define MTIBPOSIX_SERVICE_ID 1

typedef enum
{
    rpc_HealthCheck = 1,
    rpc_GpioConfig = 2,
    rpc_GpioWrite = 3,
    rpc_GpioRead = 4,
    rpc_AdcRead = 5,
    rpc_AdcReadAll = 6,
    rpc_DutPowerEnable = 7,
    rpc_DutChargePowerEnable = 8,
    rpc_DutVoltageSet = 9,
    rpc_DutCurrentRead = 10,
    rpc_DutVoltageRead = 11,
    rpc_DutPowerRead = 12,
    rpc_AltimeterRead = 13,
    rpc_AccelRead = 14,
    rpc_AccelReadMaxForce = 15,
    rpc_EepromRead = 16,
    rpc_EepromWrite = 17,
    rpc_ListFwFiles = 18,
    rpc_UploadFwFile = 19,
    rpc_DeleteFwFile = 20,
    rpc_FlashHexFile = 21,
} MtibPosix_rpc;

// Server side
static bool MtibPosix_HealthCheckHandlerImplemented = true;
__attribute__((weak)) HealthCheckResponse MtibPosix_HealthCheckHandler(HealthCheckRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_HealthCheckHandlerImplemented = false;
    HealthCheckResponse response  = {0};
    return response ;
}

cipher_rpc_err_t HealthCheckRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((HealthCheckResponse *)response ) = MtibPosix_HealthCheckHandler(*((HealthCheckRequest *)request));
    return MtibPosix_HealthCheckHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_GpioConfigHandlerImplemented = true;
__attribute__((weak)) GpioConfigResponse MtibPosix_GpioConfigHandler(GpioConfigRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_GpioConfigHandlerImplemented = false;
    GpioConfigResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GpioConfigRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GpioConfigResponse *)response ) = MtibPosix_GpioConfigHandler(*((GpioConfigRequest *)request));
    return MtibPosix_GpioConfigHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_GpioWriteHandlerImplemented = true;
__attribute__((weak)) GpioWriteResponse MtibPosix_GpioWriteHandler(GpioWriteRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_GpioWriteHandlerImplemented = false;
    GpioWriteResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GpioWriteRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GpioWriteResponse *)response ) = MtibPosix_GpioWriteHandler(*((GpioWriteRequest *)request));
    return MtibPosix_GpioWriteHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_GpioReadHandlerImplemented = true;
__attribute__((weak)) GpioReadResponse MtibPosix_GpioReadHandler(GpioReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_GpioReadHandlerImplemented = false;
    GpioReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GpioReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GpioReadResponse *)response ) = MtibPosix_GpioReadHandler(*((GpioReadRequest *)request));
    return MtibPosix_GpioReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_AdcReadHandlerImplemented = true;
__attribute__((weak)) AdcReadResponse MtibPosix_AdcReadHandler(AdcReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_AdcReadHandlerImplemented = false;
    AdcReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AdcReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AdcReadResponse *)response ) = MtibPosix_AdcReadHandler(*((AdcReadRequest *)request));
    return MtibPosix_AdcReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_AdcReadAllHandlerImplemented = true;
__attribute__((weak)) AdcReadAllResponse MtibPosix_AdcReadAllHandler(AdcReadAllRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_AdcReadAllHandlerImplemented = false;
    AdcReadAllResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AdcReadAllRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AdcReadAllResponse *)response ) = MtibPosix_AdcReadAllHandler(*((AdcReadAllRequest *)request));
    return MtibPosix_AdcReadAllHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_DutPowerEnableHandlerImplemented = true;
__attribute__((weak)) DutPowerEnableResponse MtibPosix_DutPowerEnableHandler(DutPowerEnableRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_DutPowerEnableHandlerImplemented = false;
    DutPowerEnableResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutPowerEnableRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutPowerEnableResponse *)response ) = MtibPosix_DutPowerEnableHandler(*((DutPowerEnableRequest *)request));
    return MtibPosix_DutPowerEnableHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_DutChargePowerEnableHandlerImplemented = true;
__attribute__((weak)) DutPowerEnableResponse MtibPosix_DutChargePowerEnableHandler(DutPowerEnableRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_DutChargePowerEnableHandlerImplemented = false;
    DutPowerEnableResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutChargePowerEnableRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutPowerEnableResponse *)response ) = MtibPosix_DutChargePowerEnableHandler(*((DutPowerEnableRequest *)request));
    return MtibPosix_DutChargePowerEnableHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_DutVoltageSetHandlerImplemented = true;
__attribute__((weak)) DutVoltageSetResponse MtibPosix_DutVoltageSetHandler(DutVoltageSetRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_DutVoltageSetHandlerImplemented = false;
    DutVoltageSetResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutVoltageSetRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutVoltageSetResponse *)response ) = MtibPosix_DutVoltageSetHandler(*((DutVoltageSetRequest *)request));
    return MtibPosix_DutVoltageSetHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_DutCurrentReadHandlerImplemented = true;
__attribute__((weak)) DutCurrentReadResponse MtibPosix_DutCurrentReadHandler(DutCurrentReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_DutCurrentReadHandlerImplemented = false;
    DutCurrentReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutCurrentReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutCurrentReadResponse *)response ) = MtibPosix_DutCurrentReadHandler(*((DutCurrentReadRequest *)request));
    return MtibPosix_DutCurrentReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_DutVoltageReadHandlerImplemented = true;
__attribute__((weak)) DutVoltageReadResponse MtibPosix_DutVoltageReadHandler(DutVoltageReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_DutVoltageReadHandlerImplemented = false;
    DutVoltageReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutVoltageReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutVoltageReadResponse *)response ) = MtibPosix_DutVoltageReadHandler(*((DutVoltageReadRequest *)request));
    return MtibPosix_DutVoltageReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_DutPowerReadHandlerImplemented = true;
__attribute__((weak)) DutPowerReadResponse MtibPosix_DutPowerReadHandler(DutPowerReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_DutPowerReadHandlerImplemented = false;
    DutPowerReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutPowerReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutPowerReadResponse *)response ) = MtibPosix_DutPowerReadHandler(*((DutPowerReadRequest *)request));
    return MtibPosix_DutPowerReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_AltimeterReadHandlerImplemented = true;
__attribute__((weak)) AltimeterReadResponse MtibPosix_AltimeterReadHandler(AltimeterReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_AltimeterReadHandlerImplemented = false;
    AltimeterReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AltimeterReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AltimeterReadResponse *)response ) = MtibPosix_AltimeterReadHandler(*((AltimeterReadRequest *)request));
    return MtibPosix_AltimeterReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_AccelReadHandlerImplemented = true;
__attribute__((weak)) AccelReadResponse MtibPosix_AccelReadHandler(AccelReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_AccelReadHandlerImplemented = false;
    AccelReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AccelReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AccelReadResponse *)response ) = MtibPosix_AccelReadHandler(*((AccelReadRequest *)request));
    return MtibPosix_AccelReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_AccelReadMaxForceHandlerImplemented = true;
__attribute__((weak)) AccelReadMaxResponse MtibPosix_AccelReadMaxForceHandler(AccelReadMaxRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_AccelReadMaxForceHandlerImplemented = false;
    AccelReadMaxResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AccelReadMaxForceRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AccelReadMaxResponse *)response ) = MtibPosix_AccelReadMaxForceHandler(*((AccelReadMaxRequest *)request));
    return MtibPosix_AccelReadMaxForceHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_EepromReadHandlerImplemented = true;
__attribute__((weak)) EepromReadResponse MtibPosix_EepromReadHandler(EepromReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_EepromReadHandlerImplemented = false;
    EepromReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t EepromReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((EepromReadResponse *)response ) = MtibPosix_EepromReadHandler(*((EepromReadRequest *)request));
    return MtibPosix_EepromReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_EepromWriteHandlerImplemented = true;
__attribute__((weak)) EepromWriteResponse MtibPosix_EepromWriteHandler(EepromWriteRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_EepromWriteHandlerImplemented = false;
    EepromWriteResponse response  = {0};
    return response ;
}

cipher_rpc_err_t EepromWriteRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((EepromWriteResponse *)response ) = MtibPosix_EepromWriteHandler(*((EepromWriteRequest *)request));
    return MtibPosix_EepromWriteHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_ListFwFilesHandlerImplemented = true;
__attribute__((weak)) ListFwFilesResponse MtibPosix_ListFwFilesHandler(ListFwFilesRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_ListFwFilesHandlerImplemented = false;
    ListFwFilesResponse response  = {0};
    return response ;
}

cipher_rpc_err_t ListFwFilesRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((ListFwFilesResponse *)response ) = MtibPosix_ListFwFilesHandler(*((ListFwFilesRequest *)request));
    return MtibPosix_ListFwFilesHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_UploadFwFileHandlerImplemented = true;
__attribute__((weak)) UploadFwFileResponse MtibPosix_UploadFwFileHandler(UploadFwFileRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_UploadFwFileHandlerImplemented = false;
    UploadFwFileResponse response  = {0};
    return response ;
}

cipher_rpc_err_t UploadFwFileRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((UploadFwFileResponse *)response ) = MtibPosix_UploadFwFileHandler(*((UploadFwFileRequest *)request));
    return MtibPosix_UploadFwFileHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_DeleteFwFileHandlerImplemented = true;
__attribute__((weak)) DeleteFwFileResponse MtibPosix_DeleteFwFileHandler(DeleteFwFileRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_DeleteFwFileHandlerImplemented = false;
    DeleteFwFileResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DeleteFwFileRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DeleteFwFileResponse *)response ) = MtibPosix_DeleteFwFileHandler(*((DeleteFwFileRequest *)request));
    return MtibPosix_DeleteFwFileHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibPosix_FlashHexFileHandlerImplemented = true;
__attribute__((weak)) FlashHexFileResponse MtibPosix_FlashHexFileHandler(FlashHexFileRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibPosix_FlashHexFileHandlerImplemented = false;
    FlashHexFileResponse response  = {0};
    return response ;
}

cipher_rpc_err_t FlashHexFileRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((FlashHexFileResponse *)response ) = MtibPosix_FlashHexFileHandler(*((FlashHexFileRequest *)request));
    return MtibPosix_FlashHexFileHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Client side
HealthCheckResponse MtibPosix_HealthCheckRpc(cipher_unary_rpc_user_info_t *info, HealthCheckRequest request)
{
    HealthCheckResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_HealthCheck,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GpioConfigResponse MtibPosix_GpioConfigRpc(cipher_unary_rpc_user_info_t *info, GpioConfigRequest request)
{
    GpioConfigResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_GpioConfig,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GpioWriteResponse MtibPosix_GpioWriteRpc(cipher_unary_rpc_user_info_t *info, GpioWriteRequest request)
{
    GpioWriteResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_GpioWrite,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GpioReadResponse MtibPosix_GpioReadRpc(cipher_unary_rpc_user_info_t *info, GpioReadRequest request)
{
    GpioReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_GpioRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AdcReadResponse MtibPosix_AdcReadRpc(cipher_unary_rpc_user_info_t *info, AdcReadRequest request)
{
    AdcReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_AdcRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AdcReadAllResponse MtibPosix_AdcReadAllRpc(cipher_unary_rpc_user_info_t *info, AdcReadAllRequest request)
{
    AdcReadAllResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_AdcReadAll,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutPowerEnableResponse MtibPosix_DutPowerEnableRpc(cipher_unary_rpc_user_info_t *info, DutPowerEnableRequest request)
{
    DutPowerEnableResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_DutPowerEnable,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutPowerEnableResponse MtibPosix_DutChargePowerEnableRpc(cipher_unary_rpc_user_info_t *info, DutPowerEnableRequest request)
{
    DutPowerEnableResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_DutChargePowerEnable,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutVoltageSetResponse MtibPosix_DutVoltageSetRpc(cipher_unary_rpc_user_info_t *info, DutVoltageSetRequest request)
{
    DutVoltageSetResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_DutVoltageSet,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutCurrentReadResponse MtibPosix_DutCurrentReadRpc(cipher_unary_rpc_user_info_t *info, DutCurrentReadRequest request)
{
    DutCurrentReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_DutCurrentRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutVoltageReadResponse MtibPosix_DutVoltageReadRpc(cipher_unary_rpc_user_info_t *info, DutVoltageReadRequest request)
{
    DutVoltageReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_DutVoltageRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutPowerReadResponse MtibPosix_DutPowerReadRpc(cipher_unary_rpc_user_info_t *info, DutPowerReadRequest request)
{
    DutPowerReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_DutPowerRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AltimeterReadResponse MtibPosix_AltimeterReadRpc(cipher_unary_rpc_user_info_t *info, AltimeterReadRequest request)
{
    AltimeterReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_AltimeterRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AccelReadResponse MtibPosix_AccelReadRpc(cipher_unary_rpc_user_info_t *info, AccelReadRequest request)
{
    AccelReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_AccelRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AccelReadMaxResponse MtibPosix_AccelReadMaxForceRpc(cipher_unary_rpc_user_info_t *info, AccelReadMaxRequest request)
{
    AccelReadMaxResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_AccelReadMaxForce,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
EepromReadResponse MtibPosix_EepromReadRpc(cipher_unary_rpc_user_info_t *info, EepromReadRequest request)
{
    EepromReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_EepromRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
EepromWriteResponse MtibPosix_EepromWriteRpc(cipher_unary_rpc_user_info_t *info, EepromWriteRequest request)
{
    EepromWriteResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_EepromWrite,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
ListFwFilesResponse MtibPosix_ListFwFilesRpc(cipher_unary_rpc_user_info_t *info, ListFwFilesRequest request)
{
    ListFwFilesResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_ListFwFiles,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
UploadFwFileResponse MtibPosix_UploadFwFileRpc(cipher_unary_rpc_user_info_t *info, UploadFwFileRequest request)
{
    UploadFwFileResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_UploadFwFile,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DeleteFwFileResponse MtibPosix_DeleteFwFileRpc(cipher_unary_rpc_user_info_t *info, DeleteFwFileRequest request)
{
    DeleteFwFileResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_DeleteFwFile,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
FlashHexFileResponse MtibPosix_FlashHexFileRpc(cipher_unary_rpc_user_info_t *info, FlashHexFileRequest request)
{
    FlashHexFileResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBPOSIX_SERVICE_ID,
        .rpc_id = rpc_FlashHexFile,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}

static cipher_rpc_info_t mtibposix_rpcs[] =
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

static cipher_service_info_t mtibposix_service =
{
    .id = MTIBPOSIX_SERVICE_ID,
    .name = "MtibPosix",
    .max_hops = 1,
    .rpcs = mtibposix_rpcs,
    .num_rpcs = ARRAY_SIZE(mtibposix_rpcs),
};

cipher_service_info_t *get_mtibposixservice_info(void)
{
    return &mtibposix_service;
}
