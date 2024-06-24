#ifndef MTIB_RUNNER_ZEPHYR_CIPHER_H
#define MTIB_RUNNER_ZEPHYR_CIPHER_H

#include <corekinect/cipher/cipher.h>
#include "mtib_runner_zephyr.pb.h"

// Service info registration function
cipher_service_info_t *get_mtibrunnerzephyrservice_info(void);

// Server side handler
GpioConfigurePinResponse MtibRunnerZephyr_GpioConfigurePinHandler(GpioConfigurePinRequest request);

// Client side call
GpioConfigurePinResponse MtibRunnerZephyr_GpioConfigurePinRpc(cipher_unary_rpc_user_info_t *info, GpioConfigurePinRequest request);

// Server side handler
GpioSetPinResponse MtibRunnerZephyr_GpioSetPinHandler(GpioSetPinRequest request);

// Client side call
GpioSetPinResponse MtibRunnerZephyr_GpioSetPinRpc(cipher_unary_rpc_user_info_t *info, GpioSetPinRequest request);

// Server side handler
GpioReadPinResponse MtibRunnerZephyr_GpioReadPinHandler(GpioReadPinRequest request);

// Client side call
GpioReadPinResponse MtibRunnerZephyr_GpioReadPinRpc(cipher_unary_rpc_user_info_t *info, GpioReadPinRequest request);

// Server side handler
AdcReadChannelResponse MtibRunnerZephyr_AdcReadChannelHandler(AdcReadChannelRequest request);

// Client side call
AdcReadChannelResponse MtibRunnerZephyr_AdcReadChannelRpc(cipher_unary_rpc_user_info_t *info, AdcReadChannelRequest request);

// Server side handler
AdcReadAllChannelsResponse MtibRunnerZephyr_AdcReadAllChannelsHandler(AdcReadAllChannelsRequest request);

// Client side call
AdcReadAllChannelsResponse MtibRunnerZephyr_AdcReadAllChannelsRpc(cipher_unary_rpc_user_info_t *info, AdcReadAllChannelsRequest request);

// Server side handler
DutEnablePowerResponse MtibRunnerZephyr_DutEnablePowerHandler(DutEnablePowerRequest request);

// Client side call
DutEnablePowerResponse MtibRunnerZephyr_DutEnablePowerRpc(cipher_unary_rpc_user_info_t *info, DutEnablePowerRequest request);

// Server side handler
DutEnableChargerResponse MtibRunnerZephyr_DutEnableChargerHandler(DutEnableChargerRequest request);

// Client side call
DutEnableChargerResponse MtibRunnerZephyr_DutEnableChargerRpc(cipher_unary_rpc_user_info_t *info, DutEnableChargerRequest request);

// Server side handler
DutSetOutputVoltageResponse MtibRunnerZephyr_DutSetOutputVoltageHandler(DutSetOutputVoltageRequest request);

// Client side call
DutSetOutputVoltageResponse MtibRunnerZephyr_DutSetOutputVoltageRpc(cipher_unary_rpc_user_info_t *info, DutSetOutputVoltageRequest request);

// Server side handler
Ina219ReadCurrentResponse MtibRunnerZephyr_Ina219ReadCurrentHandler(Ina219ReadCurrentRequest request);

// Client side call
Ina219ReadCurrentResponse MtibRunnerZephyr_Ina219ReadCurrentRpc(cipher_unary_rpc_user_info_t *info, Ina219ReadCurrentRequest request);

// Server side handler
Ina219ReadVoltageResponse MtibRunnerZephyr_Ina219ReadVoltageHandler(Ina219ReadVoltageRequest request);

// Client side call
Ina219ReadVoltageResponse MtibRunnerZephyr_Ina219ReadVoltageRpc(cipher_unary_rpc_user_info_t *info, Ina219ReadVoltageRequest request);

// Server side handler
Ina219ReadPowerResponse MtibRunnerZephyr_Ina219ReadPowerHandler(Ina219ReadPowerRequest request);

// Client side call
Ina219ReadPowerResponse MtibRunnerZephyr_Ina219ReadPowerRpc(cipher_unary_rpc_user_info_t *info, Ina219ReadPowerRequest request);

// Server side handler
Bmp390ReadValuesResponse MtibRunnerZephyr_Bmp390ReadValuesHandler(Bmp390ReadValuesRequest request);

// Client side call
Bmp390ReadValuesResponse MtibRunnerZephyr_Bmp390ReadValuesRpc(cipher_unary_rpc_user_info_t *info, Bmp390ReadValuesRequest request);

// Server side handler
Lis2de12ReadValuesResponse MtibRunnerZephyr_Lis2de12ReadValuesHandler(Lis2de12ReadValuesRequest request);

// Client side call
Lis2de12ReadValuesResponse MtibRunnerZephyr_Lis2de12ReadValuesRpc(cipher_unary_rpc_user_info_t *info, Lis2de12ReadValuesRequest request);

// Server side handler
Lis2de12ReadMaxForceResponse MtibRunnerZephyr_Lis2de12ReadMaxForceHandler(Lis2de12ReadMaxForceRequest request);

// Client side call
Lis2de12ReadMaxForceResponse MtibRunnerZephyr_Lis2de12ReadMaxForceRpc(cipher_unary_rpc_user_info_t *info, Lis2de12ReadMaxForceRequest request);

// Server side handler
EepromReadFromMemResponse MtibRunnerZephyr_EepromReadFromMemHandler(EepromReadFromMemRequest request);

// Client side call
EepromReadFromMemResponse MtibRunnerZephyr_EepromReadFromMemRpc(cipher_unary_rpc_user_info_t *info, EepromReadFromMemRequest request);

// Server side handler
EepromWriteToMemResponse MtibRunnerZephyr_EepromWriteToMemHandler(EepromWriteToMemRequest request);

// Client side call
EepromWriteToMemResponse MtibRunnerZephyr_EepromWriteToMemRpc(cipher_unary_rpc_user_info_t *info, EepromWriteToMemRequest request);

// Server side handler
UartPortStateChangeResponse MtibRunnerZephyr_UartPortEnableHandler(UartPortStateChangeRequest request);

// Client side call
UartPortStateChangeResponse MtibRunnerZephyr_UartPortEnableRpc(cipher_unary_rpc_user_info_t *info, UartPortStateChangeRequest request);

// Server side handler
UartPortStateChangeResponse MtibRunnerZephyr_UartPortDisableHandler(UartPortStateChangeRequest request);

// Client side call
UartPortStateChangeResponse MtibRunnerZephyr_UartPortDisableRpc(cipher_unary_rpc_user_info_t *info, UartPortStateChangeRequest request);

// Server side handler
UartMessageResponse MtibRunnerZephyr_SigmaToPiMessageHandler(UartMessageRequest request);

// Client side call
UartMessageResponse MtibRunnerZephyr_SigmaToPiMessageRpc(cipher_unary_rpc_user_info_t *info, UartMessageRequest request);

// Server side handler
UartMessageResponse MtibRunnerZephyr_PiToSigmaMessageHandler(UartMessageRequest request);

// Client side call
UartMessageResponse MtibRunnerZephyr_PiToSigmaMessageRpc(cipher_unary_rpc_user_info_t *info, UartMessageRequest request);

#endif // MTIB_RUNNER_ZEPHYR_CIPHER_H
