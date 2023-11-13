#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(app);

int main(void) {
    while (1) {
        LOG_INF("Running");
        k_msleep(1000);
    }
}
