#include "mtib_controller.cipher.h"

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/iface/iface.h>
#include <corekinect/cipher/cipher.h>

// Protobuf includes
#include "mtib_controller.pb.h"

LOG_MODULE_REGISTER(mtibcontroller);

#define MTIBCONTROLLER_SERVICE_ID 1

typedef enum
{
    rpc_Reset = 1,
    rpc_HealthCheck = 2,
    rpc_GetClusterInfo = 3,
    rpc_ListTests = 4,
    rpc_ExecuteBoardTest = 5,
    rpc_ExecutePanelTest = 6,
} MtibController_rpc;

// Server side
static bool MtibController_ResetHandlerImplemented = true;
__attribute__((weak)) ResetResponse MtibController_ResetHandler(ResetRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibController_ResetHandlerImplemented = false;
    ResetResponse response  = {0};
    return response ;
}

cipher_rpc_err_t ResetRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((ResetResponse *)response ) = MtibController_ResetHandler(*((ResetRequest *)request));
    return MtibController_ResetHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibController_HealthCheckHandlerImplemented = true;
__attribute__((weak)) HealthCheckResponse MtibController_HealthCheckHandler(HealthCheckRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibController_HealthCheckHandlerImplemented = false;
    HealthCheckResponse response  = {0};
    return response ;
}

cipher_rpc_err_t HealthCheckRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((HealthCheckResponse *)response ) = MtibController_HealthCheckHandler(*((HealthCheckRequest *)request));
    return MtibController_HealthCheckHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibController_GetClusterInfoHandlerImplemented = true;
__attribute__((weak)) GetClusterInfoResponse MtibController_GetClusterInfoHandler(GetClusterInfoRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibController_GetClusterInfoHandlerImplemented = false;
    GetClusterInfoResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GetClusterInfoRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GetClusterInfoResponse *)response ) = MtibController_GetClusterInfoHandler(*((GetClusterInfoRequest *)request));
    return MtibController_GetClusterInfoHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibController_ListTestsHandlerImplemented = true;
__attribute__((weak)) ListTestsResponse MtibController_ListTestsHandler(ListTestsRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibController_ListTestsHandlerImplemented = false;
    ListTestsResponse response  = {0};
    return response ;
}

cipher_rpc_err_t ListTestsRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((ListTestsResponse *)response ) = MtibController_ListTestsHandler(*((ListTestsRequest *)request));
    return MtibController_ListTestsHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibController_ExecuteBoardTestHandlerImplemented = true;
__attribute__((weak)) ExecuteBoardTestResponse MtibController_ExecuteBoardTestHandler(ExecuteBoardTestRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibController_ExecuteBoardTestHandlerImplemented = false;
    ExecuteBoardTestResponse response  = {0};
    return response ;
}

cipher_rpc_err_t ExecuteBoardTestRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((ExecuteBoardTestResponse *)response ) = MtibController_ExecuteBoardTestHandler(*((ExecuteBoardTestRequest *)request));
    return MtibController_ExecuteBoardTestHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool MtibController_ExecutePanelTestHandlerImplemented = true;
__attribute__((weak)) ExecutePanelTestResponse MtibController_ExecutePanelTestHandler(ExecutePanelTestRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    MtibController_ExecutePanelTestHandlerImplemented = false;
    ExecutePanelTestResponse response  = {0};
    return response ;
}

cipher_rpc_err_t ExecutePanelTestRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((ExecutePanelTestResponse *)response ) = MtibController_ExecutePanelTestHandler(*((ExecutePanelTestRequest *)request));
    return MtibController_ExecutePanelTestHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Client side
ResetResponse MtibController_ResetRpc(cipher_unary_rpc_user_info_t *info, ResetRequest request)
{
    ResetResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCONTROLLER_SERVICE_ID,
        .rpc_id = rpc_Reset,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
HealthCheckResponse MtibController_HealthCheckRpc(cipher_unary_rpc_user_info_t *info, HealthCheckRequest request)
{
    HealthCheckResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCONTROLLER_SERVICE_ID,
        .rpc_id = rpc_HealthCheck,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GetClusterInfoResponse MtibController_GetClusterInfoRpc(cipher_unary_rpc_user_info_t *info, GetClusterInfoRequest request)
{
    GetClusterInfoResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCONTROLLER_SERVICE_ID,
        .rpc_id = rpc_GetClusterInfo,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
ListTestsResponse MtibController_ListTestsRpc(cipher_unary_rpc_user_info_t *info, ListTestsRequest request)
{
    ListTestsResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCONTROLLER_SERVICE_ID,
        .rpc_id = rpc_ListTests,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
ExecuteBoardTestResponse MtibController_ExecuteBoardTestRpc(cipher_unary_rpc_user_info_t *info, ExecuteBoardTestRequest request)
{
    ExecuteBoardTestResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCONTROLLER_SERVICE_ID,
        .rpc_id = rpc_ExecuteBoardTest,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
ExecutePanelTestResponse MtibController_ExecutePanelTestRpc(cipher_unary_rpc_user_info_t *info, ExecutePanelTestRequest request)
{
    ExecutePanelTestResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = MTIBCONTROLLER_SERVICE_ID,
        .rpc_id = rpc_ExecutePanelTest,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}

static cipher_rpc_info_t mtibcontroller_rpcs[] =
{
    {
        .id = rpc_Reset,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "Reset",
        .handler = ResetRpcPrvHandler,
        .request_info = {
            .fields = ResetRequest_fields,
            .encoded_size = ResetRequest_size,
            .decoded_size = sizeof(ResetRequest)
        },
        .response_info = {
            .fields = ResetResponse_fields,
            .encoded_size = ResetResponse_size,
            .decoded_size = sizeof(ResetResponse)
        },
        .supports_parallelism = true,
    },
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
        .id = rpc_ExecuteBoardTest,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "ExecuteBoardTest",
        .handler = ExecuteBoardTestRpcPrvHandler,
        .request_info = {
            .fields = ExecuteBoardTestRequest_fields,
            .encoded_size = ExecuteBoardTestRequest_size,
            .decoded_size = sizeof(ExecuteBoardTestRequest)
        },
        .response_info = {
            .fields = ExecuteBoardTestResponse_fields,
            .encoded_size = ExecuteBoardTestResponse_size,
            .decoded_size = sizeof(ExecuteBoardTestResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_ExecutePanelTest,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "ExecutePanelTest",
        .handler = ExecutePanelTestRpcPrvHandler,
        .request_info = {
            .fields = ExecutePanelTestRequest_fields,
            .encoded_size = ExecutePanelTestRequest_size,
            .decoded_size = sizeof(ExecutePanelTestRequest)
        },
        .response_info = {
            .fields = ExecutePanelTestResponse_fields,
            .encoded_size = ExecutePanelTestResponse_size,
            .decoded_size = sizeof(ExecutePanelTestResponse)
        },
        .supports_parallelism = true,
    },
};

static cipher_service_info_t mtibcontroller_service =
{
    .id = MTIBCONTROLLER_SERVICE_ID,
    .name = "MtibController",
    .max_hops = 1,
    .rpcs = mtibcontroller_rpcs,
    .num_rpcs = ARRAY_SIZE(mtibcontroller_rpcs),
};

cipher_service_info_t *get_mtibcontrollerservice_info(void)
{
    return &mtibcontroller_service;
}
