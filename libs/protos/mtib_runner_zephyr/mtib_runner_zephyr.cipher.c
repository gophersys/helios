#include "mtib_runner_zephyr.cipher.h"

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/iface/iface.h>
#include <corekinect/cipher/cipher.h>

// Protobuf includes
#include "mtib_runner_zephyr.pb.h"

LOG_MODULE_REGISTER(mtibrunnerzephyr);

#define MTIBRUNNERZEPHYR_SERVICE_ID 1

typedef enum
{
    rpc_GpioConfigurePin = 1,
    rpc_GpioSetPin = 2,
    rpc_GpioReadPin = 3,
    rpc_AdcReadChannel = 4,
    rpc_AdcReadAllChannels = 5,
    rpc_DutEnablePower = 6,
    rpc_DutEnableCharger = 7,
    rpc_DutSetOutputVoltage = 8,
    rpc_Ina219ReadCurrent = 9,
    rpc_Ina219ReadVoltage = 10,
    rpc_Ina219ReadPower = 11,
    rpc_Bmp390ReadValues = 12,
    rpc_Lis2de12ReadValues = 13,
    rpc_Lis2de12ReadMaxForce = 14,
    rpc_EepromReadFromMem = 15,
    rpc_EepromWriteToMem = 16,
    rpc_UartPortEnable = 17,
    rpc_UartPortDisable = 18,
    rpc_SigmaToPiMessage = 19,
    rpc_PiToSigmaMessage = 20,
} MtibRunnerZephyr_rpc;

// Server side
static bool MtibRunnerZephyr_GpioConfigurePinHandlerImplemented = true;
__attribute__((weak)) GpioConfigurePinResponse MtibRunnerZephyr_GpioConfigurePinHandler(GpioConfigurePinRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_GpioConfigurePinHandlerImplemented = false;
    GpioConfigurePinResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GpioConfigurePinRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GpioConfigurePinResponse *)response ) = MtibRunnerZephyr_GpioConfigurePinHandler(*((GpioConfigurePinRequest *)request));
    return MtibRunnerZephyr_GpioConfigurePinHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerZephyr_GpioSetPinHandlerImplemented = true;
__attribute__((weak)) GpioSetPinResponse MtibRunnerZephyr_GpioSetPinHandler(GpioSetPinRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_GpioSetPinHandlerImplemented = false;
    GpioSetPinResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GpioSetPinRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GpioSetPinResponse *)response ) = MtibRunnerZephyr_GpioSetPinHandler(*((GpioSetPinRequest *)request));
    return MtibRunnerZephyr_GpioSetPinHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerZephyr_GpioReadPinHandlerImplemented = true;
__attribute__((weak)) GpioReadPinResponse MtibRunnerZephyr_GpioReadPinHandler(GpioReadPinRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_GpioReadPinHandlerImplemented = false;
    GpioReadPinResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GpioReadPinRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GpioReadPinResponse *)response ) = MtibRunnerZephyr_GpioReadPinHandler(*((GpioReadPinRequest *)request));
    return MtibRunnerZephyr_GpioReadPinHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerZephyr_AdcReadChannelHandlerImplemented = true;
__attribute__((weak)) AdcReadChannelResponse MtibRunnerZephyr_AdcReadChannelHandler(AdcReadChannelRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_AdcReadChannelHandlerImplemented = false;
    AdcReadChannelResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AdcReadChannelRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AdcReadChannelResponse *)response ) = MtibRunnerZephyr_AdcReadChannelHandler(*((AdcReadChannelRequest *)request));
    return MtibRunnerZephyr_AdcReadChannelHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerZephyr_AdcReadAllChannelsHandlerImplemented = true;
__attribute__((weak)) AdcReadAllChannelsResponse MtibRunnerZephyr_AdcReadAllChannelsHandler(AdcReadAllChannelsRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_AdcReadAllChannelsHandlerImplemented = false;
    AdcReadAllChannelsResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AdcReadAllChannelsRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AdcReadAllChannelsResponse *)response ) = MtibRunnerZephyr_AdcReadAllChannelsHandler(*((AdcReadAllChannelsRequest *)request));
    return MtibRunnerZephyr_AdcReadAllChannelsHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerZephyr_DutEnablePowerHandlerImplemented = true;
