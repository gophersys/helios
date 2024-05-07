#include "cluster_operator.cipher.h"

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/iface/iface.h>
#include <corekinect/cipher/cipher.h>

// Protobuf includes
#include "cluster_operator.pb.h"

LOG_MODULE_REGISTER(clusteroperator);

#define CLUSTEROPERATOR_SERVICE_ID 1

typedef enum
{
    rpc_HealthCheck = 1,
    rpc_GetClusterInfo = 2,
    rpc_GetDeploymentInfo = 3,
    rpc_RegisterTest = 4,
    rpc_ListTests = 5,
    rpc_ExecuteManufacturingTest = 6,
} ClusterOperator_rpc;

// Server side
static bool ClusterOperator_HealthCheckHandlerImplemented = true;
__attribute__((weak)) HealthCheckResponse ClusterOperator_HealthCheckHandler(HealthCheckRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterOperator_HealthCheckHandlerImplemented = false;
    HealthCheckResponse response  = {0};
    return response ;
}

cipher_rpc_err_t HealthCheckRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((HealthCheckResponse *)response ) = ClusterOperator_HealthCheckHandler(*((HealthCheckRequest *)request));
    return ClusterOperator_HealthCheckHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterOperator_GetClusterInfoHandlerImplemented = true;
__attribute__((weak)) GetClusterInfoResponse ClusterOperator_GetClusterInfoHandler(GetClusterInfoRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterOperator_GetClusterInfoHandlerImplemented = false;
    GetClusterInfoResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GetClusterInfoRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GetClusterInfoResponse *)response ) = ClusterOperator_GetClusterInfoHandler(*((GetClusterInfoRequest *)request));
    return ClusterOperator_GetClusterInfoHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterOperator_GetDeploymentInfoHandlerImplemented = true;
__attribute__((weak)) GetDeploymentInfoResponse ClusterOperator_GetDeploymentInfoHandler(GetDeploymentInfoRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterOperator_GetDeploymentInfoHandlerImplemented = false;
    GetDeploymentInfoResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GetDeploymentInfoRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GetDeploymentInfoResponse *)response ) = ClusterOperator_GetDeploymentInfoHandler(*((GetDeploymentInfoRequest *)request));
    return ClusterOperator_GetDeploymentInfoHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterOperator_RegisterTestHandlerImplemented = true;
__attribute__((weak)) RegisterTestResponse ClusterOperator_RegisterTestHandler(RegisterTestRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterOperator_RegisterTestHandlerImplemented = false;
    RegisterTestResponse response  = {0};
    return response ;
}

cipher_rpc_err_t RegisterTestRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((RegisterTestResponse *)response ) = ClusterOperator_RegisterTestHandler(*((RegisterTestRequest *)request));
    return ClusterOperator_RegisterTestHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterOperator_ListTestsHandlerImplemented = true;
__attribute__((weak)) ListTestsResponse ClusterOperator_ListTestsHandler(ListTestsRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterOperator_ListTestsHandlerImplemented = false;
    ListTestsResponse response  = {0};
    return response ;
}

cipher_rpc_err_t ListTestsRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((ListTestsResponse *)response ) = ClusterOperator_ListTestsHandler(*((ListTestsRequest *)request));
    return ClusterOperator_ListTestsHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool ClusterOperator_ExecuteManufacturingTestHandlerImplemented = true;
__attribute__((weak)) cluster_test.ExecuteTestResponse ClusterOperator_ExecuteManufacturingTestHandler(cluster_test.ExecuteTestRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    ClusterOperator_ExecuteManufacturingTestHandlerImplemented = false;
    cluster_test.ExecuteTestResponse response  = {0};
    return response ;
}

cipher_rpc_err_t ExecuteManufacturingTestRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((cluster_test.ExecuteTestResponse *)response ) = ClusterOperator_ExecuteManufacturingTestHandler(*((cluster_test.ExecuteTestRequest *)request));
    return ClusterOperator_ExecuteManufacturingTestHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Client side
