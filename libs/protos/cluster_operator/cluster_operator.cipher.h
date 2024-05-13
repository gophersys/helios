#ifndef CLUSTER_OPERATOR_CIPHER_H
#define CLUSTER_OPERATOR_CIPHER_H

#include <corekinect/cipher/cipher.h>
#include "cluster_operator.pb.h"

// Service info registration function
cipher_service_info_t *get_clusteroperatorservice_info(void);

// Server side handler
HealthCheckResponse ClusterOperator_HealthCheckHandler(HealthCheckRequest request);

// Client side call
HealthCheckResponse ClusterOperator_HealthCheckRpc(cipher_unary_rpc_user_info_t *info, HealthCheckRequest request);

// Server side handler
GetClusterInfoResponse ClusterOperator_GetClusterInfoHandler(GetClusterInfoRequest request);

// Client side call
GetClusterInfoResponse ClusterOperator_GetClusterInfoRpc(cipher_unary_rpc_user_info_t *info, GetClusterInfoRequest request);

// Server side handler
GetDeploymentInfoResponse ClusterOperator_GetDeploymentInfoHandler(GetDeploymentInfoRequest request);

// Client side call
GetDeploymentInfoResponse ClusterOperator_GetDeploymentInfoRpc(cipher_unary_rpc_user_info_t *info, GetDeploymentInfoRequest request);

// Server side handler
ListTestsResponse ClusterOperator_ListTestsHandler(ListTestsRequest request);

// Client side call
ListTestsResponse ClusterOperator_ListTestsRpc(cipher_unary_rpc_user_info_t *info, ListTestsRequest request);

// Server side handler
ExecuteTestResponse ClusterOperator_ExecuteTestHandler(ExecuteTestRequest request);

// Client side call
ExecuteTestResponse ClusterOperator_ExecuteTestRpc(cipher_unary_rpc_user_info_t *info, ExecuteTestRequest request);

// Server side handler
StopTestResponse ClusterOperator_StopTestHandler(StopTestRequest request);

// Client side call
StopTestResponse ClusterOperator_StopTestRpc(cipher_unary_rpc_user_info_t *info, StopTestRequest request);

// Server side handler
RegisterTestResponse ClusterOperator_RegisterTestHandler(RegisterTestRequest request);

// Client side call
RegisterTestResponse ClusterOperator_RegisterTestRpc(cipher_unary_rpc_user_info_t *info, RegisterTestRequest request);

#endif // CLUSTER_OPERATOR_CIPHER_H
