#ifndef MTIB_PI_STM_CIPHER_H
#define MTIB_PI_STM_CIPHER_H

#include <corekinect/cipher/cipher.h>
#include "mtib-pi-stm.pb.h"

// Service info registration function
cipher_service_info_t *get_mtibpistmservice_info(void);

// Server side handler
GpioConfigurePinResponse MtibPiStm_GpioConfigurePinHandler(GpioConfigurePinRequest request);

// Client side call
GpioConfigurePinResponse MtibPiStm_GpioConfigurePinRpc(cipher_unary_rpc_user_info_t *info, GpioConfigurePinRequest request);

// Server side handler
GpioSetPinResponse MtibPiStm_GpioSetPinHandler(GpioSetPinRequest request);

// Client side call
GpioSetPinResponse MtibPiStm_GpioSetPinRpc(cipher_unary_rpc_user_info_t *info, GpioSetPinRequest request);

// Server side handler
GpioReadPinResponse MtibPiStm_GpioReadPinHandler(GpioReadPinRequest request);

// Client side call
GpioReadPinResponse MtibPiStm_GpioReadPinRpc(cipher_unary_rpc_user_info_t *info, GpioReadPinRequest request);

// Server side handler
AdcReadChannelResponse MtibPiStm_AdcReadChannelHandler(AdcReadChannelRequest request);

// Client side call
AdcReadChannelResponse MtibPiStm_AdcReadChannelRpc(cipher_unary_rpc_user_info_t *info, AdcReadChannelRequest request);

// Server side handler
AdcReadAllChannelsResponse MtibPiStm_AdcReadAllChannelsHandler(AdcReadAllChannelsRequest request);

// Client side call
AdcReadAllChannelsResponse MtibPiStm_AdcReadAllChannelsRpc(cipher_unary_rpc_user_info_t *info, AdcReadAllChannelsRequest request);

// Server side handler
DutEnablePowerResponse MtibPiStm_DutEnablePowerHandler(DutEnablePowerRequest request);

// Client side call
DutEnablePowerResponse MtibPiStm_DutEnablePowerRpc(cipher_unary_rpc_user_info_t *info, DutEnablePowerRequest request);

// Server side handler
DutEnableChargerResponse MtibPiStm_DutEnableChargerHandler(DutEnableChargerRequest request);

// Client side call
DutEnableChargerResponse MtibPiStm_DutEnableChargerRpc(cipher_unary_rpc_user_info_t *info, DutEnableChargerRequest request);

// Server side handler
DutSetOutputVoltageResponse MtibPiStm_DutSetOutputVoltageHandler(DutSetOutputVoltageRequest request);

// Client side call
DutSetOutputVoltageResponse MtibPiStm_DutSetOutputVoltageRpc(cipher_unary_rpc_user_info_t *info, DutSetOutputVoltageRequest request);

// Server side handler
Ina219ReadCurrentResponse MtibPiStm_Ina219ReadCurrentHandler(Ina219ReadCurrentRequest request);

// Client side call
Ina219ReadCurrentResponse MtibPiStm_Ina219ReadCurrentRpc(cipher_unary_rpc_user_info_t *info, Ina219ReadCurrentRequest request);

// Server side handler
Ina219ReadVoltageResponse MtibPiStm_Ina219ReadVoltageHandler(Ina219ReadVoltageRequest request);

// Client side call
Ina219ReadVoltageResponse MtibPiStm_Ina219ReadVoltageRpc(cipher_unary_rpc_user_info_t *info, Ina219ReadVoltageRequest request);

// Server side handler
Ina219ReadPowerResponse MtibPiStm_Ina219ReadPowerHandler(Ina219ReadPowerRequest request);

// Client side call
Ina219ReadPowerResponse MtibPiStm_Ina219ReadPowerRpc(cipher_unary_rpc_user_info_t *info, Ina219ReadPowerRequest request);

// Server side handler
Bmp390ReadValuesResponse MtibPiStm_Bmp390ReadValuesHandler(Bmp390ReadValuesRequest request);

// Client side call
Bmp390ReadValuesResponse MtibPiStm_Bmp390ReadValuesRpc(cipher_unary_rpc_user_info_t *info, Bmp390ReadValuesRequest request);

// Server side handler
Lis2de12ReadValuesResponse MtibPiStm_Lis2de12ReadValuesHandler(Lis2de12ReadValuesRequest request);

// Client side call
Lis2de12ReadValuesResponse MtibPiStm_Lis2de12ReadValuesRpc(cipher_unary_rpc_user_info_t *info, Lis2de12ReadValuesRequest request);

// Server side handler
Lis2de12ReadMaxForceResponse MtibPiStm_Lis2de12ReadMaxForceHandler(Lis2de12ReadMaxForceRequest request);

// Client side call
Lis2de12ReadMaxForceResponse MtibPiStm_Lis2de12ReadMaxForceRpc(cipher_unary_rpc_user_info_t *info, Lis2de12ReadMaxForceRequest request);

// Server side handler
EepromReadFromMemResponse MtibPiStm_EepromReadFromMemHandler(EepromReadFromMemRequest request);

// Client side call
EepromReadFromMemResponse MtibPiStm_EepromReadFromMemRpc(cipher_unary_rpc_user_info_t *info, EepromReadFromMemRequest request);

// Server side handler
EepromWriteToMemResponse MtibPiStm_EepromWriteToMemHandler(EepromWriteToMemRequest request);

// Client side call
EepromWriteToMemResponse MtibPiStm_EepromWriteToMemRpc(cipher_unary_rpc_user_info_t *info, EepromWriteToMemRequest request);

// Server side handler
UartMessageResponse MtibPiStm_SigmaToPiMessageHandler(UartMessageRequest request);

// Client side call
UartMessageResponse MtibPiStm_SigmaToPiMessageRpc(cipher_unary_rpc_user_info_t *info, UartMessageRequest request);

// Server side handler
UartMessageResponse MtibPiStm_PiToSigmaMessageHandler(UartMessageRequest request);

// Client side call
UartMessageResponse MtibPiStm_PiToSigmaMessageRpc(cipher_unary_rpc_user_info_t *info, UartMessageRequest request);

#endif // MTIB-PI-STM_CIPHER_H
