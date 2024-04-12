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
GetOperatorInfoResponse ClusterOperator_GetOperatorInfoHandler(GetOperatorInfoRequest request);

// Client side call
GetOperatorInfoResponse ClusterOperator_GetOperatorInfoRpc(cipher_unary_rpc_user_info_t *info, GetOperatorInfoRequest request);

// Server side handler
GetDeploymentInfoResponse ClusterOperator_GetDeploymentInfoHandler(GetDeploymentInfoRequest request);

// Client side call
GetDeploymentInfoResponse ClusterOperator_GetDeploymentInfoRpc(cipher_unary_rpc_user_info_t *info, GetDeploymentInfoRequest request);

// Server side handler
RegisterTestResponse ClusterOperator_RegisterTestHandler(RegisterTestRequest request);

// Client side call
RegisterTestResponse ClusterOperator_RegisterTestRpc(cipher_unary_rpc_user_info_t *info, RegisterTestRequest request);

// Server side handler
ListTestsResponse ClusterOperator_ListTestsHandler(ListTestsRequest request);

// Client side call
ListTestsResponse ClusterOperator_ListTestsRpc(cipher_unary_rpc_user_info_t *info, ListTestsRequest request);

// Server side handler
cluster_test.ExecuteTestResponse ClusterOperator_ExecuteTestHandler(cluster_test.ExecuteTestRequest request);

// Client side call
cluster_test.ExecuteTestResponse ClusterOperator_ExecuteTestRpc(cipher_unary_rpc_user_info_t *info, cluster_test.ExecuteTestRequest request);

#endif // CLUSTER_OPERATOR_CIPHER_H
