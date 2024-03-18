#include "mtib-cs-pi.cipher.h"

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/iface/iface.h>
#include <corekinect/cipher/cipher.h>

// Protobuf includes
#include "mtib-cs-pi.pb.h"

LOG_MODULE_REGISTER(mtibcspi);

#define MTIBCSPI_SERVICE_ID 1

typedef enum
{
    rpc_GpioConfig = 1,
    rpc_GpioWrite = 2,
    rpc_GpioRead = 3,
    rpc_AdcRead = 4,
    rpc_AdcReadAll = 5,
    rpc_DutPowerEnable = 6,
    rpc_DutChargePowerEnable = 7,
    rpc_DutVoltageSet = 8,
    rpc_DutCurrentRead = 9,
    rpc_DutVoltageRead = 10,
    rpc_DutPowerRead = 11,
    rpc_AltimeterRead = 12,
    rpc_AccelRead = 13,
    rpc_AccelReadMaxForce = 14,
    rpc_EepromRead = 15,
    rpc_EepromWrite = 16,
    rpc_ListFwFiles = 17,
    rpc_UploadFwFile = 18,
    rpc_DeleteFwFile = 19,
    rpc_FlashHexFile = 20,
} MtibCsPi_rpc;

// Server side
static bool MtibCsPi_GpioConfigHandlerImplemented = true;
__attribute__((weak)) GpioConfigResponse MtibCsPi_GpioConfigHandler(GpioConfigRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_GpioConfigHandlerImplemented = false;
    GpioConfigResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GpioConfigRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GpioConfigResponse *)response ) = MtibCsPi_GpioConfigHandler(*((GpioConfigRequest *)request));
    return MtibCsPi_GpioConfigHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibCsPi_GpioWriteHandlerImplemented = true;
__attribute__((weak)) GpioWriteResponse MtibCsPi_GpioWriteHandler(GpioWriteRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_GpioWriteHandlerImplemented = false;
    GpioWriteResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GpioWriteRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GpioWriteResponse *)response ) = MtibCsPi_GpioWriteHandler(*((GpioWriteRequest *)request));
    return MtibCsPi_GpioWriteHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibCsPi_GpioReadHandlerImplemented = true;
__attribute__((weak)) GpioReadResponse MtibCsPi_GpioReadHandler(GpioReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_GpioReadHandlerImplemented = false;
    GpioReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GpioReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GpioReadResponse *)response ) = MtibCsPi_GpioReadHandler(*((GpioReadRequest *)request));
    return MtibCsPi_GpioReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibCsPi_AdcReadHandlerImplemented = true;
__attribute__((weak)) AdcReadResponse MtibCsPi_AdcReadHandler(AdcReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_AdcReadHandlerImplemented = false;
    AdcReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AdcReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AdcReadResponse *)response ) = MtibCsPi_AdcReadHandler(*((AdcReadRequest *)request));
    return MtibCsPi_AdcReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibCsPi_AdcReadAllHandlerImplemented = true;
__attribute__((weak)) AdcReadAllResponse MtibCsPi_AdcReadAllHandler(AdcReadAllRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_AdcReadAllHandlerImplemented = false;
    AdcReadAllResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AdcReadAllRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AdcReadAllResponse *)response ) = MtibCsPi_AdcReadAllHandler(*((AdcReadAllRequest *)request));
    return MtibCsPi_AdcReadAllHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibCsPi_DutPowerEnableHandlerImplemented = true;
__attribute__((weak)) DutPowerEnableResponse MtibCsPi_DutPowerEnableHandler(DutPowerEnableRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_DutPowerEnableHandlerImplemented = false;
    DutPowerEnableResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutPowerEnableRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutPowerEnableResponse *)response ) = MtibCsPi_DutPowerEnableHandler(*((DutPowerEnableRequest *)request));
    return MtibCsPi_DutPowerEnableHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibCsPi_DutChargePowerEnableHandlerImplemented = true;
__attribute__((weak)) DutPowerEnableResponse MtibCsPi_DutChargePowerEnableHandler(DutPowerEnableRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_DutChargePowerEnableHandlerImplemented = false;
    DutPowerEnableResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutChargePowerEnableRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutPowerEnableResponse *)response ) = MtibCsPi_DutChargePowerEnableHandler(*((DutPowerEnableRequest *)request));
    return MtibCsPi_DutChargePowerEnableHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibCsPi_DutVoltageSetHandlerImplemented = true;
__attribute__((weak)) DutVoltageSetResponse MtibCsPi_DutVoltageSetHandler(DutVoltageSetRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_DutVoltageSetHandlerImplemented = false;
    DutVoltageSetResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutVoltageSetRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutVoltageSetResponse *)response ) = MtibCsPi_DutVoltageSetHandler(*((DutVoltageSetRequest *)request));
    return MtibCsPi_DutVoltageSetHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibCsPi_DutCurrentReadHandlerImplemented = true;
