// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/logging/log_ctrl.h>
#include <zephyr/sys/reboot.h>

// Corekinect includes
#include <corekinect/cipher/cipher.h>

// App includes
#include "app/app.h"
#include "app/uart.h"
#include "config/config.h"

// Protocol includes
#include "protos/mtib_runner_zephyr/mtib_runner_zephyr.cipher.h"

LOG_MODULE_REGISTER(app, LOG_LEVEL_DBG);

void init_daemon()
{
    // Instantiate
    if (!cipher_daemon_init(get_daemon_config()))
    {
        LOG_ERR("Could not initialize cipher application daemon");
        k_fatal_halt(0);
    }

    // Register services
    if (!cipher_register_service(get_mtibrunnerzephyrservice_info(), true))
    {
        LOG_ERR("Could not register local services with daemon");
        k_fatal_halt(0);
    }
}

// Entry
int main(void)
{
    // Application
    static app_info_t app = {0};
    app_mtib_init(&app);

    init_daemon();

    // UART traffic forwarder
    if (!app_uart_forwarder_init())
    {
        LOG_ERR("%s", "Could not initialize UART port forwarder");
    }

    k_sleep(K_FOREVER);
}

void arch_system_halt(unsigned int reason)
{
    ARG_UNUSED(reason);

    LOG_ERR("A fatal error has occurred, resetting platform");

    LOG_PANIC();

    (void)arch_irq_lock();

    k_msleep(2000);
    sys_reboot(SYS_REBOOT_COLD);
}
