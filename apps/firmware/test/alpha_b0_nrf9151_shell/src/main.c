/*
 * Alpha B0 nRF9151 Shell Test Firmware
 *
 * Simple UART shell firmware for the nRF9151 communications processor
 * on the Alpha B0 host board (REV 1.2 UART pinout).
 *
 * Provides diagnostic shell commands for MTIB test bench validation:
 *   test ping    - UART connectivity check
 *   test info    - Board and build information
 *   test led     - LED control (red, green, blue)
 *   test modem   - Read modem IMEI/ICCID
 *
 * UART0 pins: TX=P0.21, RX=P0.22 (115200 baud)
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/shell/shell.h>
#include <zephyr/logging/log.h>

#include <nrf_modem.h>
#include <nrf_modem_at.h>
#include <modem/nrf_modem_lib.h>

LOG_MODULE_REGISTER(shell_test, LOG_LEVEL_INF);

/* LED definitions from the alpha_b0_nrf9151_common.dts devicetree */
#define RED_LED_NODE   DT_NODELABEL(red_led)
#define GREEN_LED_NODE DT_NODELABEL(green_led)
#define BLUE_LED_NODE  DT_NODELABEL(blue_led)

static const struct gpio_dt_spec led_red   = GPIO_DT_SPEC_GET(RED_LED_NODE, gpios);
static const struct gpio_dt_spec led_green = GPIO_DT_SPEC_GET(GREEN_LED_NODE, gpios);
static const struct gpio_dt_spec led_blue  = GPIO_DT_SPEC_GET(BLUE_LED_NODE, gpios);

/* Modem initialization state */
static bool modem_initialized;

/* AT command response buffer */
#define AT_RESPONSE_BUF_SIZE 256
static char at_response_buf[AT_RESPONSE_BUF_SIZE];

/*
 * Heartbeat thread - blinks blue LED every 2 seconds to indicate
 * that the firmware is running.
 */
#define HEARTBEAT_STACK_SIZE 512
#define HEARTBEAT_PRIORITY   7

static void heartbeat_entry(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	while (1) {
		gpio_pin_toggle_dt(&led_blue);
		k_msleep(2000);
	}
}

K_THREAD_DEFINE(heartbeat_tid, HEARTBEAT_STACK_SIZE,
		heartbeat_entry, NULL, NULL, NULL,
		HEARTBEAT_PRIORITY, 0, 0);

/*
 * Initialize all three LEDs as outputs.
 * Returns 0 on success, negative errno on failure.
 */
static int leds_init(void)
{
	int err;

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

	err = gpio_pin_configure_dt(&led_red, GPIO_OUTPUT_INACTIVE);
	if (err) {
		LOG_ERR("Failed to configure red LED: %d", err);
		return err;
	}

	err = gpio_pin_configure_dt(&led_green, GPIO_OUTPUT_INACTIVE);
	if (err) {
		LOG_ERR("Failed to configure green LED: %d", err);
		return err;
	}

	err = gpio_pin_configure_dt(&led_blue, GPIO_OUTPUT_INACTIVE);
	if (err) {
		LOG_ERR("Failed to configure blue LED: %d", err);
		return err;
	}

	return 0;
}

/*
 * Initialize the nRF modem library.
 * The modem may fail to initialize if no SIM is present or the modem
 * firmware is not loaded -- this is not a fatal error for the shell.
 */
static void modem_init(void)
{
	int err;

	LOG_INF("Initializing modem library...");

	err = nrf_modem_lib_init();
	if (err) {
		LOG_WRN("Modem library init failed: %d (SIM may not be present)", err);
		modem_initialized = false;
		return;
	}

	modem_initialized = true;
	LOG_INF("Modem library initialized successfully");
}

/*
 * nRF modem fault handler (required by CONFIG_NRF_MODEM_LIB_ON_FAULT_APPLICATION_SPECIFIC)
 */
void nrf_modem_fault_handler(struct nrf_modem_fault_info *fault_info)
{
	LOG_ERR("Modem fault! Reason: 0x%x, PC: 0x%x",
		fault_info->reason, fault_info->program_counter);
}

/* ----------------------------------------------------------------
 * Shell commands: test ping / test info / test led / test modem
 * ---------------------------------------------------------------- */

static int cmd_test_ping(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	shell_print(sh, "pong");
	return 0;
}

static int cmd_test_info(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	shell_print(sh, "Board:      Alpha B0 (REV 1.2)");
	shell_print(sh, "SoC:        nRF9151 (Non-Secure)");
	shell_print(sh, "UART0 TX:   P0.21");
	shell_print(sh, "UART0 RX:   P0.22");
	shell_print(sh, "Baud:       115200");
	shell_print(sh, "Build date: " __DATE__ " " __TIME__);
	shell_print(sh, "Modem:      %s", modem_initialized ? "initialized" : "not initialized");

	return 0;
}