__attribute__((weak)) DutCurrentReadResponse MtibCsPi_DutCurrentReadHandler(DutCurrentReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_DutCurrentReadHandlerImplemented = false;
    DutCurrentReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutCurrentReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutCurrentReadResponse *)response ) = MtibCsPi_DutCurrentReadHandler(*((DutCurrentReadRequest *)request));
    return MtibCsPi_DutCurrentReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibCsPi_DutVoltageReadHandlerImplemented = true;
__attribute__((weak)) DutVoltageReadResponse MtibCsPi_DutVoltageReadHandler(DutVoltageReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_DutVoltageReadHandlerImplemented = false;
    DutVoltageReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutVoltageReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutVoltageReadResponse *)response ) = MtibCsPi_DutVoltageReadHandler(*((DutVoltageReadRequest *)request));
    return MtibCsPi_DutVoltageReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibCsPi_DutPowerReadHandlerImplemented = true;
__attribute__((weak)) DutPowerReadResponse MtibCsPi_DutPowerReadHandler(DutPowerReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_DutPowerReadHandlerImplemented = false;
    DutPowerReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutPowerReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutPowerReadResponse *)response ) = MtibCsPi_DutPowerReadHandler(*((DutPowerReadRequest *)request));
    return MtibCsPi_DutPowerReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibCsPi_AltimeterReadHandlerImplemented = true;
__attribute__((weak)) AltimeterReadResponse MtibCsPi_AltimeterReadHandler(AltimeterReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_AltimeterReadHandlerImplemented = false;
    AltimeterReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AltimeterReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AltimeterReadResponse *)response ) = MtibCsPi_AltimeterReadHandler(*((AltimeterReadRequest *)request));
    return MtibCsPi_AltimeterReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibCsPi_AccelReadHandlerImplemented = true;
__attribute__((weak)) AccelReadResponse MtibCsPi_AccelReadHandler(AccelReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_AccelReadHandlerImplemented = false;
    AccelReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AccelReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AccelReadResponse *)response ) = MtibCsPi_AccelReadHandler(*((AccelReadRequest *)request));
    return MtibCsPi_AccelReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibCsPi_AccelReadMaxForceHandlerImplemented = true;
__attribute__((weak)) AccelReadMaxResponse MtibCsPi_AccelReadMaxForceHandler(AccelReadMaxRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_AccelReadMaxForceHandlerImplemented = false;
    AccelReadMaxResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AccelReadMaxForceRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AccelReadMaxResponse *)response ) = MtibCsPi_AccelReadMaxForceHandler(*((AccelReadMaxRequest *)request));
    return MtibCsPi_AccelReadMaxForceHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibCsPi_EepromReadHandlerImplemented = true;
__attribute__((weak)) EepromReadResponse MtibCsPi_EepromReadHandler(EepromReadRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_EepromReadHandlerImplemented = false;
    EepromReadResponse response  = {0};
    return response ;
}

cipher_rpc_err_t EepromReadRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((EepromReadResponse *)response ) = MtibCsPi_EepromReadHandler(*((EepromReadRequest *)request));
    return MtibCsPi_EepromReadHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibCsPi_EepromWriteHandlerImplemented = true;
__attribute__((weak)) EepromWriteResponse MtibCsPi_EepromWriteHandler(EepromWriteRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_EepromWriteHandlerImplemented = false;
    EepromWriteResponse response  = {0};
    return response ;
}

cipher_rpc_err_t EepromWriteRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((EepromWriteResponse *)response ) = MtibCsPi_EepromWriteHandler(*((EepromWriteRequest *)request));
    return MtibCsPi_EepromWriteHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibCsPi_ListFwFilesHandlerImplemented = true;
__attribute__((weak)) ListFwFilesResponse MtibCsPi_ListFwFilesHandler(ListFwFilesRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_ListFwFilesHandlerImplemented = false;
    ListFwFilesResponse response  = {0};
    return response ;
}

cipher_rpc_err_t ListFwFilesRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((ListFwFilesResponse *)response ) = MtibCsPi_ListFwFilesHandler(*((ListFwFilesRequest *)request));
    return MtibCsPi_ListFwFilesHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibCsPi_UploadFwFileHandlerImplemented = true;
__attribute__((weak)) UploadFwFileResponse MtibCsPi_UploadFwFileHandler(UploadFwFileRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_UploadFwFileHandlerImplemented = false;
    UploadFwFileResponse response  = {0};
    return response ;
}

cipher_rpc_err_t UploadFwFileRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((UploadFwFileResponse *)response ) = MtibCsPi_UploadFwFileHandler(*((UploadFwFileRequest *)request));
    return MtibCsPi_UploadFwFileHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibCsPi_DeleteFwFileHandlerImplemented = true;
__attribute__((weak)) DeleteFwFileResponse MtibCsPi_DeleteFwFileHandler(DeleteFwFileRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_DeleteFwFileHandlerImplemented = false;
    DeleteFwFileResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DeleteFwFileRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DeleteFwFileResponse *)response ) = MtibCsPi_DeleteFwFileHandler(*((DeleteFwFileRequest *)request));
    return MtibCsPi_DeleteFwFileHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibCsPi_FlashHexFileHandlerImplemented = true;
