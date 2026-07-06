// Cipher RPC server node (downlink).
//
// Registers a "math" service exposing an "add" RPC operation, then runs the
// daemon. When an uplink invokes math.add, the worker thread executes the
// handler below and returns the sum.

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Cipher includes
#include <daemon/api.h>

// Shared RPC contract
#include "math_rpc.h"

LOG_MODULE_REGISTER(rpc_downlink);

#define CIPHER_PORT 5555

static cipher_daemon_t daemon_inst;

static cipher_daemon_config_t daemon_cfg =
{
    .device_id = 0x0001,
    .num_client_ifaces = 0,
    .num_server_ifaces = 1,
    .server_ifaces =
    {
        {
            .type = IFACE_TYPE_SOCKET,
            .link = IFACE_LINK_TYPE_SERVER,
            .port = CIPHER_PORT,
        },
    },
};

/*-----------------------------------------------------------------------------------------------------
 *                                                                                          RPC Handler
 *---------------------------------------------------------------------------------------------------*/

// Invoked by the daemon's RPC worker thread. request/response point at heap
// buffers the worker allocated (sized from the ops entry below).
static cipher_rpc_err_t add_handler(void *request, void *response)
{
    const math_add_request_t *req = request;
    math_add_response_t *resp = response;

    resp->sum = req->a + req->b;
    LOG_INF("RPC math.add(%u, %u) = %u", req->a, req->b, resp->sum);

    return CIPHER_RPC_ERR_OK;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                     Service Registry
 *---------------------------------------------------------------------------------------------------*/

static cipher_ops_entry_t math_ops[] =
{
    {
        .id = MATH_OP_ADD,
        .type = CIPHER_OPS_TYPE_RPC,
        .name = "add",
        .op =
        {
            .rpc =
            {
                .request_size = sizeof(math_add_request_t),
                .response_size = sizeof(math_add_response_t),
                .handler = add_handler,
                .supports_parallelism = false,
            },
        },
    },
};

static cipher_service_entry_t math_services[] =
{
    {
        .service =
        {
            .id = MATH_SERVICE_ID,
            .name = "math",
            .allowed_hops = 1,
            .ops = math_ops,
            .num_ops = 1,
        },
    },
};

int main(void)
{
    LOG_INF("cipher RPC downlink booting (device 0x%04x, port %d)",
            daemon_cfg.device_id, CIPHER_PORT);

    cipher_daemon_init(&daemon_cfg, &daemon_inst);
    cipher_register_local_services(&daemon_inst, math_services, ARRAY_SIZE(math_services));
    cipher_daemon_start(&daemon_inst);

    while (true)
    {
        k_sleep(K_SECONDS(30));
        LOG_INF("downlink alive");
    }

    return 0;
}
