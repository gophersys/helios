#ifndef MTIB_RUNNER_CIPHER_H
#define MTIB_RUNNER_CIPHER_H

#include <corekinect/cipher/cipher.h>
#include "mtib_runner.pb.h"

// Service info registration function
cipher_service_info_t *get_mtibrunnerv1service_info(void);

// Server side handler
HealthCheckResponse MtibRunnerV1_HealthCheckHandler(Empty request);

// Client side call
HealthCheckResponse MtibRunnerV1_HealthCheckRpc(cipher_unary_rpc_user_info_t *info, Empty request);

// Server side handler
GetRunnerInfoResponse MtibRunnerV1_GetRunnerInfoHandler(Empty request);

// Client side call
GetRunnerInfoResponse MtibRunnerV1_GetRunnerInfoRpc(cipher_unary_rpc_user_info_t *info, Empty request);

// Server side handler
GpioConfigResponse MtibRunnerV1_GpioConfigHandler(GpioConfigRequest request);

// Client side call
GpioConfigResponse MtibRunnerV1_GpioConfigRpc(cipher_unary_rpc_user_info_t *info, GpioConfigRequest request);

// Server side handler
GpioWriteResponse MtibRunnerV1_GpioWriteHandler(GpioWriteRequest request);

// Client side call
GpioWriteResponse MtibRunnerV1_GpioWriteRpc(cipher_unary_rpc_user_info_t *info, GpioWriteRequest request);

// Server side handler
GpioReadResponse MtibRunnerV1_GpioReadHandler(GpioReadRequest request);

// Client side call
GpioReadResponse MtibRunnerV1_GpioReadRpc(cipher_unary_rpc_user_info_t *info, GpioReadRequest request);

// Server side handler
AdcReadResponse MtibRunnerV1_AdcReadHandler(AdcReadRequest request);

// Client side call
AdcReadResponse MtibRunnerV1_AdcReadRpc(cipher_unary_rpc_user_info_t *info, AdcReadRequest request);

// Server side handler
AdcReadAllResponse MtibRunnerV1_AdcReadAllHandler(AdcReadAllRequest request);

// Client side call
AdcReadAllResponse MtibRunnerV1_AdcReadAllRpc(cipher_unary_rpc_user_info_t *info, AdcReadAllRequest request);

// Server side handler
DutPowerResponse MtibRunnerV1_DutPowerEnableHandler(DutPowerRequest request);

// Client side call
DutPowerResponse MtibRunnerV1_DutPowerEnableRpc(cipher_unary_rpc_user_info_t *info, DutPowerRequest request);

// Server side handler
DutPowerResponse MtibRunnerV1_DutPowerDisableHandler(Empty request);

// Client side call
DutPowerResponse MtibRunnerV1_DutPowerDisableRpc(cipher_unary_rpc_user_info_t *info, Empty request);

// Server side handler
DutPowerResponse MtibRunnerV1_DutChargePowerEnableHandler(DutPowerRequest request);

// Client side call
DutPowerResponse MtibRunnerV1_DutChargePowerEnableRpc(cipher_unary_rpc_user_info_t *info, DutPowerRequest request);

// Server side handler
DutPowerResponse MtibRunnerV1_DutChargePowerDisableHandler(Empty request);

// Client side call
DutPowerResponse MtibRunnerV1_DutChargePowerDisableRpc(cipher_unary_rpc_user_info_t *info, Empty request);

// Server side handler
DutPowerReadResponse MtibRunnerV1_DutPowerReadHandler(Empty request);

// Client side call
DutPowerReadResponse MtibRunnerV1_DutPowerReadRpc(cipher_unary_rpc_user_info_t *info, Empty request);

// Server side handler
AltimeterReadResponse MtibRunnerV1_AltimeterReadHandler(Empty request);

// Client side call
AltimeterReadResponse MtibRunnerV1_AltimeterReadRpc(cipher_unary_rpc_user_info_t *info, Empty request);

// Server side handler
AccelReadResponse MtibRunnerV1_AccelReadHandler(Empty request);

// Client side call
AccelReadResponse MtibRunnerV1_AccelReadRpc(cipher_unary_rpc_user_info_t *info, Empty request);

// Server side handler
GetMotionStatusResponse MtibRunnerV1_GetMotionStatusHandler(Empty request);

// Client side call
GetMotionStatusResponse MtibRunnerV1_GetMotionStatusRpc(cipher_unary_rpc_user_info_t *info, Empty request);

// Server side handler
MotionHomeResponse MtibRunnerV1_MotionHomeHandler(Empty request);

// Client side call
MotionHomeResponse MtibRunnerV1_MotionHomeRpc(cipher_unary_rpc_user_info_t *info, Empty request);

// Server side handler
MotionTriggerResponse MtibRunnerV1_MotionTriggerHandler(MotionTriggerRequest request);

// Client side call
MotionTriggerResponse MtibRunnerV1_MotionTriggerRpc(cipher_unary_rpc_user_info_t *info, MotionTriggerRequest request);

// Server side handler
MotionContinuousResponse MtibRunnerV1_MotionContinuousHandler(MotionContinuousRequest request);

// Client side call
MotionContinuousResponse MtibRunnerV1_MotionContinuousRpc(cipher_unary_rpc_user_info_t *info, MotionContinuousRequest request);

// Server side handler
MotionStopResponse MtibRunnerV1_MotionStopHandler(Empty request);

// Client side call
MotionStopResponse MtibRunnerV1_MotionStopRpc(cipher_unary_rpc_user_info_t *info, Empty request);

// Server side handler
ListFwFilesResponse MtibRunnerV1_ListFwFilesHandler(Empty request);

// Client side call
ListFwFilesResponse MtibRunnerV1_ListFwFilesRpc(cipher_unary_rpc_user_info_t *info, Empty request);

// Server side handler
UploadFwFileResponse MtibRunnerV1_UploadFwFileHandler(UploadFwFileRequest request);

// Client side call
UploadFwFileResponse MtibRunnerV1_UploadFwFileRpc(cipher_unary_rpc_user_info_t *info, UploadFwFileRequest request);

// Server side handler
DeleteFwFileResponse MtibRunnerV1_DeleteFwFileHandler(DeleteFwFileRequest request);

// Client side call
DeleteFwFileResponse MtibRunnerV1_DeleteFwFileRpc(cipher_unary_rpc_user_info_t *info, DeleteFwFileRequest request);

// Server side handler
FlashFwFileResponse MtibRunnerV1_FlashFwFileHandler(FlashFwFileRequest request);

// Client side call
FlashFwFileResponse MtibRunnerV1_FlashFwFileRpc(cipher_unary_rpc_user_info_t *info, FlashFwFileRequest request);

// Server side handler
UartStreamResponse MtibRunnerV1_UartStreamHandler(UartStreamRequest request);

// Client side call
UartStreamResponse MtibRunnerV1_UartStreamRpc(cipher_unary_rpc_user_info_t *info, UartStreamRequest request);

#endif // MTIB_RUNNER_CIPHER_H
