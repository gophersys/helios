/*
 * IWSCK A0 — Bring-up shell
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

static const struct device *const temp_dev =
	DEVICE_DT_GET(DT_NODELABEL(temp));

static int cmd_board_info(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);
	shell_print(sh, "IWSCK A0 — nRF54L15 Bring-Up Board");
	shell_print(sh, "");
	shell_print(sh, "Pinout:");
	shell_print(sh, "  Console:    uart30  P0.02/P0.03  115200");
	shell_print(sh, "  RS232/LEMO: uart20  P1.03/P1.02  115200");
	shell_print(sh, "  I2C (bb):   i2c_bb  P2.00/P2.01  100kHz");
	shell_print(sh, "  LEDs:       P2.08(R) P2.09(G) P2.10(B) active-low");
	shell_print(sh, "  Fuel EN:    P0.01 (hog, high)");
	shell_print(sh, "  Fuel INT:   P0.00 (active-low)");
	if (device_is_ready(temp_dev)) {
		struct sensor_value val;
		sensor_sample_fetch(temp_dev);
		sensor_channel_get(temp_dev, SENSOR_CHAN_DIE_TEMP, &val);
		shell_print(sh, "Die temp:     %d.%d C", val.val1, val.val2 / 100000);
	}
	shell_print(sh, "Uptime:       %lld ms", k_uptime_get());
	shell_print(sh, "LF clock:     RC32K (no LFXO)");
	return 0;
}
SHELL_CMD_REGISTER(board, NULL, "Board info, pinout, die temp", cmd_board_info);

int main(void)
{
	printk("\n========================================\n");
	printk("  IWSCK A0 — Bring-Up Shell\n");
	printk("  Type 'help' for commands\n");
	printk("========================================\n\n");
	return 0;
}
