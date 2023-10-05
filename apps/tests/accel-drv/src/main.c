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
    LOG_RAW("\n\n%s\n", "********** Accel Drv App **********");

    cipher_daemon_init(&cfg, &d);
    cipher_daemon_start(&d);
}