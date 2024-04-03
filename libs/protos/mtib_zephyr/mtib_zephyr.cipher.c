#include "mtib_zephyr.cipher.h"

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/iface/iface.h>
#include <corekinect/cipher/cipher.h>

// Protobuf includes
#include "mtib_zephyr.pb.h"

LOG_MODULE_REGISTER(mtibzephyr);

#define MTIBZEPHYR_SERVICE_ID 1

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
    rpc_SigmaToPiMessage = 17,
    rpc_PiToSigmaMessage = 18,
} MtibZephyr_rpc;

// Server side
static bool MtibZephyr_GpioConfigurePinHandlerImplemented = true;
__attribute__((weak)) GpioConfigurePinResponse MtibZephyr_GpioConfigurePinHandler(GpioConfigurePinRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibZephyr_GpioConfigurePinHandlerImplemented = false;
    GpioConfigurePinResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GpioConfigurePinRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GpioConfigurePinResponse *)response ) = MtibZephyr_GpioConfigurePinHandler(*((GpioConfigurePinRequest *)request));
    return MtibZephyr_GpioConfigurePinHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibZephyr_GpioSetPinHandlerImplemented = true;
__attribute__((weak)) GpioSetPinResponse MtibZephyr_GpioSetPinHandler(GpioSetPinRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibZephyr_GpioSetPinHandlerImplemented = false;
    GpioSetPinResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GpioSetPinRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GpioSetPinResponse *)response ) = MtibZephyr_GpioSetPinHandler(*((GpioSetPinRequest *)request));
    return MtibZephyr_GpioSetPinHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibZephyr_GpioReadPinHandlerImplemented = true;
__attribute__((weak)) GpioReadPinResponse MtibZephyr_GpioReadPinHandler(GpioReadPinRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibZephyr_GpioReadPinHandlerImplemented = false;
    GpioReadPinResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GpioReadPinRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GpioReadPinResponse *)response ) = MtibZephyr_GpioReadPinHandler(*((GpioReadPinRequest *)request));
    return MtibZephyr_GpioReadPinHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibZephyr_AdcReadChannelHandlerImplemented = true;
__attribute__((weak)) AdcReadChannelResponse MtibZephyr_AdcReadChannelHandler(AdcReadChannelRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibZephyr_AdcReadChannelHandlerImplemented = false;
    AdcReadChannelResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AdcReadChannelRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AdcReadChannelResponse *)response ) = MtibZephyr_AdcReadChannelHandler(*((AdcReadChannelRequest *)request));
    return MtibZephyr_AdcReadChannelHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibZephyr_AdcReadAllChannelsHandlerImplemented = true;
__attribute__((weak)) AdcReadAllChannelsResponse MtibZephyr_AdcReadAllChannelsHandler(AdcReadAllChannelsRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibZephyr_AdcReadAllChannelsHandlerImplemented = false;
    AdcReadAllChannelsResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AdcReadAllChannelsRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AdcReadAllChannelsResponse *)response ) = MtibZephyr_AdcReadAllChannelsHandler(*((AdcReadAllChannelsRequest *)request));
    return MtibZephyr_AdcReadAllChannelsHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibZephyr_DutEnablePowerHandlerImplemented = true;
__attribute__((weak)) DutEnablePowerResponse MtibZephyr_DutEnablePowerHandler(DutEnablePowerRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibZephyr_DutEnablePowerHandlerImplemented = false;
    DutEnablePowerResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutEnablePowerRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutEnablePowerResponse *)response ) = MtibZephyr_DutEnablePowerHandler(*((DutEnablePowerRequest *)request));
    return MtibZephyr_DutEnablePowerHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibZephyr_DutEnableChargerHandlerImplemented = true;
__attribute__((weak)) DutEnableChargerResponse MtibZephyr_DutEnableChargerHandler(DutEnableChargerRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibZephyr_DutEnableChargerHandlerImplemented = false;
    DutEnableChargerResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutEnableChargerRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutEnableChargerResponse *)response ) = MtibZephyr_DutEnableChargerHandler(*((DutEnableChargerRequest *)request));
    return MtibZephyr_DutEnableChargerHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibZephyr_DutSetOutputVoltageHandlerImplemented = true;
