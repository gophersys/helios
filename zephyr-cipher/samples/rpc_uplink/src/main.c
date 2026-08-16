// Cipher RPC client node (uplink).
//
// Connects to the downlink, waits for service discovery to learn the remote
// math service, then invokes math.add over the network and prints the result
// returned by the remote handler.

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Cipher includes
#include <daemon/api.h>

// Shared RPC contract
#include "math_rpc.h"

LOG_MODULE_REGISTER(rpc_uplink);

#define CIPHER_SERVER_HOST CONFIG_CIPHER_SAMPLE_SERVER_HOST
#define CIPHER_PORT        5555
#define REMOTE_DEVICE_ID   0x0001

static cipher_daemon_t daemon_inst;

static cipher_daemon_config_t daemon_cfg =
{
    .device_id = 0x0002,
    .num_client_ifaces = 1,
    .num_server_ifaces = 0,
    .client_ifaces =
    {
        {
            .type = IFACE_TYPE_SOCKET,
            .link = IFACE_LINK_TYPE_CLIENT,
            .p_host = (char *)CIPHER_SERVER_HOST,
            .port = CIPHER_PORT,
        },
    },
};

int main(void)
{
    LOG_INF("cipher RPC uplink booting (device 0x%04x -> %s:%d)",
            daemon_cfg.device_id, CIPHER_SERVER_HOST, CIPHER_PORT);

    cipher_daemon_init(&daemon_cfg, &daemon_inst);
    cipher_daemon_start(&daemon_inst);

    // Give the connection + service discovery time to complete: the RPC needs
    // the device->interface route the daemon learns from the peer's traffic.
    k_sleep(K_SECONDS(5));

    for (uint32_t iteration = 1;; iteration++)
    {
        math_add_request_t request = {.a = iteration, .b = iteration * 2};
        math_add_response_t response = {0};

        cipher_unary_rpc_user_info_t info =
        {
            .device_id = REMOTE_DEVICE_ID,
            .timeout_ms = 3000,
        };

        cipher_registry_rpc_entry_t entry =
        {
            .id = (uint8_t)iteration,
            .service_id = MATH_SERVICE_ID,
            .op_id = MATH_OP_ADD,
            .request = &request,
            .request_size = sizeof(request),
            .response = &response,
            .response_size = sizeof(response),
            .user_info = &info,
        };

        LOG_INF("Invoking remote RPC math.add(%u, %u)...", request.a, request.b);
        cipher_rpc_handler(&daemon_inst, &entry);

        if (info.error == CIPHER_RPC_ERR_OK)
        {
            LOG_INF("RPC RESULT: math.add(%u, %u) = %u  %s",
                    request.a, request.b, response.sum,
                    (response.sum == request.a + request.b) ? "[VERIFIED]" : "[WRONG]");
        }
        else
        {
            LOG_ERR("RPC failed: error %d (%s)", info.error, cipher_rpc_err_str(info.error));
        }

        k_sleep(K_SECONDS(5));
    }

    return 0;
}
