// Zephyr includes
#include <zephyr/kernel.h>

// CoreKinect includes
#include "cipher.h"

int main(void)
{
	LOG_RAW("\n\n%s\n", "********** Cipher Protocol App **********");

	static cipher_daemon_t daemon = {
		.uplink_cfg = {
			.interface = TAL_INTERFACE_TYPE_SOCKET,
			.link = TAL_LINK_TYPE_UPLINK,
			.host = "192.168.0.11",
			.port = 5000,
		},
	};

	init_cipher(&daemon);
}