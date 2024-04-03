#ifndef MTIB_ZEPHYR_CIPHER_H
#define MTIB_ZEPHYR_CIPHER_H

#include <corekinect/cipher/cipher.h>
#include "mtib_zephyr.pb.h"

// Service info registration function
cipher_service_info_t *get_mtibzephyrservice_info(void);

// Server side handler
GpioConfigurePinResponse MtibZephyr_GpioConfigurePinHandler(GpioConfigurePinRequest request);

// Client side call
GpioConfigurePinResponse MtibZephyr_GpioConfigurePinRpc(cipher_unary_rpc_user_info_t *info, GpioConfigurePinRequest request);

// Server side handler
GpioSetPinResponse MtibZephyr_GpioSetPinHandler(GpioSetPinRequest request);

// Client side call
GpioSetPinResponse MtibZephyr_GpioSetPinRpc(cipher_unary_rpc_user_info_t *info, GpioSetPinRequest request);

// Server side handler
GpioReadPinResponse MtibZephyr_GpioReadPinHandler(GpioReadPinRequest request);

// Client side call
GpioReadPinResponse MtibZephyr_GpioReadPinRpc(cipher_unary_rpc_user_info_t *info, GpioReadPinRequest request);

// Server side handler
AdcReadChannelResponse MtibZephyr_AdcReadChannelHandler(AdcReadChannelRequest request);

// Client side call
AdcReadChannelResponse MtibZephyr_AdcReadChannelRpc(cipher_unary_rpc_user_info_t *info, AdcReadChannelRequest request);

// Server side handler
AdcReadAllChannelsResponse MtibZephyr_AdcReadAllChannelsHandler(AdcReadAllChannelsRequest request);

// Client side call
AdcReadAllChannelsResponse MtibZephyr_AdcReadAllChannelsRpc(cipher_unary_rpc_user_info_t *info, AdcReadAllChannelsRequest request);

// Server side handler
DutEnablePowerResponse MtibZephyr_DutEnablePowerHandler(DutEnablePowerRequest request);

// Client side call
DutEnablePowerResponse MtibZephyr_DutEnablePowerRpc(cipher_unary_rpc_user_info_t *info, DutEnablePowerRequest request);

// Server side handler
DutEnableChargerResponse MtibZephyr_DutEnableChargerHandler(DutEnableChargerRequest request);

// Client side call
DutEnableChargerResponse MtibZephyr_DutEnableChargerRpc(cipher_unary_rpc_user_info_t *info, DutEnableChargerRequest request);

// Server side handler
DutSetOutputVoltageResponse MtibZephyr_DutSetOutputVoltageHandler(DutSetOutputVoltageRequest request);

// Client side call
DutSetOutputVoltageResponse MtibZephyr_DutSetOutputVoltageRpc(cipher_unary_rpc_user_info_t *info, DutSetOutputVoltageRequest request);

// Server side handler
Ina219ReadCurrentResponse MtibZephyr_Ina219ReadCurrentHandler(Ina219ReadCurrentRequest request);

// Client side call
Ina219ReadCurrentResponse MtibZephyr_Ina219ReadCurrentRpc(cipher_unary_rpc_user_info_t *info, Ina219ReadCurrentRequest request);

// Server side handler
Ina219ReadVoltageResponse MtibZephyr_Ina219ReadVoltageHandler(Ina219ReadVoltageRequest request);

// Client side call
Ina219ReadVoltageResponse MtibZephyr_Ina219ReadVoltageRpc(cipher_unary_rpc_user_info_t *info, Ina219ReadVoltageRequest request);

// Server side handler
Ina219ReadPowerResponse MtibZephyr_Ina219ReadPowerHandler(Ina219ReadPowerRequest request);

// Client side call
Ina219ReadPowerResponse MtibZephyr_Ina219ReadPowerRpc(cipher_unary_rpc_user_info_t *info, Ina219ReadPowerRequest request);

// Server side handler
Bmp390ReadValuesResponse MtibZephyr_Bmp390ReadValuesHandler(Bmp390ReadValuesRequest request);

// Client side call
Bmp390ReadValuesResponse MtibZephyr_Bmp390ReadValuesRpc(cipher_unary_rpc_user_info_t *info, Bmp390ReadValuesRequest request);

// Server side handler
Lis2de12ReadValuesResponse MtibZephyr_Lis2de12ReadValuesHandler(Lis2de12ReadValuesRequest request);

// Client side call
Lis2de12ReadValuesResponse MtibZephyr_Lis2de12ReadValuesRpc(cipher_unary_rpc_user_info_t *info, Lis2de12ReadValuesRequest request);

// Server side handler
Lis2de12ReadMaxForceResponse MtibZephyr_Lis2de12ReadMaxForceHandler(Lis2de12ReadMaxForceRequest request);

// Client side call
Lis2de12ReadMaxForceResponse MtibZephyr_Lis2de12ReadMaxForceRpc(cipher_unary_rpc_user_info_t *info, Lis2de12ReadMaxForceRequest request);

// Server side handler
EepromReadFromMemResponse MtibZephyr_EepromReadFromMemHandler(EepromReadFromMemRequest request);

// Client side call
EepromReadFromMemResponse MtibZephyr_EepromReadFromMemRpc(cipher_unary_rpc_user_info_t *info, EepromReadFromMemRequest request);

// Server side handler
EepromWriteToMemResponse MtibZephyr_EepromWriteToMemHandler(EepromWriteToMemRequest request);

// Client side call
EepromWriteToMemResponse MtibZephyr_EepromWriteToMemRpc(cipher_unary_rpc_user_info_t *info, EepromWriteToMemRequest request);

// Server side handler
UartMessageResponse MtibZephyr_SigmaToPiMessageHandler(UartMessageRequest request);

// Client side call
UartMessageResponse MtibZephyr_SigmaToPiMessageRpc(cipher_unary_rpc_user_info_t *info, UartMessageRequest request);

// Server side handler
UartMessageResponse MtibZephyr_PiToSigmaMessageHandler(UartMessageRequest request);

// Client side call
UartMessageResponse MtibZephyr_PiToSigmaMessageRpc(cipher_unary_rpc_user_info_t *info, UartMessageRequest request);

#endif // MTIB_ZEPHYR_CIPHER_H