__attribute__((weak)) DutEnablePowerResponse MtibRunnerZephyr_DutEnablePowerHandler(DutEnablePowerRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_DutEnablePowerHandlerImplemented = false;
    DutEnablePowerResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutEnablePowerRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutEnablePowerResponse *)response ) = MtibRunnerZephyr_DutEnablePowerHandler(*((DutEnablePowerRequest *)request));
    return MtibRunnerZephyr_DutEnablePowerHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerZephyr_DutEnableChargerHandlerImplemented = true;
__attribute__((weak)) DutEnableChargerResponse MtibRunnerZephyr_DutEnableChargerHandler(DutEnableChargerRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_DutEnableChargerHandlerImplemented = false;
    DutEnableChargerResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutEnableChargerRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutEnableChargerResponse *)response ) = MtibRunnerZephyr_DutEnableChargerHandler(*((DutEnableChargerRequest *)request));
    return MtibRunnerZephyr_DutEnableChargerHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerZephyr_DutSetOutputVoltageHandlerImplemented = true;
__attribute__((weak)) DutSetOutputVoltageResponse MtibRunnerZephyr_DutSetOutputVoltageHandler(DutSetOutputVoltageRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_DutSetOutputVoltageHandlerImplemented = false;
    DutSetOutputVoltageResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutSetOutputVoltageRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutSetOutputVoltageResponse *)response ) = MtibRunnerZephyr_DutSetOutputVoltageHandler(*((DutSetOutputVoltageRequest *)request));
    return MtibRunnerZephyr_DutSetOutputVoltageHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerZephyr_Ina219ReadCurrentHandlerImplemented = true;
__attribute__((weak)) Ina219ReadCurrentResponse MtibRunnerZephyr_Ina219ReadCurrentHandler(Ina219ReadCurrentRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_Ina219ReadCurrentHandlerImplemented = false;
    Ina219ReadCurrentResponse response  = {0};
    return response ;
}

cipher_rpc_err_t Ina219ReadCurrentRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((Ina219ReadCurrentResponse *)response ) = MtibRunnerZephyr_Ina219ReadCurrentHandler(*((Ina219ReadCurrentRequest *)request));
    return MtibRunnerZephyr_Ina219ReadCurrentHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerZephyr_Ina219ReadVoltageHandlerImplemented = true;
__attribute__((weak)) Ina219ReadVoltageResponse MtibRunnerZephyr_Ina219ReadVoltageHandler(Ina219ReadVoltageRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_Ina219ReadVoltageHandlerImplemented = false;
    Ina219ReadVoltageResponse response  = {0};
    return response ;
}

cipher_rpc_err_t Ina219ReadVoltageRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((Ina219ReadVoltageResponse *)response ) = MtibRunnerZephyr_Ina219ReadVoltageHandler(*((Ina219ReadVoltageRequest *)request));
    return MtibRunnerZephyr_Ina219ReadVoltageHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerZephyr_Ina219ReadPowerHandlerImplemented = true;
__attribute__((weak)) Ina219ReadPowerResponse MtibRunnerZephyr_Ina219ReadPowerHandler(Ina219ReadPowerRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_Ina219ReadPowerHandlerImplemented = false;
    Ina219ReadPowerResponse response  = {0};
    return response ;
}

cipher_rpc_err_t Ina219ReadPowerRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((Ina219ReadPowerResponse *)response ) = MtibRunnerZephyr_Ina219ReadPowerHandler(*((Ina219ReadPowerRequest *)request));
    return MtibRunnerZephyr_Ina219ReadPowerHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerZephyr_Bmp390ReadValuesHandlerImplemented = true;
__attribute__((weak)) Bmp390ReadValuesResponse MtibRunnerZephyr_Bmp390ReadValuesHandler(Bmp390ReadValuesRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_Bmp390ReadValuesHandlerImplemented = false;
    Bmp390ReadValuesResponse response  = {0};
    return response ;
}

cipher_rpc_err_t Bmp390ReadValuesRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((Bmp390ReadValuesResponse *)response ) = MtibRunnerZephyr_Bmp390ReadValuesHandler(*((Bmp390ReadValuesRequest *)request));
    return MtibRunnerZephyr_Bmp390ReadValuesHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerZephyr_Lis2de12ReadValuesHandlerImplemented = true;
