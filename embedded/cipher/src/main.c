// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(app);

// Cipher includes
#include "cipher/test/include/cipher_tests.h"
#include "daemon/api.h"
#include "daemon/fifo.h"
#include "daemon/registry.h"
#include "utils/err.h"

// App includes
#include "autogen/autogen.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Daemon Config
 *---------------------------------------------------------------------------------------------------*/

#define POSIX_HOST_IP "192.168.0.110"
#define UPLINK_SOCKET 5000
#define DOWNLINK_SOCKET 5001

static cipher_daemon_config_t config = {
    .device_id = THIS_DEVICE_ID,
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

static cipher_daemon_t daemon = {0};

/*-----------------------------------------------------------------------------------------------------
 *                                                                                       Auto Gen Stuff
 *---------------------------------------------------------------------------------------------------*/

// Generated RPC prototypes
MotionResponse_t accel_command_motion_handler(MotionRequest_t request) {
    // ... user's implementation ...
    MotionResponse_t resp = {
        .success = true,
    };
    static int count = 0;
    count++;

    LOG("Calling me %d", count);
    return resp;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  App
 *---------------------------------------------------------------------------------------------------*/
void test_raw_rpc(void);
void test_api_rpc(void);

int main(void) {

    LOG_RAW("\n\n%s\n", "********** Cipher Protocol App **********");
    cipher_test_rpc();
    // cipher_init_daemon(&config, &daemon);

    // size_t num_services = 0;
    // cipher_service_entry_t* services = cipher_get_local_services(&num_services);
    // cipher_register_local_services(&daemon, services, num_services);

    // LOG("App Initialized OK");
    // while (true) {
    //     cipher_test_rpc();
    //     test_raw_rpc();
    //     test_api_rpc();
    //     k_msleep(1000);
    // }
}

void test_raw_rpc(void) {
    // Allocate packet memory
    cipher_packet_fifo_item_t* fifo_item = alloc_packet_fifo_item(&daemon, sizeof(MotionRequest_t));
    CHECK_MALLOC(fifo_item);

    // Populate the right header
    fifo_item->packet.header.type = CIPHER_PACKET_TYPE_RPC;
    fifo_item->packet.header.destination_id = THIS_DEVICE_ID;
    fifo_item->packet.header.service_id = 6969;
    fifo_item->packet.header.operation_id = OP_ID_RPC_MOTION_COMMAND;

    MotionRequest_t* request_payload = (MotionRequest_t*)fifo_item->packet.payload;

    request_payload->Direction = DIRECTION_X;
    request_payload->force = 2.54;
    request_payload->interval = 2.3;

    // Send packet to queue
    k_fifo_put(&daemon.rpc_packet_queue, fifo_item);
}

void test_api_rpc(void) {

    MotionRequest_t request = {

    };

    int err = 0;
    cipher_rpc_user_info_t data = {
        .device_id = THIS_DEVICE_ID,
        .error = &err,
        .timeout_ms = 500,
    };

    MotionResponse_t response = accel_command_motion_rpc(&daemon, &data, request);

    if (err != 0) {
        ERROR("error calling rpc %d", err);
    }
}