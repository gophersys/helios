#include "test_case.cipher.h"

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/iface/iface.h>
#include <corekinect/cipher/cipher.h>

// Protobuf includes
#include "test_case.pb.h"

LOG_MODULE_REGISTER(testcaseruntimeservice);

#define TESTCASERUNTIMESERVICE_SERVICE_ID 1

typedef enum
{
    rpc_HealthCheck = 1,
    rpc_GetTestInfo = 2,
    rpc_Run = 3,
    rpc_Stop = 4,
    rpc_GetAssets = 5,
    rpc_GetAsset = 6,
} TestCaseRuntimeService_rpc;

// Server side
static bool TestCaseRuntimeService_HealthCheckHandlerImplemented = true;
__attribute__((weak)) HealthCheckResponse TestCaseRuntimeService_HealthCheckHandler(Empty request)
{
    LOG_WRN("%s default implementation called", __func__);
    TestCaseRuntimeService_HealthCheckHandlerImplemented = false;
    HealthCheckResponse response  = {0};
    return response ;
}

cipher_rpc_err_t HealthCheckRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((HealthCheckResponse *)response ) = TestCaseRuntimeService_HealthCheckHandler(*((Empty *)request));
    return TestCaseRuntimeService_HealthCheckHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool TestCaseRuntimeService_GetTestInfoHandlerImplemented = true;
__attribute__((weak)) GetTestInfoResponse TestCaseRuntimeService_GetTestInfoHandler(Empty request)
{
    LOG_WRN("%s default implementation called", __func__);
    TestCaseRuntimeService_GetTestInfoHandlerImplemented = false;
    GetTestInfoResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GetTestInfoRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GetTestInfoResponse *)response ) = TestCaseRuntimeService_GetTestInfoHandler(*((Empty *)request));
    return TestCaseRuntimeService_GetTestInfoHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool TestCaseRuntimeService_RunHandlerImplemented = true;
__attribute__((weak)) RunResponse TestCaseRuntimeService_RunHandler(RunRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    TestCaseRuntimeService_RunHandlerImplemented = false;
    RunResponse response  = {0};
    return response ;
}

cipher_rpc_err_t RunRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((RunResponse *)response ) = TestCaseRuntimeService_RunHandler(*((RunRequest *)request));
    return TestCaseRuntimeService_RunHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool TestCaseRuntimeService_StopHandlerImplemented = true;
__attribute__((weak)) StopResponse TestCaseRuntimeService_StopHandler(StopRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    TestCaseRuntimeService_StopHandlerImplemented = false;
    StopResponse response  = {0};
    return response ;
}

cipher_rpc_err_t StopRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((StopResponse *)response ) = TestCaseRuntimeService_StopHandler(*((StopRequest *)request));
    return TestCaseRuntimeService_StopHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool TestCaseRuntimeService_GetAssetsHandlerImplemented = true;
__attribute__((weak)) GetAssetsResponse TestCaseRuntimeService_GetAssetsHandler(Empty request)
{
    LOG_WRN("%s default implementation called", __func__);
    TestCaseRuntimeService_GetAssetsHandlerImplemented = false;
    GetAssetsResponse response  = {0};
    return response ;
}

cipher_rpc_err_t GetAssetsRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GetAssetsResponse *)response ) = TestCaseRuntimeService_GetAssetsHandler(*((Empty *)request));
    return TestCaseRuntimeService_GetAssetsHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Server side
static bool TestCaseRuntimeService_GetAssetHandlerImplemented = true;
__attribute__((weak)) GetAssetRequest TestCaseRuntimeService_GetAssetHandler(GetAssetRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    TestCaseRuntimeService_GetAssetHandlerImplemented = false;
    GetAssetRequest response  = {0};
    return response ;
}

cipher_rpc_err_t GetAssetRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((GetAssetRequest *)response ) = TestCaseRuntimeService_GetAssetHandler(*((GetAssetRequest *)request));
    return TestCaseRuntimeService_GetAssetHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Client side