__attribute__((weak)) Lis2de12ReadValuesResponse MtibRunnerZephyr_Lis2de12ReadValuesHandler(Lis2de12ReadValuesRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_Lis2de12ReadValuesHandlerImplemented = false;
    Lis2de12ReadValuesResponse response  = {0};
    return response ;
}

cipher_rpc_err_t Lis2de12ReadValuesRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((Lis2de12ReadValuesResponse *)response ) = MtibRunnerZephyr_Lis2de12ReadValuesHandler(*((Lis2de12ReadValuesRequest *)request));
    return MtibRunnerZephyr_Lis2de12ReadValuesHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerZephyr_Lis2de12ReadMaxForceHandlerImplemented = true;
__attribute__((weak)) Lis2de12ReadMaxForceResponse MtibRunnerZephyr_Lis2de12ReadMaxForceHandler(Lis2de12ReadMaxForceRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_Lis2de12ReadMaxForceHandlerImplemented = false;
    Lis2de12ReadMaxForceResponse response  = {0};
    return response ;
}

cipher_rpc_err_t Lis2de12ReadMaxForceRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((Lis2de12ReadMaxForceResponse *)response ) = MtibRunnerZephyr_Lis2de12ReadMaxForceHandler(*((Lis2de12ReadMaxForceRequest *)request));
    return MtibRunnerZephyr_Lis2de12ReadMaxForceHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerZephyr_EepromReadFromMemHandlerImplemented = true;
__attribute__((weak)) EepromReadFromMemResponse MtibRunnerZephyr_EepromReadFromMemHandler(EepromReadFromMemRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_EepromReadFromMemHandlerImplemented = false;
    EepromReadFromMemResponse response  = {0};
    return response ;
}

cipher_rpc_err_t EepromReadFromMemRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((EepromReadFromMemResponse *)response ) = MtibRunnerZephyr_EepromReadFromMemHandler(*((EepromReadFromMemRequest *)request));
    return MtibRunnerZephyr_EepromReadFromMemHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerZephyr_EepromWriteToMemHandlerImplemented = true;
__attribute__((weak)) EepromWriteToMemResponse MtibRunnerZephyr_EepromWriteToMemHandler(EepromWriteToMemRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_EepromWriteToMemHandlerImplemented = false;
    EepromWriteToMemResponse response  = {0};
    return response ;
}

cipher_rpc_err_t EepromWriteToMemRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((EepromWriteToMemResponse *)response ) = MtibRunnerZephyr_EepromWriteToMemHandler(*((EepromWriteToMemRequest *)request));
    return MtibRunnerZephyr_EepromWriteToMemHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerZephyr_UartPortEnableHandlerImplemented = true;
__attribute__((weak)) UartPortStateChangeResponse MtibRunnerZephyr_UartPortEnableHandler(UartPortStateChangeRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_UartPortEnableHandlerImplemented = false;
    UartPortStateChangeResponse response  = {0};
    return response ;
}

cipher_rpc_err_t UartPortEnableRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((UartPortStateChangeResponse *)response ) = MtibRunnerZephyr_UartPortEnableHandler(*((UartPortStateChangeRequest *)request));
    return MtibRunnerZephyr_UartPortEnableHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerZephyr_UartPortDisableHandlerImplemented = true;
__attribute__((weak)) UartPortStateChangeResponse MtibRunnerZephyr_UartPortDisableHandler(UartPortStateChangeRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_UartPortDisableHandlerImplemented = false;
    UartPortStateChangeResponse response  = {0};
    return response ;
}

cipher_rpc_err_t UartPortDisableRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((UartPortStateChangeResponse *)response ) = MtibRunnerZephyr_UartPortDisableHandler(*((UartPortStateChangeRequest *)request));
    return MtibRunnerZephyr_UartPortDisableHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerZephyr_SigmaToPiMessageHandlerImplemented = true;
__attribute__((weak)) UartMessageResponse MtibRunnerZephyr_SigmaToPiMessageHandler(UartMessageRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_SigmaToPiMessageHandlerImplemented = false;
    UartMessageResponse response  = {0};
    return response ;
}

cipher_rpc_err_t SigmaToPiMessageRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((UartMessageResponse *)response ) = MtibRunnerZephyr_SigmaToPiMessageHandler(*((UartMessageRequest *)request));
    return MtibRunnerZephyr_SigmaToPiMessageHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibRunnerZephyr_PiToSigmaMessageHandlerImplemented = true;