static int cmd_test_led(const struct shell *sh, size_t argc, char **argv)
{
	const struct gpio_dt_spec *led;
	const char *color;
	bool on;
	int err;

	if (argc != 3) {
		shell_error(sh, "Usage: test led <red|green|blue> <on|off>");
		return -EINVAL;
	}

	color = argv[1];

	if (strcmp(color, "red") == 0) {
		led = &led_red;
	} else if (strcmp(color, "green") == 0) {
		led = &led_green;
	} else if (strcmp(color, "blue") == 0) {
		led = &led_blue;
	} else {
		shell_error(sh, "Unknown LED color '%s' (use red, green, or blue)", color);
		return -EINVAL;
	}

	if (strcmp(argv[2], "on") == 0) {
		on = true;
	} else if (strcmp(argv[2], "off") == 0) {
		on = false;
	} else {
		shell_error(sh, "Unknown state '%s' (use on or off)", argv[2]);
		return -EINVAL;
	}

	/* LEDs are active-low, so set=1 means active (on) via the dt spec */
	err = gpio_pin_set_dt(led, on ? 1 : 0);
	if (err) {
		shell_error(sh, "Failed to set LED: %d", err);
		return err;
	}

	shell_print(sh, "%s LED %s", color, on ? "on" : "off");
	return 0;
}

static int cmd_test_modem(const struct shell *sh, size_t argc, char **argv)
{
	int err;

	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	if (!modem_initialized) {
		shell_warn(sh, "Modem is not initialized (SIM may not be present)");
		shell_print(sh, "Attempting modem initialization...");
		modem_init();
		if (!modem_initialized) {
			shell_error(sh, "Modem initialization failed");
			return -EIO;
		}
	}

	/* Read IMEI with AT+CGSN */
	memset(at_response_buf, 0, sizeof(at_response_buf));
	err = nrf_modem_at_cmd(at_response_buf, sizeof(at_response_buf), "AT+CGSN");
	if (err) {
		shell_error(sh, "AT+CGSN failed: %d", err);
	} else {
		/* Trim trailing whitespace / OK */
		char *end = strstr(at_response_buf, "\r");
		if (end) {
			*end = '\0';
		}
		shell_print(sh, "IMEI: %s", at_response_buf);
	}

	/* Read ICCID with AT%XICCID */
	memset(at_response_buf, 0, sizeof(at_response_buf));
	err = nrf_modem_at_cmd(at_response_buf, sizeof(at_response_buf), "AT%%XICCID");
	if (err) {
		shell_warn(sh, "AT%%XICCID failed: %d (SIM may not be inserted)", err);
	} else {
		/* Response format: %XICCID: <iccid> */
		char *iccid = strstr(at_response_buf, ": ");
		if (iccid) {
			iccid += 2;
			char *end = strstr(iccid, "\r");
			if (end) {
				*end = '\0';
			}
			shell_print(sh, "ICCID: %s", iccid);
		} else {
			shell_print(sh, "ICCID response: %s", at_response_buf);
		}
	}

	return 0;
}

/* Register shell commands under the "test" parent command */
SHELL_STATIC_SUBCMD_SET_CREATE(sub_test,
	SHELL_CMD(ping, NULL, "Respond with pong (UART connectivity check)", cmd_test_ping),
	SHELL_CMD(info, NULL, "Print board revision, UART pins, build date", cmd_test_info),
	SHELL_CMD_ARG(led, NULL, "Control LEDs: test led <red|green|blue> <on|off>",
		      cmd_test_led, 3, 0),
	SHELL_CMD(modem, NULL, "Read modem IMEI and ICCID", cmd_test_modem),
	SHELL_SUBCMD_SET_END
);

SHELL_CMD_REGISTER(test, &sub_test, "Alpha B0 nRF9151 test commands", NULL);

/* ----------------------------------------------------------------
 * Main entry point
 * ---------------------------------------------------------------- */

int main(void)
{
	int err;

	printk("\n");
	printk("===========================================\n");
	printk("  Alpha B0 nRF9151 Shell Test Firmware\n");
	printk("  Board:    Alpha B0 (REV 1.2)\n");
	printk("  UART0:    TX=P0.21  RX=P0.22\n");
	printk("  Baud:     115200\n");
	printk("  Build:    " __DATE__ " " __TIME__ "\n");
	printk("===========================================\n");
	printk("\n");

	/* Initialize LEDs */
	err = leds_init();
	if (err) {
		LOG_ERR("LED initialization failed: %d", err);
	} else {
		LOG_INF("LEDs initialized (red=P0.5, green=P0.4, blue=P0.6)");
		/* Flash green briefly to indicate successful boot */
		gpio_pin_set_dt(&led_green, 1);
		k_msleep(500);
		gpio_pin_set_dt(&led_green, 0);
	}

	/* Initialize modem (non-fatal if it fails) */
	modem_init();

	LOG_INF("Shell is ready. Type 'test ping' to verify UART.");

	return 0;
}
