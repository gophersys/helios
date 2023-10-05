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
}
