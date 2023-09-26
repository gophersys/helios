// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(app);

// Cipher includes
#include "daemon/api.h"
#include "utils/err.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Daemon Config
 *---------------------------------------------------------------------------------------------------*/

#define POSIX_HOST_IP "192.168.0.11"
#define UPLINK_SOCKET 5000
#define DOWNLINK_SOCKET 5001

static cipher_daemon_config_t config = {
	.uplink_ifaces[0] = {
		.type = TAL_INTERFACE_TYPE_SOCKET,
		.link = TAL_LINK_TYPE_UPLINK,
		.host = POSIX_HOST_IP,
		.port = UPLINK_SOCKET,
	},
	.downlink_ifaces[0] = {
		.type = TAL_INTERFACE_TYPE_SOCKET,
		.link = TAL_LINK_TYPE_DOWNLINK,
		.host = POSIX_HOST_IP,
		.port = DOWNLINK_SOCKET,
	},
};

static cipher_daemon_t daemon = {0};

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  App
 *---------------------------------------------------------------------------------------------------*/

int main(void)
{
	LOG_RAW("\n\n%s\n", "********** Cipher Protocol App **********");

	cipher_init_daemon(&config, &daemon);

	LOG("App Initialized OK");

	while (true)
		k_msleep(1000);
}