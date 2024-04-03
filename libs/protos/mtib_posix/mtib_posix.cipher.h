#ifndef MTIB_POSIX_CIPHER_H
#define MTIB_POSIX_CIPHER_H

#include <corekinect/cipher/cipher.h>
#include "mtib_posix.pb.h"

// Service info registration function
cipher_service_info_t *get_mtibposixservice_info(void);

// Server side handler
HealthCheckResponse MtibPosix_HealthCheckHandler(HealthCheckRequest request);

// Client side call
HealthCheckResponse MtibPosix_HealthCheckRpc(cipher_unary_rpc_user_info_t *info, HealthCheckRequest request);

// Server side handler
GpioConfigResponse MtibPosix_GpioConfigHandler(GpioConfigRequest request);

// Client side call
GpioConfigResponse MtibPosix_GpioConfigRpc(cipher_unary_rpc_user_info_t *info, GpioConfigRequest request);

// Server side handler
GpioWriteResponse MtibPosix_GpioWriteHandler(GpioWriteRequest request);

// Client side call
GpioWriteResponse MtibPosix_GpioWriteRpc(cipher_unary_rpc_user_info_t *info, GpioWriteRequest request);

// Server side handler
GpioReadResponse MtibPosix_GpioReadHandler(GpioReadRequest request);

// Client side call
GpioReadResponse MtibPosix_GpioReadRpc(cipher_unary_rpc_user_info_t *info, GpioReadRequest request);

// Server side handler
AdcReadResponse MtibPosix_AdcReadHandler(AdcReadRequest request);

// Client side call
AdcReadResponse MtibPosix_AdcReadRpc(cipher_unary_rpc_user_info_t *info, AdcReadRequest request);

// Server side handler
AdcReadAllResponse MtibPosix_AdcReadAllHandler(AdcReadAllRequest request);

// Client side call
AdcReadAllResponse MtibPosix_AdcReadAllRpc(cipher_unary_rpc_user_info_t *info, AdcReadAllRequest request);

// Server side handler
DutPowerEnableResponse MtibPosix_DutPowerEnableHandler(DutPowerEnableRequest request);

// Client side call
DutPowerEnableResponse MtibPosix_DutPowerEnableRpc(cipher_unary_rpc_user_info_t *info, DutPowerEnableRequest request);

// Server side handler
DutPowerEnableResponse MtibPosix_DutChargePowerEnableHandler(DutPowerEnableRequest request);

// Client side call
DutPowerEnableResponse MtibPosix_DutChargePowerEnableRpc(cipher_unary_rpc_user_info_t *info, DutPowerEnableRequest request);

// Server side handler
DutVoltageSetResponse MtibPosix_DutVoltageSetHandler(DutVoltageSetRequest request);

// Client side call
DutVoltageSetResponse MtibPosix_DutVoltageSetRpc(cipher_unary_rpc_user_info_t *info, DutVoltageSetRequest request);

// Server side handler
DutCurrentReadResponse MtibPosix_DutCurrentReadHandler(DutCurrentReadRequest request);

// Client side call
DutCurrentReadResponse MtibPosix_DutCurrentReadRpc(cipher_unary_rpc_user_info_t *info, DutCurrentReadRequest request);

// Server side handler
DutVoltageReadResponse MtibPosix_DutVoltageReadHandler(DutVoltageReadRequest request);

// Client side call
DutVoltageReadResponse MtibPosix_DutVoltageReadRpc(cipher_unary_rpc_user_info_t *info, DutVoltageReadRequest request);

// Server side handler
DutPowerReadResponse MtibPosix_DutPowerReadHandler(DutPowerReadRequest request);

// Client side call
DutPowerReadResponse MtibPosix_DutPowerReadRpc(cipher_unary_rpc_user_info_t *info, DutPowerReadRequest request);

// Server side handler
AltimeterReadResponse MtibPosix_AltimeterReadHandler(AltimeterReadRequest request);

// Client side call
AltimeterReadResponse MtibPosix_AltimeterReadRpc(cipher_unary_rpc_user_info_t *info, AltimeterReadRequest request);

// Server side handler
AccelReadResponse MtibPosix_AccelReadHandler(AccelReadRequest request);

// Client side call
AccelReadResponse MtibPosix_AccelReadRpc(cipher_unary_rpc_user_info_t *info, AccelReadRequest request);

// Server side handler
AccelReadMaxResponse MtibPosix_AccelReadMaxForceHandler(AccelReadMaxRequest request);

// Client side call
AccelReadMaxResponse MtibPosix_AccelReadMaxForceRpc(cipher_unary_rpc_user_info_t *info, AccelReadMaxRequest request);

// Server side handler
EepromReadResponse MtibPosix_EepromReadHandler(EepromReadRequest request);

// Client side call
EepromReadResponse MtibPosix_EepromReadRpc(cipher_unary_rpc_user_info_t *info, EepromReadRequest request);

// Server side handler
EepromWriteResponse MtibPosix_EepromWriteHandler(EepromWriteRequest request);

// Client side call
EepromWriteResponse MtibPosix_EepromWriteRpc(cipher_unary_rpc_user_info_t *info, EepromWriteRequest request);

// Server side handler
ListFwFilesResponse MtibPosix_ListFwFilesHandler(ListFwFilesRequest request);

// Client side call
ListFwFilesResponse MtibPosix_ListFwFilesRpc(cipher_unary_rpc_user_info_t *info, ListFwFilesRequest request);

// Server side handler
UploadFwFileResponse MtibPosix_UploadFwFileHandler(UploadFwFileRequest request);

// Client side call
UploadFwFileResponse MtibPosix_UploadFwFileRpc(cipher_unary_rpc_user_info_t *info, UploadFwFileRequest request);

// Server side handler
DeleteFwFileResponse MtibPosix_DeleteFwFileHandler(DeleteFwFileRequest request);

// Client side call
DeleteFwFileResponse MtibPosix_DeleteFwFileRpc(cipher_unary_rpc_user_info_t *info, DeleteFwFileRequest request);

// Server side handler
FlashHexFileResponse MtibPosix_FlashHexFileHandler(FlashHexFileRequest request);

// Client side call
FlashHexFileResponse MtibPosix_FlashHexFileRpc(cipher_unary_rpc_user_info_t *info, FlashHexFileRequest request);

#endif // MTIB_POSIX_CIPHER_H
