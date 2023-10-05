// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/net_ip.h>
#include <zephyr/net/socket.h>
#include <zephyr/posix/netinet/in.h>
#include <zephyr/posix/sys/socket.h>

LOG_MODULE_REGISTER(app);

// Cipher includes
#include "cipher_tests.h"
#include "daemon/api.h"
#include "daemon/fifo.h"
#include "daemon/registry.h"
#include "utils/err.h"

// App includes
#include "config.h"
#include "motion-bed.h"

int main(void) {
    LOG_RAW("\n\n%s\n", "********** Accel Drv App **********");

    cipher_daemon_init(&cfg, &d);
    cipher_daemon_start(&d);

    k_msleep(1000);

    while (true) {

        motion_request_t request = {
            .direction = DIRECTION_X,
            .force = 1,
            .interval = 100,
        };

        cipher_rpc_user_info_t info = {
            .device_id = 124,
            .timeout_ms = 100,
        };

        motion_response_t response = accel_bench_rpc_command_motion(&d, &info, request);
        if (info.error != CIPHER_RPC_ERR_OK) {
            ERROR("RPC error: %d", info.error);
        }

        LOG("Success: %d, ErrCode: %d", response.success, response.error_code);
    }
}