/*
 * IWSCK — Bring-up shell (A0 + A1)
 *
 * All peripherals self-init via SYS_INIT:
 *   led.c    — RGB LED control          (pri 90)
 *   rs232.c  — RS232/LEMO uart20        (pri 91)
 *   fuel.c   — BQ35100 fuel gauge + INT (pri 92)
 *   ble.c    — BLE GATT server          (lazy, on first `ble start`)
 *
 * Built-in shells (gpio, i2c, sensor, kernel) via Kconfig.
 */

#include <zephyr/kernel.h>
#include <zephyr/shell/shell.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/drivers/clock_control.h>

#ifdef CONFIG_BOARD_IWSCK_A0
#define BOARD_NAME    "IWSCK A0"
#define CONSOLE_PINS  "P0.02/P0.03"
#define RS232_PINS    "P1.03/P1.02"
#define I2C_TYPE      "i2c_bb  P2.00/P2.01  100kHz"
#define LED_PINS      "P2.08(G) P2.09(B) P2.10(R) active-low"
#define FUEL_EN_PIN   "P0.01 (output, high)"
#define FUEL_INT_PIN  "P0.00 (active-low)"
#define NFC_STATUS    "disabled (reworked to RS232)"
#else
#define BOARD_NAME    "IWSCK A1"
#define CONSOLE_PINS  "P0.00/P0.01"
#define RS232_PINS    "P1.08/P1.09"
#define I2C_TYPE      "twim21  P1.04/P1.05  100kHz"
#define LED_PINS      "P2.07(R) P2.08(G) P2.09(B) active-low"
#define FUEL_EN_PIN   "P0.03 (output, high)"
#define FUEL_INT_PIN  "P0.02 (active-low)"
#define NFC_STATUS    "nfct    P1.02/P1.03"
#endif

static const struct device *const temp_dev =
	DEVICE_DT_GET(DT_NODELABEL(temp));
static const struct device *const clk_dev =
	DEVICE_DT_GET(DT_NODELABEL(clock));

static int cmd_board_info(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);
	shell_print(sh, BOARD_NAME " — nRF54L15 Bring-Up Board");
	shell_print(sh, "");
	shell_print(sh, "Pinout:");
	shell_print(sh, "  Console:    uart30  %s  115200", CONSOLE_PINS);
	shell_print(sh, "  RS232/LEMO: uart20  %s  115200", RS232_PINS);
	shell_print(sh, "  I2C:        %s", I2C_TYPE);
	shell_print(sh, "  NFC:        %s", NFC_STATUS);
	shell_print(sh, "  LEDs:       %s", LED_PINS);
	shell_print(sh, "  Fuel EN:    %s", FUEL_EN_PIN);
	shell_print(sh, "  Fuel INT:   %s", FUEL_INT_PIN);
	if (device_is_ready(temp_dev)) {
		struct sensor_value val;
		sensor_sample_fetch(temp_dev);
		sensor_channel_get(temp_dev, SENSOR_CHAN_DIE_TEMP, &val);
		shell_print(sh, "Die temp:     %d.%d C", val.val1, val.val2 / 100000);
	}
	shell_print(sh, "Uptime:       %lld ms", k_uptime_get());
	shell_print(sh, "HF clock:     HFXO 32MHz %s",
		    device_is_ready(clk_dev) ? "OK" : "FAIL");
	shell_print(sh, "LF clock:     RC32K (no LFXO)");
	return 0;
}
SHELL_CMD_REGISTER(board, NULL, "Board info, pinout, die temp", cmd_board_info);

int main(void)
{
	printk("\n========================================\n");
	printk("  " BOARD_NAME " — Bring-Up Shell\n");
	printk("  Type 'help' for commands\n");
	printk("========================================\n\n");
	return 0;
}
