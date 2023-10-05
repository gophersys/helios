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
    LOG_RAW("\n\n%s\n", "********** Motion Bed App **********");

    // Create protocol daemon
    cipher_daemon_init(&cfg, &d);

    // Register services
    size_t num_services = 0;
    cipher_service_entry_t* services = accel_fixture_get_services(&num_services);
    cipher_register_local_services(&d, services, num_services);

    // Start application daemon
    cipher_daemon_start(&d);
}

motion_response_t accel_bench_rpc_command_motion_handler(motion_request_t request) {

    motion_response_t response = {0};
    return response;
}