__attribute__((weak)) DutSetOutputVoltageResponse MtibZephyr_DutSetOutputVoltageHandler(DutSetOutputVoltageRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibZephyr_DutSetOutputVoltageHandlerImplemented = false;
    DutSetOutputVoltageResponse response  = {0};
    return response ;
}

cipher_rpc_err_t DutSetOutputVoltageRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((DutSetOutputVoltageResponse *)response ) = MtibZephyr_DutSetOutputVoltageHandler(*((DutSetOutputVoltageRequest *)request));
    return MtibZephyr_DutSetOutputVoltageHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibZephyr_Ina219ReadCurrentHandlerImplemented = true;
__attribute__((weak)) Ina219ReadCurrentResponse MtibZephyr_Ina219ReadCurrentHandler(Ina219ReadCurrentRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibZephyr_Ina219ReadCurrentHandlerImplemented = false;
    Ina219ReadCurrentResponse response  = {0};
    return response ;
}

cipher_rpc_err_t Ina219ReadCurrentRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((Ina219ReadCurrentResponse *)response ) = MtibZephyr_Ina219ReadCurrentHandler(*((Ina219ReadCurrentRequest *)request));
    return MtibZephyr_Ina219ReadCurrentHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibZephyr_Ina219ReadVoltageHandlerImplemented = true;
__attribute__((weak)) Ina219ReadVoltageResponse MtibZephyr_Ina219ReadVoltageHandler(Ina219ReadVoltageRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibZephyr_Ina219ReadVoltageHandlerImplemented = false;
    Ina219ReadVoltageResponse response  = {0};
    return response ;
}

cipher_rpc_err_t Ina219ReadVoltageRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((Ina219ReadVoltageResponse *)response ) = MtibZephyr_Ina219ReadVoltageHandler(*((Ina219ReadVoltageRequest *)request));
    return MtibZephyr_Ina219ReadVoltageHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibZephyr_Ina219ReadPowerHandlerImplemented = true;
__attribute__((weak)) Ina219ReadPowerResponse MtibZephyr_Ina219ReadPowerHandler(Ina219ReadPowerRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibZephyr_Ina219ReadPowerHandlerImplemented = false;
    Ina219ReadPowerResponse response  = {0};
    return response ;
}

cipher_rpc_err_t Ina219ReadPowerRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((Ina219ReadPowerResponse *)response ) = MtibZephyr_Ina219ReadPowerHandler(*((Ina219ReadPowerRequest *)request));
    return MtibZephyr_Ina219ReadPowerHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibZephyr_Bmp390ReadValuesHandlerImplemented = true;
__attribute__((weak)) Bmp390ReadValuesResponse MtibZephyr_Bmp390ReadValuesHandler(Bmp390ReadValuesRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibZephyr_Bmp390ReadValuesHandlerImplemented = false;
    Bmp390ReadValuesResponse response  = {0};
    return response ;
}

cipher_rpc_err_t Bmp390ReadValuesRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((Bmp390ReadValuesResponse *)response ) = MtibZephyr_Bmp390ReadValuesHandler(*((Bmp390ReadValuesRequest *)request));
    return MtibZephyr_Bmp390ReadValuesHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibZephyr_Lis2de12ReadValuesHandlerImplemented = true;
__attribute__((weak)) Lis2de12ReadValuesResponse MtibZephyr_Lis2de12ReadValuesHandler(Lis2de12ReadValuesRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibZephyr_Lis2de12ReadValuesHandlerImplemented = false;
    Lis2de12ReadValuesResponse response  = {0};
    return response ;
}

cipher_rpc_err_t Lis2de12ReadValuesRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((Lis2de12ReadValuesResponse *)response ) = MtibZephyr_Lis2de12ReadValuesHandler(*((Lis2de12ReadValuesRequest *)request));
    return MtibZephyr_Lis2de12ReadValuesHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibZephyr_Lis2de12ReadMaxForceHandlerImplemented = true;
__attribute__((weak)) Lis2de12ReadMaxForceResponse MtibZephyr_Lis2de12ReadMaxForceHandler(Lis2de12ReadMaxForceRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibZephyr_Lis2de12ReadMaxForceHandlerImplemented = false;
    Lis2de12ReadMaxForceResponse response  = {0};
    return response ;
}