HealthCheckResponse TestCaseRuntimeService_HealthCheckRpc(cipher_unary_rpc_user_info_t *info, Empty request)
{
    HealthCheckResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = TESTCASERUNTIMESERVICE_SERVICE_ID,
        .rpc_id = rpc_HealthCheck,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GetTestInfoResponse TestCaseRuntimeService_GetTestInfoRpc(cipher_unary_rpc_user_info_t *info, Empty request)
{
    GetTestInfoResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = TESTCASERUNTIMESERVICE_SERVICE_ID,
        .rpc_id = rpc_GetTestInfo,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
RunResponse TestCaseRuntimeService_RunRpc(cipher_unary_rpc_user_info_t *info, RunRequest request)
{
    RunResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = TESTCASERUNTIMESERVICE_SERVICE_ID,
        .rpc_id = rpc_Run,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
StopResponse TestCaseRuntimeService_StopRpc(cipher_unary_rpc_user_info_t *info, StopRequest request)
{
    StopResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = TESTCASERUNTIMESERVICE_SERVICE_ID,
        .rpc_id = rpc_Stop,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GetAssetsResponse TestCaseRuntimeService_GetAssetsRpc(cipher_unary_rpc_user_info_t *info, Empty request)
{
    GetAssetsResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = TESTCASERUNTIMESERVICE_SERVICE_ID,
        .rpc_id = rpc_GetAssets,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}
GetAssetRequest TestCaseRuntimeService_GetAssetRpc(cipher_unary_rpc_user_info_t *info, GetAssetRequest request)
{
    GetAssetRequest response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = TESTCASERUNTIMESERVICE_SERVICE_ID,
        .rpc_id = rpc_GetAsset,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}

static cipher_rpc_info_t testcaseruntimeservice_rpcs[] =
{
    {
        .id = rpc_HealthCheck,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "HealthCheck",
        .handler = HealthCheckRpcPrvHandler,
        .request_info = {
            .fields = Empty_fields,
            .encoded_size = Empty_size,
            .decoded_size = sizeof(Empty)
        },
        .response_info = {
            .fields = HealthCheckResponse_fields,
            .encoded_size = HealthCheckResponse_size,
            .decoded_size = sizeof(HealthCheckResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_GetTestInfo,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "GetTestInfo",
        .handler = GetTestInfoRpcPrvHandler,
        .request_info = {
            .fields = Empty_fields,
            .encoded_size = Empty_size,
            .decoded_size = sizeof(Empty)
        },
        .response_info = {
            .fields = GetTestInfoResponse_fields,
            .encoded_size = GetTestInfoResponse_size,
            .decoded_size = sizeof(GetTestInfoResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_Run,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "Run",
        .handler = RunRpcPrvHandler,
        .request_info = {
            .fields = RunRequest_fields,
            .encoded_size = RunRequest_size,
            .decoded_size = sizeof(RunRequest)
        },
        .response_info = {
            .fields = RunResponse_fields,
            .encoded_size = RunResponse_size,
            .decoded_size = sizeof(RunResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_Stop,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "Stop",
        .handler = StopRpcPrvHandler,
        .request_info = {
            .fields = StopRequest_fields,
            .encoded_size = StopRequest_size,
            .decoded_size = sizeof(StopRequest)
        },
        .response_info = {
            .fields = StopResponse_fields,
            .encoded_size = StopResponse_size,
            .decoded_size = sizeof(StopResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_GetAssets,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "GetAssets",
        .handler = GetAssetsRpcPrvHandler,
        .request_info = {
            .fields = Empty_fields,
            .encoded_size = Empty_size,
            .decoded_size = sizeof(Empty)
        },
        .response_info = {
            .fields = GetAssetsResponse_fields,
            .encoded_size = GetAssetsResponse_size,
            .decoded_size = sizeof(GetAssetsResponse)
        },
        .supports_parallelism = true,
    },
    {
        .id = rpc_GetAsset,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "GetAsset",
        .handler = GetAssetRpcPrvHandler,
        .request_info = {
            .fields = GetAssetRequest_fields,
            .encoded_size = GetAssetRequest_size,
            .decoded_size = sizeof(GetAssetRequest)
        },
        .response_info = {
            .fields = GetAssetRequest_fields,
            .encoded_size = GetAssetRequest_size,
            .decoded_size = sizeof(GetAssetRequest)
        },
        .supports_parallelism = true,
    },
};

static cipher_service_info_t testcaseruntimeservice_service =
{
    .id = TESTCASERUNTIMESERVICE_SERVICE_ID,
    .name = "TestCaseRuntimeService",
    .max_hops = 1,
    .rpcs = testcaseruntimeservice_rpcs,
    .num_rpcs = ARRAY_SIZE(testcaseruntimeservice_rpcs),
};

cipher_service_info_t *get_testcaseruntimeserviceservice_info(void)
{
    return &testcaseruntimeservice_service;
}