__attribute__((weak)) UartMessageResponse MtibRunnerZephyr_PiToSigmaMessageHandler(UartMessageRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibRunnerZephyr_PiToSigmaMessageHandlerImplemented = false;
    UartMessageResponse response  = {0};
    return response ;
}

cipher_rpc_err_t PiToSigmaMessageRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((UartMessageResponse *)response ) = MtibRunnerZephyr_PiToSigmaMessageHandler(*((UartMessageRequest *)request));
    return MtibRunnerZephyr_PiToSigmaMessageHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Client side
GpioConfigurePinResponse MtibRunnerZephyr_GpioConfigurePinRpc(cipher_unary_rpc_user_info_t *info, GpioConfigurePinRequest request)
{
    GpioConfigurePinResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_GpioConfigurePin,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GpioSetPinResponse MtibRunnerZephyr_GpioSetPinRpc(cipher_unary_rpc_user_info_t *info, GpioSetPinRequest request)
{
    GpioSetPinResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_GpioSetPin,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GpioReadPinResponse MtibRunnerZephyr_GpioReadPinRpc(cipher_unary_rpc_user_info_t *info, GpioReadPinRequest request)
{
    GpioReadPinResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_GpioReadPin,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AdcReadChannelResponse MtibRunnerZephyr_AdcReadChannelRpc(cipher_unary_rpc_user_info_t *info, AdcReadChannelRequest request)
{
    AdcReadChannelResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_AdcReadChannel,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AdcReadAllChannelsResponse MtibRunnerZephyr_AdcReadAllChannelsRpc(cipher_unary_rpc_user_info_t *info, AdcReadAllChannelsRequest request)
{
    AdcReadAllChannelsResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_AdcReadAllChannels,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutEnablePowerResponse MtibRunnerZephyr_DutEnablePowerRpc(cipher_unary_rpc_user_info_t *info, DutEnablePowerRequest request)
{
    DutEnablePowerResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_DutEnablePower,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutEnableChargerResponse MtibRunnerZephyr_DutEnableChargerRpc(cipher_unary_rpc_user_info_t *info, DutEnableChargerRequest request)
{
    DutEnableChargerResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_DutEnableCharger,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutSetOutputVoltageResponse MtibRunnerZephyr_DutSetOutputVoltageRpc(cipher_unary_rpc_user_info_t *info, DutSetOutputVoltageRequest request)
{
    DutSetOutputVoltageResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_DutSetOutputVoltage,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
Ina219ReadCurrentResponse MtibRunnerZephyr_Ina219ReadCurrentRpc(cipher_unary_rpc_user_info_t *info, Ina219ReadCurrentRequest request)
{
    Ina219ReadCurrentResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_Ina219ReadCurrent,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
Ina219ReadVoltageResponse MtibRunnerZephyr_Ina219ReadVoltageRpc(cipher_unary_rpc_user_info_t *info, Ina219ReadVoltageRequest request)
{
    Ina219ReadVoltageResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_Ina219ReadVoltage,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
Ina219ReadPowerResponse MtibRunnerZephyr_Ina219ReadPowerRpc(cipher_unary_rpc_user_info_t *info, Ina219ReadPowerRequest request)
{
    Ina219ReadPowerResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_Ina219ReadPower,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
Bmp390ReadValuesResponse MtibRunnerZephyr_Bmp390ReadValuesRpc(cipher_unary_rpc_user_info_t *info, Bmp390ReadValuesRequest request)
{
    Bmp390ReadValuesResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_Bmp390ReadValues,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
Lis2de12ReadValuesResponse MtibRunnerZephyr_Lis2de12ReadValuesRpc(cipher_unary_rpc_user_info_t *info, Lis2de12ReadValuesRequest request)
{
    Lis2de12ReadValuesResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_Lis2de12ReadValues,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
Lis2de12ReadMaxForceResponse MtibRunnerZephyr_Lis2de12ReadMaxForceRpc(cipher_unary_rpc_user_info_t *info, Lis2de12ReadMaxForceRequest request)
{
    Lis2de12ReadMaxForceResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_Lis2de12ReadMaxForce,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
EepromReadFromMemResponse MtibRunnerZephyr_EepromReadFromMemRpc(cipher_unary_rpc_user_info_t *info, EepromReadFromMemRequest request)
{
    EepromReadFromMemResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_EepromReadFromMem,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
EepromWriteToMemResponse MtibRunnerZephyr_EepromWriteToMemRpc(cipher_unary_rpc_user_info_t *info, EepromWriteToMemRequest request)
{
    EepromWriteToMemResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_EepromWriteToMem,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
UartPortStateChangeResponse MtibRunnerZephyr_UartPortEnableRpc(cipher_unary_rpc_user_info_t *info, UartPortStateChangeRequest request)
{
    UartPortStateChangeResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_UartPortEnable,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
UartPortStateChangeResponse MtibRunnerZephyr_UartPortDisableRpc(cipher_unary_rpc_user_info_t *info, UartPortStateChangeRequest request)
{
    UartPortStateChangeResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_UartPortDisable,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
UartMessageResponse MtibRunnerZephyr_SigmaToPiMessageRpc(cipher_unary_rpc_user_info_t *info, UartMessageRequest request)
{
    UartMessageResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_SigmaToPiMessage,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
UartMessageResponse MtibRunnerZephyr_PiToSigmaMessageRpc(cipher_unary_rpc_user_info_t *info, UartMessageRequest request)
{
    UartMessageResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBRUNNERZEPHYR_SERVICE_ID,
        .rpc_id = rpc_PiToSigmaMessage,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}

static cipher_rpc_info_t mtibrunnerzephyr_rpcs[] =
{
    {
        .id = rpc_GpioConfigurePin,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "GpioConfigurePin",
        .handler = GpioConfigurePinRpcPrvHandler,
        .request_info = {
            .fields = GpioConfigurePinRequest_fields,
            .encoded_size = GpioConfigurePinRequest_size,
            .decoded_size = sizeof(GpioConfigurePinRequest)
        },
        .response_info = {
            .fields = GpioConfigurePinResponse_fields,
            .encoded_size = GpioConfigurePinResponse_size,
            .decoded_size = sizeof(GpioConfigurePinResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_GpioSetPin,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "GpioSetPin",
        .handler = GpioSetPinRpcPrvHandler,
        .request_info = {
            .fields = GpioSetPinRequest_fields,
            .encoded_size = GpioSetPinRequest_size,
            .decoded_size = sizeof(GpioSetPinRequest)
        },
        .response_info = {
            .fields = GpioSetPinResponse_fields,
            .encoded_size = GpioSetPinResponse_size,
            .decoded_size = sizeof(GpioSetPinResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_GpioReadPin,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "GpioReadPin",
        .handler = GpioReadPinRpcPrvHandler,
        .request_info = {
            .fields = GpioReadPinRequest_fields,
            .encoded_size = GpioReadPinRequest_size,
            .decoded_size = sizeof(GpioReadPinRequest)
        },
        .response_info = {
            .fields = GpioReadPinResponse_fields,
            .encoded_size = GpioReadPinResponse_size,
            .decoded_size = sizeof(GpioReadPinResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_AdcReadChannel,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "AdcReadChannel",
        .handler = AdcReadChannelRpcPrvHandler,
        .request_info = {
            .fields = AdcReadChannelRequest_fields,
            .encoded_size = AdcReadChannelRequest_size,
            .decoded_size = sizeof(AdcReadChannelRequest)
        },
        .response_info = {
            .fields = AdcReadChannelResponse_fields,
            .encoded_size = AdcReadChannelResponse_size,
            .decoded_size = sizeof(AdcReadChannelResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_AdcReadAllChannels,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "AdcReadAllChannels",
        .handler = AdcReadAllChannelsRpcPrvHandler,
        .request_info = {
            .fields = AdcReadAllChannelsRequest_fields,
            .encoded_size = AdcReadAllChannelsRequest_size,
            .decoded_size = sizeof(AdcReadAllChannelsRequest)
        },
        .response_info = {
            .fields = AdcReadAllChannelsResponse_fields,
            .encoded_size = AdcReadAllChannelsResponse_size,
            .decoded_size = sizeof(AdcReadAllChannelsResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_DutEnablePower,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "DutEnablePower",
        .handler = DutEnablePowerRpcPrvHandler,
        .request_info = {
            .fields = DutEnablePowerRequest_fields,
            .encoded_size = DutEnablePowerRequest_size,
            .decoded_size = sizeof(DutEnablePowerRequest)
        },
        .response_info = {
            .fields = DutEnablePowerResponse_fields,
            .encoded_size = DutEnablePowerResponse_size,
            .decoded_size = sizeof(DutEnablePowerResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_DutEnableCharger,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "DutEnableCharger",
        .handler = DutEnableChargerRpcPrvHandler,
        .request_info = {
            .fields = DutEnableChargerRequest_fields,
            .encoded_size = DutEnableChargerRequest_size,
            .decoded_size = sizeof(DutEnableChargerRequest)
        },
        .response_info = {
            .fields = DutEnableChargerResponse_fields,
            .encoded_size = DutEnableChargerResponse_size,
            .decoded_size = sizeof(DutEnableChargerResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_DutSetOutputVoltage,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "DutSetOutputVoltage",
        .handler = DutSetOutputVoltageRpcPrvHandler,
        .request_info = {
            .fields = DutSetOutputVoltageRequest_fields,
            .encoded_size = DutSetOutputVoltageRequest_size,
            .decoded_size = sizeof(DutSetOutputVoltageRequest)
        },
        .response_info = {
            .fields = DutSetOutputVoltageResponse_fields,
            .encoded_size = DutSetOutputVoltageResponse_size,
            .decoded_size = sizeof(DutSetOutputVoltageResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_Ina219ReadCurrent,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "Ina219ReadCurrent",
        .handler = Ina219ReadCurrentRpcPrvHandler,
        .request_info = {
            .fields = Ina219ReadCurrentRequest_fields,
            .encoded_size = Ina219ReadCurrentRequest_size,
            .decoded_size = sizeof(Ina219ReadCurrentRequest)
        },
        .response_info = {
            .fields = Ina219ReadCurrentResponse_fields,
            .encoded_size = Ina219ReadCurrentResponse_size,
            .decoded_size = sizeof(Ina219ReadCurrentResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_Ina219ReadVoltage,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "Ina219ReadVoltage",
        .handler = Ina219ReadVoltageRpcPrvHandler,
        .request_info = {
            .fields = Ina219ReadVoltageRequest_fields,
            .encoded_size = Ina219ReadVoltageRequest_size,
            .decoded_size = sizeof(Ina219ReadVoltageRequest)
        },
        .response_info = {
            .fields = Ina219ReadVoltageResponse_fields,
            .encoded_size = Ina219ReadVoltageResponse_size,
            .decoded_size = sizeof(Ina219ReadVoltageResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_Ina219ReadPower,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "Ina219ReadPower",
        .handler = Ina219ReadPowerRpcPrvHandler,
        .request_info = {
            .fields = Ina219ReadPowerRequest_fields,
            .encoded_size = Ina219ReadPowerRequest_size,
            .decoded_size = sizeof(Ina219ReadPowerRequest)
        },
        .response_info = {
            .fields = Ina219ReadPowerResponse_fields,
            .encoded_size = Ina219ReadPowerResponse_size,
            .decoded_size = sizeof(Ina219ReadPowerResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_Bmp390ReadValues,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "Bmp390ReadValues",
        .handler = Bmp390ReadValuesRpcPrvHandler,
        .request_info = {
            .fields = Bmp390ReadValuesRequest_fields,
            .encoded_size = Bmp390ReadValuesRequest_size,
            .decoded_size = sizeof(Bmp390ReadValuesRequest)
        },
        .response_info = {
            .fields = Bmp390ReadValuesResponse_fields,
            .encoded_size = Bmp390ReadValuesResponse_size,
            .decoded_size = sizeof(Bmp390ReadValuesResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_Lis2de12ReadValues,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "Lis2de12ReadValues",
        .handler = Lis2de12ReadValuesRpcPrvHandler,
        .request_info = {
            .fields = Lis2de12ReadValuesRequest_fields,
            .encoded_size = Lis2de12ReadValuesRequest_size,
            .decoded_size = sizeof(Lis2de12ReadValuesRequest)
        },
        .response_info = {
            .fields = Lis2de12ReadValuesResponse_fields,
            .encoded_size = Lis2de12ReadValuesResponse_size,
            .decoded_size = sizeof(Lis2de12ReadValuesResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_Lis2de12ReadMaxForce,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "Lis2de12ReadMaxForce",
        .handler = Lis2de12ReadMaxForceRpcPrvHandler,
        .request_info = {
            .fields = Lis2de12ReadMaxForceRequest_fields,
            .encoded_size = Lis2de12ReadMaxForceRequest_size,
            .decoded_size = sizeof(Lis2de12ReadMaxForceRequest)
        },
        .response_info = {
            .fields = Lis2de12ReadMaxForceResponse_fields,
            .encoded_size = Lis2de12ReadMaxForceResponse_size,
            .decoded_size = sizeof(Lis2de12ReadMaxForceResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_EepromReadFromMem,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "EepromReadFromMem",
        .handler = EepromReadFromMemRpcPrvHandler,
        .request_info = {
            .fields = EepromReadFromMemRequest_fields,
            .encoded_size = EepromReadFromMemRequest_size,
            .decoded_size = sizeof(EepromReadFromMemRequest)
        },
        .response_info = {
            .fields = EepromReadFromMemResponse_fields,
            .encoded_size = EepromReadFromMemResponse_size,
            .decoded_size = sizeof(EepromReadFromMemResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_EepromWriteToMem,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "EepromWriteToMem",
        .handler = EepromWriteToMemRpcPrvHandler,
        .request_info = {
            .fields = EepromWriteToMemRequest_fields,
            .encoded_size = EepromWriteToMemRequest_size,
            .decoded_size = sizeof(EepromWriteToMemRequest)
        },
        .response_info = {
            .fields = EepromWriteToMemResponse_fields,
            .encoded_size = EepromWriteToMemResponse_size,
            .decoded_size = sizeof(EepromWriteToMemResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_UartPortEnable,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "UartPortEnable",
        .handler = UartPortEnableRpcPrvHandler,
        .request_info = {
            .fields = UartPortStateChangeRequest_fields,
            .encoded_size = UartPortStateChangeRequest_size,
            .decoded_size = sizeof(UartPortStateChangeRequest)
        },
        .response_info = {
            .fields = UartPortStateChangeResponse_fields,
            .encoded_size = UartPortStateChangeResponse_size,
            .decoded_size = sizeof(UartPortStateChangeResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_UartPortDisable,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "UartPortDisable",
        .handler = UartPortDisableRpcPrvHandler,
        .request_info = {
            .fields = UartPortStateChangeRequest_fields,
            .encoded_size = UartPortStateChangeRequest_size,
            .decoded_size = sizeof(UartPortStateChangeRequest)
        },
        .response_info = {
            .fields = UartPortStateChangeResponse_fields,
            .encoded_size = UartPortStateChangeResponse_size,
            .decoded_size = sizeof(UartPortStateChangeResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_SigmaToPiMessage,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "SigmaToPiMessage",
        .handler = SigmaToPiMessageRpcPrvHandler,
        .request_info = {
            .fields = UartMessageRequest_fields,
            .encoded_size = UartMessageRequest_size,
            .decoded_size = sizeof(UartMessageRequest)
        },
        .response_info = {
            .fields = UartMessageResponse_fields,
            .encoded_size = UartMessageResponse_size,
            .decoded_size = sizeof(UartMessageResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_PiToSigmaMessage,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "PiToSigmaMessage",
        .handler = PiToSigmaMessageRpcPrvHandler,
        .request_info = {
            .fields = UartMessageRequest_fields,
            .encoded_size = UartMessageRequest_size,
            .decoded_size = sizeof(UartMessageRequest)
        },
        .response_info = {
            .fields = UartMessageResponse_fields,
            .encoded_size = UartMessageResponse_size,
            .decoded_size = sizeof(UartMessageResponse)
        },
        .supports_parallelism = true,
    },
};

static cipher_service_info_t mtibrunnerzephyr_service =
{
    .id = MTIBRUNNERZEPHYR_SERVICE_ID,
    .name = "MtibRunnerZephyr",
    .max_hops = 1,
    .rpcs = mtibrunnerzephyr_rpcs,
    .num_rpcs = ARRAY_SIZE(mtibrunnerzephyr_rpcs),
};

cipher_service_info_t *get_mtibrunnerzephyrservice_info(void)
{
    return &mtibrunnerzephyr_service;
}
