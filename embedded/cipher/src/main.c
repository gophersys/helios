// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(app);

// CoreKinect includes
#include "cipher.h"
#include "utils.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Daemon Config
 *---------------------------------------------------------------------------------------------------*/

#define POSIX_HOST_IP "192.168.0.11"
#define UPLINK_SOCKET 5000
#define DOWNLINK_SOCKET 5001

static cipher_daemon_t daemon = {
	.uplink_interface_cfg[0] = {
		.type = TAL_INTERFACE_TYPE_SOCKET,
		.link = TAL_LINK_TYPE_UPLINK,
		.host = POSIX_HOST_IP,
		.port = UPLINK_SOCKET,
	},
	.downlink_interface_cfg[0] = {
		.type = TAL_INTERFACE_TYPE_SOCKET,
		.link = TAL_LINK_TYPE_DOWNLINK,
		.host = POSIX_HOST_IP,
		.port = DOWNLINK_SOCKET,
	},
};

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  App
 *---------------------------------------------------------------------------------------------------*/

int main(void)
{
	LOG_RAW("\n\n%s\n", "********** Cipher Protocol App **********");

	if (!cipher_init_daemon(&daemon))
		ERROR("Unable to initialize cipher daemon");

	LOG("App Initialized OK");

	while (true)
		k_msleep(1000);
}

// (1 Uplink + 1 Downlink only)
// 162488 [1]
// 186152 [2] +23664
// 209816 [3] +23664