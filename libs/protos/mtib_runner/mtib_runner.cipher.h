#ifndef MTIB_RUNNER_CIPHER_H
#define MTIB_RUNNER_CIPHER_H

#include <corekinect/cipher/cipher.h>
#include "mtib_runner.pb.h"

// Service info registration function
cipher_service_info_t *get_mtibrunnerservice_info(void);

// Server side handler
HealthCheckResponse MtibRunner_HealthCheckHandler(HealthCheckRequest request);

// Client side call
HealthCheckResponse MtibRunner_HealthCheckRpc(cipher_unary_rpc_user_info_t *info, HealthCheckRequest request);

// Server side handler
GetRunnerInfoResponse MtibRunner_GetRunnerInfoHandler(GetRunnerInfoRequest request);

// Client side call
GetRunnerInfoResponse MtibRunner_GetRunnerInfoRpc(cipher_unary_rpc_user_info_t *info, GetRunnerInfoRequest request);

// Server side handler
ResetResponse MtibRunner_ResetHandler(ResetRequest request);

// Client side call
ResetResponse MtibRunner_ResetRpc(cipher_unary_rpc_user_info_t *info, ResetRequest request);

// Server side handler
GpioConfigResponse MtibRunner_GpioConfigHandler(GpioConfigRequest request);

// Client side call
GpioConfigResponse MtibRunner_GpioConfigRpc(cipher_unary_rpc_user_info_t *info, GpioConfigRequest request);

// Server side handler
GpioWriteResponse MtibRunner_GpioWriteHandler(GpioWriteRequest request);

// Client side call
GpioWriteResponse MtibRunner_GpioWriteRpc(cipher_unary_rpc_user_info_t *info, GpioWriteRequest request);

// Server side handler
GpioReadResponse MtibRunner_GpioReadHandler(GpioReadRequest request);

// Client side call
GpioReadResponse MtibRunner_GpioReadRpc(cipher_unary_rpc_user_info_t *info, GpioReadRequest request);

// Server side handler
AdcReadResponse MtibRunner_AdcReadHandler(AdcReadRequest request);

// Client side call
AdcReadResponse MtibRunner_AdcReadRpc(cipher_unary_rpc_user_info_t *info, AdcReadRequest request);

// Server side handler
AdcReadAllResponse MtibRunner_AdcReadAllHandler(AdcReadAllRequest request);

// Client side call
AdcReadAllResponse MtibRunner_AdcReadAllRpc(cipher_unary_rpc_user_info_t *info, AdcReadAllRequest request);

// Server side handler
DutPowerEnableResponse MtibRunner_DutPowerEnableHandler(DutPowerEnableRequest request);

// Client side call
DutPowerEnableResponse MtibRunner_DutPowerEnableRpc(cipher_unary_rpc_user_info_t *info, DutPowerEnableRequest request);

// Server side handler
DutPowerEnableResponse MtibRunner_DutChargePowerEnableHandler(DutPowerEnableRequest request);

// Client side call
DutPowerEnableResponse MtibRunner_DutChargePowerEnableRpc(cipher_unary_rpc_user_info_t *info, DutPowerEnableRequest request);

// Server side handler
DutVoltageSetResponse MtibRunner_DutVoltageSetHandler(DutVoltageSetRequest request);

// Client side call
DutVoltageSetResponse MtibRunner_DutVoltageSetRpc(cipher_unary_rpc_user_info_t *info, DutVoltageSetRequest request);

// Server side handler
DutCurrentReadResponse MtibRunner_DutCurrentReadHandler(DutCurrentReadRequest request);

// Client side call
DutCurrentReadResponse MtibRunner_DutCurrentReadRpc(cipher_unary_rpc_user_info_t *info, DutCurrentReadRequest request);

// Server side handler
DutVoltageReadResponse MtibRunner_DutVoltageReadHandler(DutVoltageReadRequest request);

// Client side call
DutVoltageReadResponse MtibRunner_DutVoltageReadRpc(cipher_unary_rpc_user_info_t *info, DutVoltageReadRequest request);

// Server side handler
DutPowerReadResponse MtibRunner_DutPowerReadHandler(DutPowerReadRequest request);

// Client side call
DutPowerReadResponse MtibRunner_DutPowerReadRpc(cipher_unary_rpc_user_info_t *info, DutPowerReadRequest request);

// Server side handler
AltimeterReadResponse MtibRunner_AltimeterReadHandler(AltimeterReadRequest request);

// Client side call
AltimeterReadResponse MtibRunner_AltimeterReadRpc(cipher_unary_rpc_user_info_t *info, AltimeterReadRequest request);

// Server side handler
AccelReadResponse MtibRunner_AccelReadHandler(AccelReadRequest request);

// Client side call
AccelReadResponse MtibRunner_AccelReadRpc(cipher_unary_rpc_user_info_t *info, AccelReadRequest request);

// Server side handler
AccelReadMaxResponse MtibRunner_AccelReadMaxForceHandler(AccelReadMaxRequest request);

// Client side call
AccelReadMaxResponse MtibRunner_AccelReadMaxForceRpc(cipher_unary_rpc_user_info_t *info, AccelReadMaxRequest request);

// Server side handler
EepromReadResponse MtibRunner_EepromReadHandler(EepromReadRequest request);

// Client side call
EepromReadResponse MtibRunner_EepromReadRpc(cipher_unary_rpc_user_info_t *info, EepromReadRequest request);

// Server side handler
EepromWriteResponse MtibRunner_EepromWriteHandler(EepromWriteRequest request);

// Client side call
EepromWriteResponse MtibRunner_EepromWriteRpc(cipher_unary_rpc_user_info_t *info, EepromWriteRequest request);

// Server side handler
ListFwFilesResponse MtibRunner_ListFwFilesHandler(ListFwFilesRequest request);

// Client side call
ListFwFilesResponse MtibRunner_ListFwFilesRpc(cipher_unary_rpc_user_info_t *info, ListFwFilesRequest request);

// Server side handler
UploadFwFileResponse MtibRunner_UploadFwFileHandler(UploadFwFileRequest request);

// Client side call
UploadFwFileResponse MtibRunner_UploadFwFileRpc(cipher_unary_rpc_user_info_t *info, UploadFwFileRequest request);

// Server side handler
DeleteFwFileResponse MtibRunner_DeleteFwFileHandler(DeleteFwFileRequest request);

// Client side call
DeleteFwFileResponse MtibRunner_DeleteFwFileRpc(cipher_unary_rpc_user_info_t *info, DeleteFwFileRequest request);

// Server side handler
FlashHexFileResponse MtibRunner_FlashHexFileHandler(FlashHexFileRequest request);

// Client side call
FlashHexFileResponse MtibRunner_FlashHexFileRpc(cipher_unary_rpc_user_info_t *info, FlashHexFileRequest request);

#endif // MTIB_RUNNER_CIPHER_H
