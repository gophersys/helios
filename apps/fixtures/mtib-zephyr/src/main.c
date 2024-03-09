// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/logging/log_ctrl.h>
#include <zephyr/sys/reboot.h>

// Corekinect includes
#include <corekinect/cipher/cipher.h>

// App includes
#include "config/config.h"
#include "app/app.h"
#include "app/uart.h"

// Protocol includes
#include "protos/mtib_pi_stm/mtib-pi-stm.cipher.h"

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
    if (!cipher_register_service(get_mtibpistmservice_info(), true))
    {
        LOG_ERR("Could not register local services with daemon");
        k_fatal_halt(0);
    }
}

// Entry
int main(void)
{
    static app_info_t app = {0};
    app_mtib_init(&app);
    if (!app_uart_forwarder_init())
    {
        LOG_ERR("%s", "Could not initialize UART port forwarder");
    }

    init_daemon();

    k_sleep(K_FOREVER);
}

void arch_system_halt(unsigned int reason)
{
    ARG_UNUSED(reason);

    LOG_ERR("A fatal error has occurred, resetting platform");

    LOG_PANIC();

    k_msleep(1000);

    sys_reboot(SYS_REBOOT_COLD);
}
