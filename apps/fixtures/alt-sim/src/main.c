// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Cipher includes
#include "daemon/api.h"

// App includes
#include "alt-sim-srvc.h"   // We offer this service to the test-fw
#include "app/app.h"        // The simulator app
#include "config/config.h"  // Network configuration of cluster

LOG_MODULE_REGISTER(app);

int main(void) {
    LOG_RAW("\n\n%s\n", "********** Altimeter Sim App **********");

    // Create a new daemon instance
    cipher_daemon_config_t* cfg = get_app_config();
    cipher_daemon_t* d = get_app_daemon();
    cipher_daemon_init(cfg, d);

    size_t num_local_services = 0;
    cipher_service_entry_t* local_services = alt_sim_fixture_get_services(&num_local_services);
    cipher_register_local_services(d, local_services, num_local_services);  // Register services we offer

    // Start
    cipher_daemon_start(d);
    alt_sim_app_start();
}