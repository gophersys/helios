#ifndef CLUSTER_TEST_CIPHER_H
#define CLUSTER_TEST_CIPHER_H

#include <corekinect/cipher/cipher.h>
#include "cluster_test.pb.h"

// Service info registration function
cipher_service_info_t *get_clustertestservice_info(void);

// Server side handler
HealthCheckResponse ClusterTest_HealthCheckHandler(HealthCheckRequest request);

// Client side call
HealthCheckResponse ClusterTest_HealthCheckRpc(cipher_unary_rpc_user_info_t *info, HealthCheckRequest request);

// Server side handler
ExecuteResponse ClusterTest_ExecuteHandler(ExecuteRequest request);

// Client side call
ExecuteResponse ClusterTest_ExecuteRpc(cipher_unary_rpc_user_info_t *info, ExecuteRequest request);

// Server side handler
StopResponse ClusterTest_StopHandler(StopRequest request);

// Client side call
StopResponse ClusterTest_StopRpc(cipher_unary_rpc_user_info_t *info, StopRequest request);

#endif // CLUSTER_TEST_CIPHER_H
