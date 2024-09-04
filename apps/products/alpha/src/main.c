// Standard includes
#include <stdbool.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(app, 4);

int main(void)
{
    while (true)
    {
        LOG_INF("Hello world!");
        k_msleep(1000);
    }

    return 0;
}