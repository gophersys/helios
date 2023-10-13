// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Cipher includes
#include "daemon/api.h"

// App includes
#include "alt-drv-test-srvc.h"  // We offer this service to the runner
#include "alt-sim-srvc.h"       // We consume this service from the icle
#include "config/config.h"      // Network configuration of cluster
#include "test/test.h"          // Test App

LOG_MODULE_REGISTER(app);

int main(void) {
    LOG_RAW("%s", "********** Accel Drv Test App **********");

    // Create a new daemon instance
    cipher_daemon_config_t* cfg = get_app_config();
    cipher_daemon_t* d = get_app_daemon();
    cipher_daemon_init(cfg, d);

    size_t num_local_services = 0;
    cipher_service_entry_t* local_services = alt_drv_test_get_services(&num_local_services);
    cipher_register_local_services(d, local_services, num_local_services);  // Services we offer

    size_t num_remote_services = 0;
    cipher_service_entry_t* remote_services = alt_sim_fixture_get_services(&num_remote_services);
    cipher_register_remote_services(d, remote_services, num_remote_services);  // Services we consume

    // Start
    cipher_daemon_start(d);
    test_app_start();

    // run_manual_test();
}