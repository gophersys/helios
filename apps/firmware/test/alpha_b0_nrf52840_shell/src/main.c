/*
 * Alpha B0 nRF52840 Shell Test Firmware
 *
 * Simple Zephyr shell application for MTIB UART testing on the
 * Alpha B0 host board (REV 1.2 pinout).
 *
 * UART0 pins: TX=P0.23, RX=P0.25 (from alpha_b0_nrf52840-pinctrl.dtsi)
 * LEDs: Red=P0.17, Green=P0.13, Blue=P0.15 (active-low)
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/shell/shell.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/logging/log.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>

LOG_MODULE_REGISTER(shell_test, LOG_LEVEL_INF);

/* --------------------------------------------------------------------------
 * LED definitions from board DTS
 * -------------------------------------------------------------------------- */

#define LED_RED_NODE   DT_NODELABEL(red_led)
#define LED_GREEN_NODE DT_NODELABEL(green_led)
#define LED_BLUE_NODE  DT_NODELABEL(blue_led)

static const struct gpio_dt_spec led_red   = GPIO_DT_SPEC_GET(LED_RED_NODE, gpios);
static const struct gpio_dt_spec led_green = GPIO_DT_SPEC_GET(LED_GREEN_NODE, gpios);
static const struct gpio_dt_spec led_blue  = GPIO_DT_SPEC_GET(LED_BLUE_NODE, gpios);

/* --------------------------------------------------------------------------
 * GPIO port references for raw GPIO commands
 * -------------------------------------------------------------------------- */

static const struct device *gpio0_dev = DEVICE_DT_GET(DT_NODELABEL(gpio0));
static const struct device *gpio1_dev = DEVICE_DT_GET(DT_NODELABEL(gpio1));

/* --------------------------------------------------------------------------
 * Heartbeat thread - blinks green LED every 2 seconds
 * -------------------------------------------------------------------------- */

#define HEARTBEAT_STACK_SIZE 512
#define HEARTBEAT_PRIORITY   7

static void heartbeat_entry(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	while (1) {
		gpio_pin_toggle_dt(&led_green);
		k_sleep(K_SECONDS(2));
	}
}

K_THREAD_DEFINE(heartbeat_tid, HEARTBEAT_STACK_SIZE,
		heartbeat_entry, NULL, NULL, NULL,
		HEARTBEAT_PRIORITY, 0, 0);

/* --------------------------------------------------------------------------
 * Shell command: test ping
 * -------------------------------------------------------------------------- */

static int cmd_ping(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	shell_print(sh, "pong");
	return 0;
}

/* --------------------------------------------------------------------------
 * Shell command: test info
 * -------------------------------------------------------------------------- */

static int cmd_info(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	shell_print(sh, "Board:      Alpha B0 nRF52840");
	shell_print(sh, "Revision:   REV 1.2");
	shell_print(sh, "UART0 TX:   P0.23");
	shell_print(sh, "UART0 RX:   P0.25");
	shell_print(sh, "Baud:       115200");
	shell_print(sh, "LED Red:    P0.17 (active-low)");
	shell_print(sh, "LED Green:  P0.13 (active-low)");
	shell_print(sh, "LED Blue:   P0.15 (active-low)");
	shell_print(sh, "Build date: " __DATE__ " " __TIME__);
	return 0;
}

/* --------------------------------------------------------------------------
 * Shell command: test led <red|green|blue> <on|off>
 * -------------------------------------------------------------------------- */

static int cmd_led(const struct shell *sh, size_t argc, char **argv)
{
	if (argc != 3) {
		shell_error(sh, "Usage: test led <red|green|blue> <on|off>");
		return -EINVAL;
	}

	const struct gpio_dt_spec *led = NULL;
	const char *color = argv[1];
	const char *state = argv[2];

	if (strcmp(color, "red") == 0) {
		led = &led_red;
	} else if (strcmp(color, "green") == 0) {
		led = &led_green;
	} else if (strcmp(color, "blue") == 0) {
		led = &led_blue;
	} else {
		shell_error(sh, "Unknown LED color: %s (use red, green, blue)", color);
		return -EINVAL;
	}

	int on;

	if (strcmp(state, "on") == 0) {
		on = 1;
	} else if (strcmp(state, "off") == 0) {
		on = 0;
	} else {
		shell_error(sh, "Unknown state: %s (use on, off)", state);
		return -EINVAL;
	}

	int ret = gpio_pin_set_dt(led, on);

	if (ret < 0) {
		shell_error(sh, "Failed to set LED: %d", ret);
		return ret;
	}

	shell_print(sh, "LED %s %s", color, state);
	return 0;
}

/* --------------------------------------------------------------------------
 * Shell command: test gpio <pin> <in|out> [high|low]
 *
 * Pin format: "0.17" for P0.17 or "1.11" for P1.11
 * -------------------------------------------------------------------------- */

