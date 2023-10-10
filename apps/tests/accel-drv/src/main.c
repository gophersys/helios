// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/net_ip.h>
#include <zephyr/net/socket.h>
#include <zephyr/posix/netinet/in.h>
#include <zephyr/posix/sys/socket.h>

LOG_MODULE_REGISTER(app);

// Cipher includes
#include "daemon/api.h"
#include "daemon/fifo.h"
#include "daemon/registry.h"
#include "utils/err.h"

// App includes
#include "config.h"
#include "motion-bed.h"

int main(void) {
    LOG_RAW("\n\n%s\n", "********** Accel Drv App **********");

    // Create a new daemon instance
    cipher_daemon_init(&cfg, &d);

    // Register all services for this device
    size_t num_services = 0;
    cipher_service_entry_t* services = accel_fixture_get_services(&num_services);
    cipher_register_remote_services(&d, services, num_services);

    // Let it rip
    cipher_daemon_start(&d);

    while (true) {
        k_msleep(500);

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

        LOG("Success: %s, ErrCode: %d", response.success ? "true" : "false", response.error_code);
    }
}