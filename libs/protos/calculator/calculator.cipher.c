#include "calculator.cipher.h"

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/iface/iface.h>
#include <corekinect/cipher/cipher.h>

// Protobuf includes
#include "calculator.pb.h"

LOG_MODULE_REGISTER(calculator);

#define CALCULATOR_SERVICE_ID 1

typedef enum
{
    rpc_AddIntegers = 1,
} Calculator_rpc;

// Server side
static bool Calculator_AddIntegersHandlerImplemented = true;
__attribute__((weak)) AddIntegersResponse Calculator_AddIntegersHandler(AddIntegersRequest request)
{
    LOG_WRN("%s default implementation called", __func__);
    Calculator_AddIntegersHandlerImplemented = false;
    AddIntegersResponse response  = {0};
    return response ;
}

cipher_rpc_err_t AddIntegersRpcPrvHandler(void *request, void *response)
{
    // Call the actual handler function
    *((AddIntegersResponse *)response ) = Calculator_AddIntegersHandler(*((AddIntegersRequest *)request));
    return Calculator_AddIntegersHandlerImplemented ? CIPHER_RPC_ERR_OK : CIPHER_RPC_ERR_NOT_IMPLEMENTED;
}

// Client side
AddIntegersResponse Calculator_AddIntegersRpc(cipher_unary_rpc_user_info_t *info, AddIntegersRequest request)
{
    AddIntegersResponse response  = {0};

    cipher_daemon_rpc_context_t context =
    {
        .local = true,
        .user_info = info,
        .service_id = CALCULATOR_SERVICE_ID,
        .rpc_id = rpc_AddIntegers,
        .request_struct = &request,
        .request_struct_size = sizeof(request),
        .response_struct = &response ,
        .response_struct_size = sizeof(response)
    };

    cipher_daemon_execute_remote_rpc(&context);
    return response;
}

static cipher_rpc_info_t calculator_rpcs[] =
{
    {
        .id = rpc_AddIntegers,
        .type = CIPHER_RPC_TYPE_UNARY,
        .name = "AddIntegers",
        .handler = AddIntegersRpcPrvHandler,
        .request_info = {
            .fields = AddIntegersRequest_fields,
            .encoded_size = AddIntegersRequest_size,
            .decoded_size = sizeof(AddIntegersRequest)
        },
        .response_info = {
            .fields = AddIntegersResponse_fields,
            .encoded_size = AddIntegersResponse_size,
            .decoded_size = sizeof(AddIntegersResponse)
        },
        .supports_parallelism = true,
    },
};

static cipher_service_info_t calculator_service =
{
    .id = CALCULATOR_SERVICE_ID,
    .name = "Calculator",
    .max_hops = 1,
    .rpcs = calculator_rpcs,
    .num_rpcs = ARRAY_SIZE(calculator_rpcs),
};

cipher_service_info_t *get_calculatorservice_info(void)
{
    return &calculator_service;
}
