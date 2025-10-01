// Standard includes
#include <stdbool.h>
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(alpha, 4);

int main(void) {
    // Main application loop
    while (1) {
        LOG_INF("Hello, World!");

        k_msleep(1000);
    }

    return 0;
}