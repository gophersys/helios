#ifndef TEST_CASE_CIPHER_H
#define TEST_CASE_CIPHER_H

#include <corekinect/cipher/cipher.h>
#include "test_case.pb.h"

// Service info registration function
cipher_service_info_t *get_testcaseruntimeserviceservice_info(void);

// Server side handler
HealthCheckResponse TestCaseRuntimeService_HealthCheckHandler(Empty request);

// Client side call
HealthCheckResponse TestCaseRuntimeService_HealthCheckRpc(cipher_unary_rpc_user_info_t *info, Empty request);

// Server side handler
GetTestInfoResponse TestCaseRuntimeService_GetTestInfoHandler(Empty request);

// Client side call
GetTestInfoResponse TestCaseRuntimeService_GetTestInfoRpc(cipher_unary_rpc_user_info_t *info, Empty request);

// Server side handler
RunResponse TestCaseRuntimeService_RunHandler(RunRequest request);

// Client side call
RunResponse TestCaseRuntimeService_RunRpc(cipher_unary_rpc_user_info_t *info, RunRequest request);

// Server side handler
StopResponse TestCaseRuntimeService_StopHandler(StopRequest request);

// Client side call
StopResponse TestCaseRuntimeService_StopRpc(cipher_unary_rpc_user_info_t *info, StopRequest request);

// Server side handler
GetAssetsResponse TestCaseRuntimeService_GetAssetsHandler(Empty request);

// Client side call
GetAssetsResponse TestCaseRuntimeService_GetAssetsRpc(cipher_unary_rpc_user_info_t *info, Empty request);

// Server side handler
GetAssetRequest TestCaseRuntimeService_GetAssetHandler(GetAssetRequest request);

// Client side call
GetAssetRequest TestCaseRuntimeService_GetAssetRpc(cipher_unary_rpc_user_info_t *info, GetAssetRequest request);

#endif // TEST_CASE_CIPHER_H