HealthCheckResponse ClusterOperator_HealthCheckRpc(cipher_unary_rpc_user_info_t *info, HealthCheckRequest request)
{
    HealthCheckResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTEROPERATOR_SERVICE_ID,
        .rpc_id = rpc_HealthCheck,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GetClusterInfoResponse ClusterOperator_GetClusterInfoRpc(cipher_unary_rpc_user_info_t *info, GetClusterInfoRequest request)
{
    GetClusterInfoResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTEROPERATOR_SERVICE_ID,
        .rpc_id = rpc_GetClusterInfo,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GetDeploymentInfoResponse ClusterOperator_GetDeploymentInfoRpc(cipher_unary_rpc_user_info_t *info, GetDeploymentInfoRequest request)
{
    GetDeploymentInfoResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTEROPERATOR_SERVICE_ID,
        .rpc_id = rpc_GetDeploymentInfo,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
RegisterTestResponse ClusterOperator_RegisterTestRpc(cipher_unary_rpc_user_info_t *info, RegisterTestRequest request)
{
    RegisterTestResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTEROPERATOR_SERVICE_ID,
        .rpc_id = rpc_RegisterTest,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
ListTestsResponse ClusterOperator_ListTestsRpc(cipher_unary_rpc_user_info_t *info, ListTestsRequest request)
{
    ListTestsResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTEROPERATOR_SERVICE_ID,
        .rpc_id = rpc_ListTests,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
cluster_test.ExecuteTestResponse ClusterOperator_ExecuteManufacturingTestRpc(cipher_unary_rpc_user_info_t *info, cluster_test.ExecuteTestRequest request)
{
    cluster_test.ExecuteTestResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CLUSTEROPERATOR_SERVICE_ID,
        .rpc_id = rpc_ExecuteManufacturingTest,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}

static cipher_rpc_info_t clusteroperator_rpcs[] =
{
    {
        .id = rpc_HealthCheck,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "HealthCheck",
        .handler = HealthCheckRpcPrvHandler,
        .request_info = {
            .fields = HealthCheckRequest_fields,
            .encoded_size = HealthCheckRequest_size,
            .decoded_size = sizeof(HealthCheckRequest)
        },
        .response_info = {
            .fields = HealthCheckResponse_fields,
            .encoded_size = HealthCheckResponse_size,
            .decoded_size = sizeof(HealthCheckResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_GetClusterInfo,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "GetClusterInfo",
        .handler = GetClusterInfoRpcPrvHandler,
        .request_info = {
            .fields = GetClusterInfoRequest_fields,
            .encoded_size = GetClusterInfoRequest_size,
            .decoded_size = sizeof(GetClusterInfoRequest)
        },
        .response_info = {
            .fields = GetClusterInfoResponse_fields,
            .encoded_size = GetClusterInfoResponse_size,
            .decoded_size = sizeof(GetClusterInfoResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_GetDeploymentInfo,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "GetDeploymentInfo",
        .handler = GetDeploymentInfoRpcPrvHandler,
        .request_info = {
            .fields = GetDeploymentInfoRequest_fields,
            .encoded_size = GetDeploymentInfoRequest_size,
            .decoded_size = sizeof(GetDeploymentInfoRequest)
        },
        .response_info = {
            .fields = GetDeploymentInfoResponse_fields,
            .encoded_size = GetDeploymentInfoResponse_size,
            .decoded_size = sizeof(GetDeploymentInfoResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_RegisterTest,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "RegisterTest",
        .handler = RegisterTestRpcPrvHandler,
        .request_info = {
            .fields = RegisterTestRequest_fields,
            .encoded_size = RegisterTestRequest_size,
            .decoded_size = sizeof(RegisterTestRequest)
        },
        .response_info = {
            .fields = RegisterTestResponse_fields,
            .encoded_size = RegisterTestResponse_size,
            .decoded_size = sizeof(RegisterTestResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_ListTests,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "ListTests",
        .handler = ListTestsRpcPrvHandler,
        .request_info = {
            .fields = ListTestsRequest_fields,
            .encoded_size = ListTestsRequest_size,
            .decoded_size = sizeof(ListTestsRequest)
        },
        .response_info = {
            .fields = ListTestsResponse_fields,
            .encoded_size = ListTestsResponse_size,
            .decoded_size = sizeof(ListTestsResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_ExecuteManufacturingTest,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "ExecuteManufacturingTest",
        .handler = ExecuteManufacturingTestRpcPrvHandler,
        .request_info = {
            .fields = cluster_test.ExecuteTestRequest_fields,
            .encoded_size = cluster_test.ExecuteTestRequest_size,
            .decoded_size = sizeof(cluster_test.ExecuteTestRequest)
        },
        .response_info = {
            .fields = cluster_test.ExecuteTestResponse_fields,
            .encoded_size = cluster_test.ExecuteTestResponse_size,
            .decoded_size = sizeof(cluster_test.ExecuteTestResponse)
        },
        .supports_parallelism = true,
    },
};

static cipher_service_info_t clusteroperator_service =
{
    .id = CLUSTEROPERATOR_SERVICE_ID,
    .name = "ClusterOperator",
    .max_hops = 1,
    .rpcs = clusteroperator_rpcs,
    .num_rpcs = ARRAY_SIZE(clusteroperator_rpcs),
};

cipher_service_info_t *get_clusteroperatorservice_info(void)
{
    return &clusteroperator_service;
}