static int cmd_gpio(const struct shell *sh, size_t argc, char **argv)
{
	if (argc < 3 || argc > 4) {
		shell_error(sh, "Usage: test gpio <port.pin> <in|out> [high|low]");
		shell_error(sh, "  Example: test gpio 0.17 out high");
		shell_error(sh, "  Example: test gpio 0.25 in");
		return -EINVAL;
	}

	/* Parse port.pin */
	unsigned int port = 0;
	unsigned int pin = 0;

	if (sscanf(argv[1], "%u.%u", &port, &pin) != 2) {
		shell_error(sh, "Invalid pin format: %s (use port.pin, e.g. 0.17)", argv[1]);
		return -EINVAL;
	}

	if (port > 1) {
		shell_error(sh, "Invalid port: %u (use 0 or 1)", port);
		return -EINVAL;
	}

	if (pin > 31) {
		shell_error(sh, "Invalid pin: %u (use 0-31)", pin);
		return -EINVAL;
	}

	const struct device *gpio_dev = (port == 0) ? gpio0_dev : gpio1_dev;

	if (!device_is_ready(gpio_dev)) {
		shell_error(sh, "GPIO port %u device not ready", port);
		return -ENODEV;
	}

	const char *dir = argv[2];

	if (strcmp(dir, "in") == 0) {
		int ret = gpio_pin_configure(gpio_dev, pin, GPIO_INPUT);

		if (ret < 0) {
			shell_error(sh, "Failed to configure P%u.%02u as input: %d",
				    port, pin, ret);
			return ret;
		}

		int val = gpio_pin_get(gpio_dev, pin);

		if (val < 0) {
			shell_error(sh, "Failed to read P%u.%02u: %d", port, pin, val);
			return val;
		}

		shell_print(sh, "P%u.%02u = %d", port, pin, val);
	} else if (strcmp(dir, "out") == 0) {
		int level = 0;

		if (argc == 4) {
			if (strcmp(argv[3], "high") == 0) {
				level = 1;
			} else if (strcmp(argv[3], "low") == 0) {
				level = 0;
			} else {
				shell_error(sh, "Unknown level: %s (use high, low)",
					    argv[3]);
				return -EINVAL;
			}
		}

		int ret = gpio_pin_configure(gpio_dev, pin,
					     GPIO_OUTPUT_INIT_LOW | GPIO_ACTIVE_HIGH);

		if (ret < 0) {
			shell_error(sh, "Failed to configure P%u.%02u as output: %d",
				    port, pin, ret);
			return ret;
		}

		ret = gpio_pin_set(gpio_dev, pin, level);
		if (ret < 0) {
			shell_error(sh, "Failed to set P%u.%02u: %d", port, pin, ret);
			return ret;
		}

		shell_print(sh, "P%u.%02u -> %s", port, pin, level ? "HIGH" : "LOW");
	} else {
		shell_error(sh, "Unknown direction: %s (use in, out)", dir);
		return -EINVAL;
	}

	return 0;
}

/* --------------------------------------------------------------------------
 * Register shell commands under "test" parent
 * -------------------------------------------------------------------------- */

SHELL_STATIC_SUBCMD_SET_CREATE(sub_test,
	SHELL_CMD(ping, NULL, "Respond with pong (MTIB UART connectivity test)", cmd_ping),
	SHELL_CMD(info, NULL, "Print board info, UART pins, and build date", cmd_info),
	SHELL_CMD_ARG(led, NULL,
		      "Control LEDs: test led <red|green|blue> <on|off>",
		      cmd_led, 3, 0),
	SHELL_CMD_ARG(gpio, NULL,
		      "GPIO control: test gpio <port.pin> <in|out> [high|low]",
		      cmd_gpio, 3, 1),
	SHELL_SUBCMD_SET_END
);

SHELL_CMD_REGISTER(test, &sub_test, "Test commands for MTIB validation", NULL);

/* --------------------------------------------------------------------------
 * Main
 * -------------------------------------------------------------------------- */

int main(void)
{
	int ret;

	/* Initialize LEDs */
	if (!gpio_is_ready_dt(&led_red)) {
		LOG_ERR("Red LED GPIO device not ready");
		return -ENODEV;
	}
	if (!gpio_is_ready_dt(&led_green)) {
		LOG_ERR("Green LED GPIO device not ready");
		return -ENODEV;
	}
	if (!gpio_is_ready_dt(&led_blue)) {
		LOG_ERR("Blue LED GPIO device not ready");
		return -ENODEV;
	}

	ret = gpio_pin_configure_dt(&led_red, GPIO_OUTPUT_INACTIVE);
	if (ret < 0) {
		LOG_ERR("Failed to configure red LED: %d", ret);
		return ret;
	}

	ret = gpio_pin_configure_dt(&led_green, GPIO_OUTPUT_INACTIVE);
	if (ret < 0) {
		LOG_ERR("Failed to configure green LED: %d", ret);
		return ret;
	}

	ret = gpio_pin_configure_dt(&led_blue, GPIO_OUTPUT_INACTIVE);
	if (ret < 0) {
		LOG_ERR("Failed to configure blue LED: %d", ret);
		return ret;
	}

	LOG_INF("=== Alpha B0 nRF52840 Shell Test Firmware ===");
	LOG_INF("Board:    Alpha B0 (REV 1.2)");
	LOG_INF("UART0:    TX=P0.23  RX=P0.25  @ 115200 baud");
	LOG_INF("LEDs:     Red=P0.17  Green=P0.13  Blue=P0.15");
	LOG_INF("Build:    " __DATE__ " " __TIME__);
	LOG_INF("Shell ready. Type 'test ping' to verify UART.");

	/* Flash all three LEDs briefly to signal boot */
	gpio_pin_set_dt(&led_red, 1);
	gpio_pin_set_dt(&led_green, 1);
	gpio_pin_set_dt(&led_blue, 1);
	k_sleep(K_MSEC(500));
	gpio_pin_set_dt(&led_red, 0);
	gpio_pin_set_dt(&led_green, 0);
	gpio_pin_set_dt(&led_blue, 0);

	/* Heartbeat thread is already running (K_THREAD_DEFINE) */

	return 0;
}
