#include "cipher_tests.h"

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/random/rand32.h>

// Cipher includes
#include "daemon/api.h"
#include "daemon/daemon.h"
#include "daemon/fifo.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/

LOG_MODULE_REGISTER(rpc_test, DAEMON_LOG_LEVEL);

#define SERVICE_ID 25
#define DEVICE_ID 255
#define RAND_OP_ID 1

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                Types
 *---------------------------------------------------------------------------------------------------*/

typedef struct {
    bool _64bit;
} rand_request_t;

typedef struct {
    uint32_t rand32;
    uint64_t rand64;
} rand_response_t;

static bool intentional_timeout_active = false;
static uint32_t intentional_tiemout_ms = 0;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                       Remote RPC API
 *---------------------------------------------------------------------------------------------------*/

rand_response_t rand_rpc(cipher_daemon_t* d, cipher_rpc_user_info_t* info, rand_request_t request) {

    // Response buffer
    rand_response_t response = {0};

    // RPC entry info
    cipher_rpc_entry_t rpc_entry = {
        .service_id = SERVICE_ID,
        .op_id = RAND_OP_ID,
        .request = &request,
        .request_size = sizeof(request),
        .response = &response,
        .response_size = sizeof(response),
        .user_info = info,
    };
    sys_rand_get(&rpc_entry.id, sizeof(rpc_entry.id));

    // Call general purpose RPC handler
    cipher_remote_rpc_handler(d, &rpc_entry);

    return response;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                  Local RPC callbacks
 *---------------------------------------------------------------------------------------------------*/
static bool rand_handler_implemented = true;
rand_response_t rand_handler(rand_request_t request) {

    DBG("Executing %s with request %d", __func__, request._64bit);

    rand_response_t response = {0};
    if (request._64bit) {
        sys_rand_get(&response.rand64, sizeof(uint64_t));
    } else {
        sys_rand_get(&response.rand32, sizeof(uint32_t));
    }

    if (intentional_timeout_active) {
        k_msleep(intentional_tiemout_ms);
    }

    return response;
}

cipher_rpc_err_t rand_prv_handler(void* request, void* response) {

    rand_request_t* typed_request = (rand_request_t*)request;
    rand_response_t* typed_response = (rand_response_t*)response;

    *typed_response = rand_handler(*typed_request);

    if (!rand_handler_implemented) {
        return CIPHER_RPC_ERR_NOT_IMPLEMENTED;
    }

    return CIPHER_RPC_ERR_OK;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Service
 *---------------------------------------------------------------------------------------------------*/
cipher_ops_entry_t ops[] = {
    {
        .id = RAND_OP_ID,
        .type = CIPHER_OPS_TYPE_RPC,
        .name = "Rand",
        .op = {
            .rpc = {
                .handler = rand_prv_handler,
                .request_size = sizeof(rand_request_t),
                .response_size = sizeof(rand_response_t),
                .supports_parallelism = false,
            },
        },
    },
};

cipher_service_entry_t services[] = {
    {
        .local = true,
        .iface = NULL,
        .service = {
            .name = "RPC Test Service",
            .service_id = SERVICE_ID,
            .device_id = DEVICE_ID,
            .allowed_hops = 1,
            .ops = ops,
            .num_ops = ARRAY_SIZE(ops),
        },
    },
};

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                 Test
 *---------------------------------------------------------------------------------------------------*/
cipher_daemon_t d = {0};
#define POSIX_HOST_IP "127.0.0.1"
#define UPLINK_SOCKET 5000    // Client connects to this port
#define DOWNLINK_SOCKET 5000  // Server listens on this port

static cipher_daemon_config_t config = {
    .device_id = DEVICE_ID,
    .uplink_ifaces[0] = {
        .type = TAL_INTERFACE_TYPE_SOCKET,
        .link = TAL_LINK_TYPE_UPLINK,
        .host = POSIX_HOST_IP,
        .port = UPLINK_SOCKET,
    },
    .downlink_ifaces[0] = {
        .type = TAL_INTERFACE_TYPE_SOCKET,
        .link = TAL_LINK_TYPE_DOWNLINK,
        .host = POSIX_HOST_IP,
        .port = DOWNLINK_SOCKET,
    },
};

void cipher_test_rpc(void) {

    // Initialize the daemon
    cipher_daemon_init(&config, &d);

    // Register a test local service
    cipher_register_local_services(&d, services, ARRAY_SIZE(services));

    // Test 1: Test that a remote RPC will work
    intentional_timeout_active = true;
    intentional_tiemout_ms = 500;

    cipher_rpc_err_t err = CIPHER_RPC_ERR_OK;
    cipher_rpc_user_info_t info = {
        .device_id = DEVICE_ID,
        .error = &err,
        .timeout_ms = 100,
    };
    rand_request_t request = {
        ._64bit = true,
    };

    rand_response_t response = rand_rpc(&d, &info, request);
    if (info.error != CIPHER_RPC_ERR_OK) {
        WARN("This error shouldve returned OK");
    }

    (void)response;

    k_msleep(20000);

    // Test 2: Test a remote RPC executing on this host
    // cipher_packet_fifo_item_t* fifo_item = alloc_packet_fifo_item(&d, sizeof(rand_request_t));
    // CHECK_MALLOC(fifo_item);

    // cipher_header_t* header = &fifo_item->packet.header;
    // header->type = CIPHER_PACKET_TYPE_RPC;
    // header->destination_id = DEVICE_ID;
    // header->service_id = SERVICE_ID;
    // header->operation_id = 1;
    // CIPHER_SET_FLAG(header->flags, CIPHER_FLAG_RPC_REQUEST);

    // k_fifo_put(&d.rpc_packet_queue, fifo_item);
}