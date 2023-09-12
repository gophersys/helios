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

/* size of stack area used by each thread */
#define STACKSIZE 1024

/* scheduling priority used by each thread */
#define PRIORITY 7

#define LED0_NODE DT_ALIAS(led0)
#define LED1_NODE DT_ALIAS(led1)

#if !DT_NODE_HAS_STATUS(LED0_NODE, okay)
#error "Unsupported board: led0 devicetree alias is not defined"
#endif

// #if !DT_NODE_HAS_STATUS(LED1_NODE, okay)
// #error "Unsupported board: led1 devicetree alias is not defined"
// #endif

struct printk_data_t
{
	void *fifo_reserved; /* 1st word reserved for use by fifo */
	uint32_t led;
	uint32_t cnt;
};

K_FIFO_DEFINE(printk_fifo);

struct led
{
	struct gpio_dt_spec spec;
	uint8_t num;
};

static const struct led led0 = {
	.spec = GPIO_DT_SPEC_GET_OR(LED0_NODE, gpios, {0}),
	.num = 0,
};

static const struct led led1 = {
	.spec = GPIO_DT_SPEC_GET_OR(LED0_NODE, gpios, {0}),
	.num = 1,
};

#define BIND_PORT 4242

int main(void)
{
	printf("Starting Echo Server...\n");

	int serv;
	struct sockaddr_in bind_addr;
	static int counter;

	serv = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);

	if (serv < 0)
	{
		printf("error: socket: %d\n", errno);
		exit(1);
	}

	bind_addr.sin_family = AF_INET;
	bind_addr.sin_addr.s_addr = htonl(INADDR_ANY);
	bind_addr.sin_port = htons(BIND_PORT);

	if (bind(serv, (struct sockaddr *)&bind_addr, sizeof(bind_addr)) < 0)
	{
		printf("error: bind: %d\n", errno);
		exit(1);
	}

	if (listen(serv, 5) < 0)
	{
		printf("error: listen: %d\n", errno);
		exit(1);
	}

	printf("Single-threaded TCP echo server waits for a connection on "
		   "port %d...\n",
		   BIND_PORT);

	while (1)
	{
		struct sockaddr_in client_addr;
		socklen_t client_addr_len = sizeof(client_addr);
		char addr_str[32];
		int client = accept(serv, (struct sockaddr *)&client_addr,
							&client_addr_len);

		if (client < 0)
		{
			printf("error: accept: %d\n", errno);
			continue;
		}

		inet_ntop(client_addr.sin_family, &client_addr.sin_addr,
				  addr_str, sizeof(addr_str));
		printf("Connection #%d from %s\n", counter++, addr_str);

		while (1)
		{
			char buf[128], *p;
			int len = recv(client, buf, sizeof(buf), 0);
			int out_len;

			if (len <= 0)
			{
				if (len < 0)
				{
					printf("error: recv: %d\n", errno);
				}
				break;
			}

			p = buf;
			do
			{
				out_len = send(client, p, len, 0);
				if (out_len < 0)
				{
					printf("error: send: %d\n", errno);
					goto error;
				}
				p += out_len;
				len -= out_len;
			} while (len);
		}

	error:
		close(client);
		printf("Connection from %s closed\n", addr_str);
	}
	return 0;
}

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

		struct printk_data_t tx_data = {.led = id, .cnt = cnt};

		size_t size = sizeof(struct printk_data_t);
		char *mem_ptr = k_malloc(size);
		__ASSERT_NO_MSG(mem_ptr != 0);

		memcpy(mem_ptr, &tx_data, size);

		k_fifo_put(&printk_fifo, mem_ptr);

		k_msleep(sleep_ms);
		cnt++;
	}
}

void blink0(void)
{
	blink(&led0, 100, 0);
}

void blink1(void)
{
	blink(&led1, 1000, 1);
}

void uart_out(void)
{
	while (1)
	{
		struct printk_data_t *rx_data = k_fifo_get(&printk_fifo,
												   K_FOREVER);
		printk("Toggled led%d; counter=%d\n",
			   rx_data->led, rx_data->cnt);
		k_free(rx_data);
	}
}

K_THREAD_DEFINE(blink0_id, STACKSIZE, blink0, NULL, NULL, NULL,
				PRIORITY, 0, 0);
K_THREAD_DEFINE(blink1_id, STACKSIZE, blink1, NULL, NULL, NULL,
				PRIORITY, 0, 0);
K_THREAD_DEFINE(uart_out_id, STACKSIZE, uart_out, NULL, NULL, NULL,
				PRIORITY, 0, 0);
