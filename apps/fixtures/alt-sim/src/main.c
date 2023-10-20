// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Cipher includes
#include "daemon/api.h"

// App includes
#include "alt-drv-test-srvc.h"  // We consume this service from the test app
#include "alt-sim-srvc.h"       // We offer this service to the test-fw
#include "app/app.h"            // The simulator app
#include "config/config.h"      // Network configuration of cluster

LOG_MODULE_REGISTER(app);

int main(void) {
    LOG_RAW("\n\n%s\n", "********** Alt Simulator App **********");

    // Create a new daemon instance
    cipher_daemon_config_t* cfg = get_app_config();
    cipher_daemon_t* d = get_app_daemon();
    cipher_daemon_init(cfg, d);

    size_t num_local_services = 0;
    cipher_service_entry_t* local_services = alt_sim_fixture_get_services(&num_local_services);
    cipher_register_local_services(d, local_services, num_local_services);  // Register services we offer

    // size_t num_remote_services = 0;
    // cipher_service_entry_t* remote_services = alt_drv_test_get_services(&num_remote_services);
    // cipher_register_remote_services(d, remote_services, num_remote_services);  // Services we consume

    // Start
    cipher_daemon_start(d);
    alt_sim_app_start();
}