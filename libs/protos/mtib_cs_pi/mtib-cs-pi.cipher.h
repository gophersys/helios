#ifndef MTIB_CS_PI_CIPHER_H
#define MTIB_CS_PI_CIPHER_H

#include <corekinect/cipher/cipher.h>
#include "mtib-cs-pi.pb.h"

// Service info registration function
cipher_service_info_t *get_mtibcspiservice_info(void);

// Server side handler
GpioConfigResponse MtibCsPi_GpioConfigHandler(GpioConfigRequest request);

// Client side call
GpioConfigResponse MtibCsPi_GpioConfigRpc(cipher_unary_rpc_user_info_t *info, GpioConfigRequest request);

// Server side handler
GpioWriteResponse MtibCsPi_GpioWriteHandler(GpioWriteRequest request);

// Client side call
GpioWriteResponse MtibCsPi_GpioWriteRpc(cipher_unary_rpc_user_info_t *info, GpioWriteRequest request);

// Server side handler
GpioReadResponse MtibCsPi_GpioReadHandler(GpioReadRequest request);

// Client side call
GpioReadResponse MtibCsPi_GpioReadRpc(cipher_unary_rpc_user_info_t *info, GpioReadRequest request);

// Server side handler
AdcReadResponse MtibCsPi_AdcReadHandler(AdcReadRequest request);

// Client side call
AdcReadResponse MtibCsPi_AdcReadRpc(cipher_unary_rpc_user_info_t *info, AdcReadRequest request);

// Server side handler
AdcReadAllResponse MtibCsPi_AdcReadAllHandler(AdcReadAllRequest request);

// Client side call
AdcReadAllResponse MtibCsPi_AdcReadAllRpc(cipher_unary_rpc_user_info_t *info, AdcReadAllRequest request);

// Server side handler
DutPowerEnableResponse MtibCsPi_DutPowerEnableHandler(DutPowerEnableRequest request);

// Client side call
DutPowerEnableResponse MtibCsPi_DutPowerEnableRpc(cipher_unary_rpc_user_info_t *info, DutPowerEnableRequest request);

// Server side handler
DutPowerEnableResponse MtibCsPi_DutChargePowerEnableHandler(DutPowerEnableRequest request);

// Client side call
DutPowerEnableResponse MtibCsPi_DutChargePowerEnableRpc(cipher_unary_rpc_user_info_t *info, DutPowerEnableRequest request);

// Server side handler
DutVoltageSetResponse MtibCsPi_DutVoltageSetHandler(DutVoltageSetRequest request);

// Client side call
DutVoltageSetResponse MtibCsPi_DutVoltageSetRpc(cipher_unary_rpc_user_info_t *info, DutVoltageSetRequest request);

// Server side handler
DutCurrentReadResponse MtibCsPi_DutCurrentReadHandler(DutCurrentReadRequest request);

// Client side call
DutCurrentReadResponse MtibCsPi_DutCurrentReadRpc(cipher_unary_rpc_user_info_t *info, DutCurrentReadRequest request);

// Server side handler
DutVoltageReadResponse MtibCsPi_DutVoltageReadHandler(DutVoltageReadRequest request);

// Client side call
DutVoltageReadResponse MtibCsPi_DutVoltageReadRpc(cipher_unary_rpc_user_info_t *info, DutVoltageReadRequest request);

// Server side handler
DutPowerReadResponse MtibCsPi_DutPowerReadHandler(DutPowerReadRequest request);

// Client side call
DutPowerReadResponse MtibCsPi_DutPowerReadRpc(cipher_unary_rpc_user_info_t *info, DutPowerReadRequest request);

// Server side handler
AltimeterReadResponse MtibCsPi_AltimeterReadHandler(AltimeterReadRequest request);

// Client side call
AltimeterReadResponse MtibCsPi_AltimeterReadRpc(cipher_unary_rpc_user_info_t *info, AltimeterReadRequest request);

// Server side handler
AccelReadResponse MtibCsPi_AccelReadHandler(AccelReadRequest request);

// Client side call
AccelReadResponse MtibCsPi_AccelReadRpc(cipher_unary_rpc_user_info_t *info, AccelReadRequest request);

// Server side handler
AccelReadMaxResponse MtibCsPi_AccelReadMaxForceHandler(AccelReadMaxRequest request);

// Client side call
AccelReadMaxResponse MtibCsPi_AccelReadMaxForceRpc(cipher_unary_rpc_user_info_t *info, AccelReadMaxRequest request);

// Server side handler
EepromReadResponse MtibCsPi_EepromReadHandler(EepromReadRequest request);

// Client side call
EepromReadResponse MtibCsPi_EepromReadRpc(cipher_unary_rpc_user_info_t *info, EepromReadRequest request);

// Server side handler
EepromWriteResponse MtibCsPi_EepromWriteHandler(EepromWriteRequest request);

// Client side call
EepromWriteResponse MtibCsPi_EepromWriteRpc(cipher_unary_rpc_user_info_t *info, EepromWriteRequest request);

// Server side handler
ListFwFilesResponse MtibCsPi_ListFwFilesHandler(ListFwFilesRequest request);

// Client side call
ListFwFilesResponse MtibCsPi_ListFwFilesRpc(cipher_unary_rpc_user_info_t *info, ListFwFilesRequest request);

// Server side handler
UploadFwFileResponse MtibCsPi_UploadFwFileHandler(UploadFwFileRequest request);

// Client side call
UploadFwFileResponse MtibCsPi_UploadFwFileRpc(cipher_unary_rpc_user_info_t *info, UploadFwFileRequest request);

// Server side handler
DeleteFwFileResponse MtibCsPi_DeleteFwFileHandler(DeleteFwFileRequest request);

// Client side call
DeleteFwFileResponse MtibCsPi_DeleteFwFileRpc(cipher_unary_rpc_user_info_t *info, DeleteFwFileRequest request);

// Server side handler
FlashHexFileResponse MtibCsPi_FlashHexFileHandler(FlashHexFileRequest request);

// Client side call
FlashHexFileResponse MtibCsPi_FlashHexFileRpc(cipher_unary_rpc_user_info_t *info, FlashHexFileRequest request);

#endif // MTIB-CS-PI_CIPHER_H
