#include "cipher.h"

void cipher_daemon(void *arg0, void *arg1, void *arg2)
{
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

K_THREAD_DEFINE(cipher_id, 10000, cipher_daemon, NULL, NULL, NULL, 10, 0, 0);

int main(void)
{
	while (1)
	{
		k_msleep(1000);
	}
}