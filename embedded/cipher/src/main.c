#include <stdio.h>
#include <stdlib.h>
#include <errno.h>

#ifndef __ZEPHYR__

#include <netinet/in.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>

#else

#include <zephyr/net/socket.h>
#include <zephyr/kernel.h>

#endif

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/__assert.h>
#include <string.h>

// Mateo
#include "zephyr/logging/log.h"
#include "cipher.h"

#define LED0_NODE DT_ALIAS(led0)

#if !DT_NODE_HAS_STATUS(LED0_NODE, okay)
#error "Unsupported board: led0 devicetree alias is not defined"
#endif

#define BIND_PORT 4242

LOG_MODULE_REGISTER(cipher, LOG_LEVEL_DBG);

void cipher_daemon(void *arg0, void *arg1, void *arg2)
{
	cipher_daemon_t daemon = {0};
	init_cipher(&daemon);
}

K_THREAD_DEFINE(cipher_id,
				2048,
				cipher_daemon,
				NULL, NULL, NULL,
				10,
				0,
				0);

struct led
{
	struct gpio_dt_spec spec;
	uint8_t num;
};

void blink(const struct led *led, uint32_t sleep_ms, uint32_t id)
{
	const struct gpio_dt_spec *spec = &led->spec;
	int cnt = 0;
	int ret;

	if (!device_is_ready(spec->port))
	{
		printk("Error: %s device is not ready\n", spec->port->name);
		return;
	}

	ret = gpio_pin_configure_dt(spec, GPIO_OUTPUT);
	if (ret != 0)
	{
		printk("Error %d: failed to configure pin %d (LED '%d')\n",
			   ret, spec->pin, led->num);
		return;
	}

	while (1)
	{
		gpio_pin_set(spec->port, spec->pin, cnt % 2);

		k_msleep(sleep_ms);
		cnt++;
	}
}

int main(void)
{
	static const struct led led0 = {
		.spec = GPIO_DT_SPEC_GET_OR(LED0_NODE, gpios, {0}),
		.num = 0,
	};

	while (1)
	{
		blink(&led0, 500, 0);
	}
}