cipher_rpc_err_t Lis2de12ReadMaxForceRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((Lis2de12ReadMaxForceResponse *)response ) = MtibZephyr_Lis2de12ReadMaxForceHandler(*((Lis2de12ReadMaxForceRequest *)request));
    return MtibZephyr_Lis2de12ReadMaxForceHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibZephyr_EepromReadFromMemHandlerImplemented = true;
__attribute__((weak)) EepromReadFromMemResponse MtibZephyr_EepromReadFromMemHandler(EepromReadFromMemRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibZephyr_EepromReadFromMemHandlerImplemented = false;
    EepromReadFromMemResponse response  = {0};
    return response ;
}

cipher_rpc_err_t EepromReadFromMemRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((EepromReadFromMemResponse *)response ) = MtibZephyr_EepromReadFromMemHandler(*((EepromReadFromMemRequest *)request));
    return MtibZephyr_EepromReadFromMemHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibZephyr_EepromWriteToMemHandlerImplemented = true;
__attribute__((weak)) EepromWriteToMemResponse MtibZephyr_EepromWriteToMemHandler(EepromWriteToMemRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibZephyr_EepromWriteToMemHandlerImplemented = false;
    EepromWriteToMemResponse response  = {0};
    return response ;
}

cipher_rpc_err_t EepromWriteToMemRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((EepromWriteToMemResponse *)response ) = MtibZephyr_EepromWriteToMemHandler(*((EepromWriteToMemRequest *)request));
    return MtibZephyr_EepromWriteToMemHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibZephyr_SigmaToPiMessageHandlerImplemented = true;
__attribute__((weak)) UartMessageResponse MtibZephyr_SigmaToPiMessageHandler(UartMessageRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibZephyr_SigmaToPiMessageHandlerImplemented = false;
    UartMessageResponse response  = {0};
    return response ;
}

cipher_rpc_err_t SigmaToPiMessageRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((UartMessageResponse *)response ) = MtibZephyr_SigmaToPiMessageHandler(*((UartMessageRequest *)request));
    return MtibZephyr_SigmaToPiMessageHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibZephyr_PiToSigmaMessageHandlerImplemented = true;
__attribute__((weak)) UartMessageResponse MtibZephyr_PiToSigmaMessageHandler(UartMessageRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibZephyr_PiToSigmaMessageHandlerImplemented = false;
    UartMessageResponse response  = {0};
    return response ;
}

cipher_rpc_err_t PiToSigmaMessageRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((UartMessageResponse *)response ) = MtibZephyr_PiToSigmaMessageHandler(*((UartMessageRequest *)request));
    return MtibZephyr_PiToSigmaMessageHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Client side
