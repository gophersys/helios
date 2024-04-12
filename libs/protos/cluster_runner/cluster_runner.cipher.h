#ifndef CLUSTER_RUNNER_CIPHER_H
#define CLUSTER_RUNNER_CIPHER_H

#include <corekinect/cipher/cipher.h>
#include "cluster_runner.pb.h"

// Service info registration function
cipher_service_info_t *get_clusterrunnerservice_info(void);

// Server side handler
HealthCheckResponse ClusterRunner_HealthCheckHandler(HealthCheckRequest request);

// Client side call
HealthCheckResponse ClusterRunner_HealthCheckRpc(cipher_unary_rpc_user_info_t *info, HealthCheckRequest request);

// Server side handler
GetRunnerInfoResponse ClusterRunner_GetRunnerInfoHandler(GetRunnerInfoRequest request);

// Client side call
GetRunnerInfoResponse ClusterRunner_GetRunnerInfoRpc(cipher_unary_rpc_user_info_t *info, GetRunnerInfoRequest request);

// Server side handler
ResetResponse ClusterRunner_ResetHandler(ResetRequest request);

// Client side call
ResetResponse ClusterRunner_ResetRpc(cipher_unary_rpc_user_info_t *info, ResetRequest request);

// Server side handler
GpioConfigResponse ClusterRunner_GpioConfigHandler(GpioConfigRequest request);

// Client side call
GpioConfigResponse ClusterRunner_GpioConfigRpc(cipher_unary_rpc_user_info_t *info, GpioConfigRequest request);

// Server side handler
GpioWriteResponse ClusterRunner_GpioWriteHandler(GpioWriteRequest request);

// Client side call
GpioWriteResponse ClusterRunner_GpioWriteRpc(cipher_unary_rpc_user_info_t *info, GpioWriteRequest request);

// Server side handler
GpioReadResponse ClusterRunner_GpioReadHandler(GpioReadRequest request);

// Client side call
GpioReadResponse ClusterRunner_GpioReadRpc(cipher_unary_rpc_user_info_t *info, GpioReadRequest request);

// Server side handler
AdcReadResponse ClusterRunner_AdcReadHandler(AdcReadRequest request);

// Client side call
AdcReadResponse ClusterRunner_AdcReadRpc(cipher_unary_rpc_user_info_t *info, AdcReadRequest request);

// Server side handler
AdcReadAllResponse ClusterRunner_AdcReadAllHandler(AdcReadAllRequest request);

// Client side call
AdcReadAllResponse ClusterRunner_AdcReadAllRpc(cipher_unary_rpc_user_info_t *info, AdcReadAllRequest request);

// Server side handler
DutPowerEnableResponse ClusterRunner_DutPowerEnableHandler(DutPowerEnableRequest request);

// Client side call
DutPowerEnableResponse ClusterRunner_DutPowerEnableRpc(cipher_unary_rpc_user_info_t *info, DutPowerEnableRequest request);

// Server side handler
DutPowerEnableResponse ClusterRunner_DutChargePowerEnableHandler(DutPowerEnableRequest request);

// Client side call
DutPowerEnableResponse ClusterRunner_DutChargePowerEnableRpc(cipher_unary_rpc_user_info_t *info, DutPowerEnableRequest request);

// Server side handler
DutVoltageSetResponse ClusterRunner_DutVoltageSetHandler(DutVoltageSetRequest request);

// Client side call
DutVoltageSetResponse ClusterRunner_DutVoltageSetRpc(cipher_unary_rpc_user_info_t *info, DutVoltageSetRequest request);

// Server side handler
DutCurrentReadResponse ClusterRunner_DutCurrentReadHandler(DutCurrentReadRequest request);

// Client side call
DutCurrentReadResponse ClusterRunner_DutCurrentReadRpc(cipher_unary_rpc_user_info_t *info, DutCurrentReadRequest request);

// Server side handler
DutVoltageReadResponse ClusterRunner_DutVoltageReadHandler(DutVoltageReadRequest request);

// Client side call
DutVoltageReadResponse ClusterRunner_DutVoltageReadRpc(cipher_unary_rpc_user_info_t *info, DutVoltageReadRequest request);

// Server side handler
DutPowerReadResponse ClusterRunner_DutPowerReadHandler(DutPowerReadRequest request);

// Client side call
DutPowerReadResponse ClusterRunner_DutPowerReadRpc(cipher_unary_rpc_user_info_t *info, DutPowerReadRequest request);

// Server side handler
AltimeterReadResponse ClusterRunner_AltimeterReadHandler(AltimeterReadRequest request);

// Client side call
AltimeterReadResponse ClusterRunner_AltimeterReadRpc(cipher_unary_rpc_user_info_t *info, AltimeterReadRequest request);

// Server side handler
AccelReadResponse ClusterRunner_AccelReadHandler(AccelReadRequest request);

// Client side call
AccelReadResponse ClusterRunner_AccelReadRpc(cipher_unary_rpc_user_info_t *info, AccelReadRequest request);

// Server side handler
AccelReadMaxResponse ClusterRunner_AccelReadMaxForceHandler(AccelReadMaxRequest request);

// Client side call
AccelReadMaxResponse ClusterRunner_AccelReadMaxForceRpc(cipher_unary_rpc_user_info_t *info, AccelReadMaxRequest request);

// Server side handler
EepromReadResponse ClusterRunner_EepromReadHandler(EepromReadRequest request);

// Client side call
EepromReadResponse ClusterRunner_EepromReadRpc(cipher_unary_rpc_user_info_t *info, EepromReadRequest request);

// Server side handler
EepromWriteResponse ClusterRunner_EepromWriteHandler(EepromWriteRequest request);

// Client side call
EepromWriteResponse ClusterRunner_EepromWriteRpc(cipher_unary_rpc_user_info_t *info, EepromWriteRequest request);

// Server side handler
ListFwFilesResponse ClusterRunner_ListFwFilesHandler(ListFwFilesRequest request);

// Client side call
ListFwFilesResponse ClusterRunner_ListFwFilesRpc(cipher_unary_rpc_user_info_t *info, ListFwFilesRequest request);

// Server side handler
UploadFwFileResponse ClusterRunner_UploadFwFileHandler(UploadFwFileRequest request);

// Client side call
UploadFwFileResponse ClusterRunner_UploadFwFileRpc(cipher_unary_rpc_user_info_t *info, UploadFwFileRequest request);

// Server side handler
DeleteFwFileResponse ClusterRunner_DeleteFwFileHandler(DeleteFwFileRequest request);

// Client side call
DeleteFwFileResponse ClusterRunner_DeleteFwFileRpc(cipher_unary_rpc_user_info_t *info, DeleteFwFileRequest request);

// Server side handler
FlashHexFileResponse ClusterRunner_FlashHexFileHandler(FlashHexFileRequest request);

// Client side call
FlashHexFileResponse ClusterRunner_FlashHexFileRpc(cipher_unary_rpc_user_info_t *info, FlashHexFileRequest request);

#endif // CLUSTER_RUNNER_CIPHER_H
