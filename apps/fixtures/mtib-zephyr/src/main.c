// Standard includes
#include <errno.h>
#include <stdio.h>
#include <string.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Cipher includes
#include "daemon/api.h"
#include "app/app.h"

LOG_MODULE_REGISTER(app);

int main(void) {
    // Create a new daemon instance
    cipher_daemon_config_t cfg = {};
    cipher_daemon_t d = {};
    cipher_daemon_init(&cfg, &d);

    while (1) {
        LOG_INF("Running");
        k_msleep(1000);
    }
}