GpioConfigurePinResponse MtibZephyr_GpioConfigurePinRpc(cipher_unary_rpc_user_info_t *info, GpioConfigurePinRequest request)
{
    GpioConfigurePinResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBZEPHYR_SERVICE_ID,
        .rpc_id = rpc_GpioConfigurePin,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GpioSetPinResponse MtibZephyr_GpioSetPinRpc(cipher_unary_rpc_user_info_t *info, GpioSetPinRequest request)
{
    GpioSetPinResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBZEPHYR_SERVICE_ID,
        .rpc_id = rpc_GpioSetPin,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GpioReadPinResponse MtibZephyr_GpioReadPinRpc(cipher_unary_rpc_user_info_t *info, GpioReadPinRequest request)
{
    GpioReadPinResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBZEPHYR_SERVICE_ID,
        .rpc_id = rpc_GpioReadPin,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AdcReadChannelResponse MtibZephyr_AdcReadChannelRpc(cipher_unary_rpc_user_info_t *info, AdcReadChannelRequest request)
{
    AdcReadChannelResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBZEPHYR_SERVICE_ID,
        .rpc_id = rpc_AdcReadChannel,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
AdcReadAllChannelsResponse MtibZephyr_AdcReadAllChannelsRpc(cipher_unary_rpc_user_info_t *info, AdcReadAllChannelsRequest request)
{
    AdcReadAllChannelsResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBZEPHYR_SERVICE_ID,
        .rpc_id = rpc_AdcReadAllChannels,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutEnablePowerResponse MtibZephyr_DutEnablePowerRpc(cipher_unary_rpc_user_info_t *info, DutEnablePowerRequest request)
{
    DutEnablePowerResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBZEPHYR_SERVICE_ID,
        .rpc_id = rpc_DutEnablePower,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutEnableChargerResponse MtibZephyr_DutEnableChargerRpc(cipher_unary_rpc_user_info_t *info, DutEnableChargerRequest request)
{
    DutEnableChargerResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBZEPHYR_SERVICE_ID,
        .rpc_id = rpc_DutEnableCharger,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
DutSetOutputVoltageResponse MtibZephyr_DutSetOutputVoltageRpc(cipher_unary_rpc_user_info_t *info, DutSetOutputVoltageRequest request)
{
    DutSetOutputVoltageResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBZEPHYR_SERVICE_ID,
        .rpc_id = rpc_DutSetOutputVoltage,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
Ina219ReadCurrentResponse MtibZephyr_Ina219ReadCurrentRpc(cipher_unary_rpc_user_info_t *info, Ina219ReadCurrentRequest request)
{
    Ina219ReadCurrentResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBZEPHYR_SERVICE_ID,
        .rpc_id = rpc_Ina219ReadCurrent,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
Ina219ReadVoltageResponse MtibZephyr_Ina219ReadVoltageRpc(cipher_unary_rpc_user_info_t *info, Ina219ReadVoltageRequest request)
{
    Ina219ReadVoltageResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBZEPHYR_SERVICE_ID,
        .rpc_id = rpc_Ina219ReadVoltage,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
Ina219ReadPowerResponse MtibZephyr_Ina219ReadPowerRpc(cipher_unary_rpc_user_info_t *info, Ina219ReadPowerRequest request)
{
    Ina219ReadPowerResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBZEPHYR_SERVICE_ID,
        .rpc_id = rpc_Ina219ReadPower,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
Bmp390ReadValuesResponse MtibZephyr_Bmp390ReadValuesRpc(cipher_unary_rpc_user_info_t *info, Bmp390ReadValuesRequest request)
{
    Bmp390ReadValuesResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBZEPHYR_SERVICE_ID,
        .rpc_id = rpc_Bmp390ReadValues,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
Lis2de12ReadValuesResponse MtibZephyr_Lis2de12ReadValuesRpc(cipher_unary_rpc_user_info_t *info, Lis2de12ReadValuesRequest request)
{
    Lis2de12ReadValuesResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBZEPHYR_SERVICE_ID,
        .rpc_id = rpc_Lis2de12ReadValues,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
Lis2de12ReadMaxForceResponse MtibZephyr_Lis2de12ReadMaxForceRpc(cipher_unary_rpc_user_info_t *info, Lis2de12ReadMaxForceRequest request)
{
    Lis2de12ReadMaxForceResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBZEPHYR_SERVICE_ID,
        .rpc_id = rpc_Lis2de12ReadMaxForce,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
EepromReadFromMemResponse MtibZephyr_EepromReadFromMemRpc(cipher_unary_rpc_user_info_t *info, EepromReadFromMemRequest request)
{
    EepromReadFromMemResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBZEPHYR_SERVICE_ID,
        .rpc_id = rpc_EepromReadFromMem,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
EepromWriteToMemResponse MtibZephyr_EepromWriteToMemRpc(cipher_unary_rpc_user_info_t *info, EepromWriteToMemRequest request)
{
    EepromWriteToMemResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBZEPHYR_SERVICE_ID,
        .rpc_id = rpc_EepromWriteToMem,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
UartMessageResponse MtibZephyr_SigmaToPiMessageRpc(cipher_unary_rpc_user_info_t *info, UartMessageRequest request)
{
    UartMessageResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBZEPHYR_SERVICE_ID,
        .rpc_id = rpc_SigmaToPiMessage,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
UartMessageResponse MtibZephyr_PiToSigmaMessageRpc(cipher_unary_rpc_user_info_t *info, UartMessageRequest request)
{
    UartMessageResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBZEPHYR_SERVICE_ID,
        .rpc_id = rpc_PiToSigmaMessage,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}

static cipher_rpc_info_t mtibzephyr_rpcs[] =
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

static cipher_service_info_t mtibzephyr_service =
{
    .id = MTIBZEPHYR_SERVICE_ID,
    .name = "MtibZephyr",
    .max_hops = 1,
    .rpcs = mtibzephyr_rpcs,
    .num_rpcs = ARRAY_SIZE(mtibzephyr_rpcs),
};

cipher_service_info_t *get_mtibzephyrservice_info(void)
{
    return &mtibzephyr_service;
}