__attribute__((weak)) FlashHexFileResponse MtibCsPi_FlashHexFileHandler(FlashHexFileRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibCsPi_FlashHexFileHandlerImplemented = false;
    FlashHexFileResponse response  = {0};
    return response ;
}

cipher_rpc_err_t FlashHexFileRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((FlashHexFileResponse *)response ) = MtibCsPi_FlashHexFileHandler(*((FlashHexFileRequest *)request));
    return MtibCsPi_FlashHexFileHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Client side
GpioConfigResponse MtibCsPi_GpioConfigRpc(cipher_unary_rpc_user_info_t *info, GpioConfigRequest request)
{
    GpioConfigResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_GpioConfig,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GpioWriteResponse MtibCsPi_GpioWriteRpc(cipher_unary_rpc_user_info_t *info, GpioWriteRequest request)
{
    GpioWriteResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_GpioWrite,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GpioReadResponse MtibCsPi_GpioReadRpc(cipher_unary_rpc_user_info_t *info, GpioReadRequest request)
{
    GpioReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_GpioRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AdcReadResponse MtibCsPi_AdcReadRpc(cipher_unary_rpc_user_info_t *info, AdcReadRequest request)
{
    AdcReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_AdcRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AdcReadAllResponse MtibCsPi_AdcReadAllRpc(cipher_unary_rpc_user_info_t *info, AdcReadAllRequest request)
{
    AdcReadAllResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_AdcReadAll,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutPowerEnableResponse MtibCsPi_DutPowerEnableRpc(cipher_unary_rpc_user_info_t *info, DutPowerEnableRequest request)
{
    DutPowerEnableResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_DutPowerEnable,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutPowerEnableResponse MtibCsPi_DutChargePowerEnableRpc(cipher_unary_rpc_user_info_t *info, DutPowerEnableRequest request)
{
    DutPowerEnableResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_DutChargePowerEnable,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutVoltageSetResponse MtibCsPi_DutVoltageSetRpc(cipher_unary_rpc_user_info_t *info, DutVoltageSetRequest request)
{
    DutVoltageSetResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_DutVoltageSet,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutCurrentReadResponse MtibCsPi_DutCurrentReadRpc(cipher_unary_rpc_user_info_t *info, DutCurrentReadRequest request)
{
    DutCurrentReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_DutCurrentRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutVoltageReadResponse MtibCsPi_DutVoltageReadRpc(cipher_unary_rpc_user_info_t *info, DutVoltageReadRequest request)
{
    DutVoltageReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_DutVoltageRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutPowerReadResponse MtibCsPi_DutPowerReadRpc(cipher_unary_rpc_user_info_t *info, DutPowerReadRequest request)
{
    DutPowerReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_DutPowerRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AltimeterReadResponse MtibCsPi_AltimeterReadRpc(cipher_unary_rpc_user_info_t *info, AltimeterReadRequest request)
{
    AltimeterReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_AltimeterRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AccelReadResponse MtibCsPi_AccelReadRpc(cipher_unary_rpc_user_info_t *info, AccelReadRequest request)
{
    AccelReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_AccelRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AccelReadMaxResponse MtibCsPi_AccelReadMaxForceRpc(cipher_unary_rpc_user_info_t *info, AccelReadMaxRequest request)
{
    AccelReadMaxResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_AccelReadMaxForce,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
EepromReadResponse MtibCsPi_EepromReadRpc(cipher_unary_rpc_user_info_t *info, EepromReadRequest request)
{
    EepromReadResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_EepromRead,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
EepromWriteResponse MtibCsPi_EepromWriteRpc(cipher_unary_rpc_user_info_t *info, EepromWriteRequest request)
{
    EepromWriteResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_EepromWrite,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
ListFwFilesResponse MtibCsPi_ListFwFilesRpc(cipher_unary_rpc_user_info_t *info, ListFwFilesRequest request)
{
    ListFwFilesResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_ListFwFiles,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
UploadFwFileResponse MtibCsPi_UploadFwFileRpc(cipher_unary_rpc_user_info_t *info, UploadFwFileRequest request)
{
    UploadFwFileResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_UploadFwFile,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DeleteFwFileResponse MtibCsPi_DeleteFwFileRpc(cipher_unary_rpc_user_info_t *info, DeleteFwFileRequest request)
{
    DeleteFwFileResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_DeleteFwFile,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
FlashHexFileResponse MtibCsPi_FlashHexFileRpc(cipher_unary_rpc_user_info_t *info, FlashHexFileRequest request)
{
    FlashHexFileResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCSPI_SERVICE_ID,
        .rpc_id = rpc_FlashHexFile,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}

static cipher_rpc_info_t mtibcspi_rpcs[] =
{
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

static cipher_service_info_t mtibcspi_service =
{
    .id = MTIBCSPI_SERVICE_ID,
    .name = "MtibCsPi",
    .max_hops = 1,
    .rpcs = mtibcspi_rpcs,
    .num_rpcs = ARRAY_SIZE(mtibcspi_rpcs),
};

cipher_service_info_t *get_mtibcspiservice_info(void)
{
    return &mtibcspi_service;
}
