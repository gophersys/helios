/* Low-power mode shell command — demonstrates nRF54L15 sleep current */

#include <zephyr/kernel.h>
#include <zephyr/shell/shell.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/pm/pm.h>
#include <zephyr/pm/policy.h>
#include <zephyr/pm/device.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/shell/shell_uart.h>

/* BLE advertising data — minimal for ultra-low-power mode */
static const struct bt_data ulp_ad[] = {
	BT_DATA_BYTES(BT_DATA_FLAGS, BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR),
};
static const struct bt_data ulp_sd[] = {
	BT_DATA(BT_DATA_NAME_COMPLETE, CONFIG_BT_DEVICE_NAME,
		sizeof(CONFIG_BT_DEVICE_NAME) - 1),
};

static int cmd_sleep(const struct shell *sh, size_t argc, char **argv)
{
	int seconds = 5;
	if (argc >= 2) {
		seconds = atoi(argv[1]);
		if (seconds < 1 || seconds > 60) {
			shell_error(sh, "Duration must be 1-60 seconds");
			return -EINVAL;
		}
	}

	shell_print(sh, "Sleeping for %d seconds (shell inactive)...", seconds);
	/* Flush shell output */
	k_msleep(100);

	/* Sleep — the kernel idle thread will invoke PM and enter low-power */
	k_sleep(K_SECONDS(seconds));

	shell_print(sh, "Woke up! Uptime: %lld ms", k_uptime_get());
	return 0;
}

static int cmd_idle(const struct shell *sh, size_t argc, char **argv)
{
	shell_print(sh, "Current idle stats:");
	shell_print(sh, "  Uptime: %lld ms", k_uptime_get());
#ifdef CONFIG_PM_DEVICE
	shell_print(sh, "  PM Device: enabled");
#else
	shell_print(sh, "  PM Device: disabled");
#endif
#ifdef CONFIG_PM_DEVICE_RUNTIME
	shell_print(sh, "  PM Device Runtime: enabled");
#else
	shell_print(sh, "  PM Device Runtime: disabled");
#endif
	return 0;
}

/* Deferred low-power entry — runs from system workqueue after shell has
 * fully processed the uninit and aborted its thread. */
static void enter_lowpower_work_fn(struct k_work *w);
K_WORK_DELAYABLE_DEFINE(enter_lowpower_work, enter_lowpower_work_fn);

static void enter_lowpower_work_fn(struct k_work *w)
{
	ARG_UNUSED(w);

	/* Disable UART peripheral — don't sleep here, this is syswork context */
	const struct device *uart30 = DEVICE_DT_GET(DT_NODELABEL(uart30));
	if (device_is_ready(uart30)) {
		uart_irq_rx_disable(uart30);
		uart_irq_tx_disable(uart30);
#ifdef CONFIG_PM_DEVICE
		pm_device_action_run(uart30, PM_DEVICE_ACTION_SUSPEND);
#endif
	}
	/* After this returns, with shell thread aborted and UART off,
	 * only idle + BT threads remain. System enters low-power idle. */
}

static void shell_uninit_cb(const struct shell *sh, int res)
{
	ARG_UNUSED(sh); ARG_UNUSED(res);
	/* Shell thread is about to abort. Schedule UART disable on syswork. */
	k_work_schedule(&enter_lowpower_work, K_MSEC(100));
}

static int cmd_ultralow(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);

	/* Step 1: Start BLE advertising */
	shell_print(sh, "Initializing BLE...");
	int err = bt_enable(NULL);
	if (err && err != -EALREADY) {
		shell_error(sh, "bt_enable: %d", err);
		return err;
	}

	/* Slow advertising: 1000ms interval for minimum power. */
	static const struct bt_le_adv_param ulp_adv_param =
		BT_LE_ADV_PARAM_INIT(BT_LE_ADV_OPT_CONN,
				     BT_GAP_ADV_SLOW_INT_MIN,  /* 1000ms */
				     BT_GAP_ADV_SLOW_INT_MAX,  /* 1200ms */
				     NULL);
	err = bt_le_adv_start(&ulp_adv_param, ulp_ad, ARRAY_SIZE(ulp_ad),
			      ulp_sd, ARRAY_SIZE(ulp_sd));
	if (err && err != -EALREADY) {
		shell_error(sh, "Adv start: %d", err);
		return err;
	}
	shell_print(sh, "BLE advertising as '%s'", bt_get_name());

	/* Step 2: Announce UART shutdown */
	shell_print(sh, "Disabling UART console — board will be headless + BLE only");
	shell_print(sh, "Power cycle to restore shell.");

	/* Step 3: Uninit shell — callback fires after shell thread aborts,
	 * which then disables UART. With no runnable threads left,
	 * the kernel idle thread takes over and enters low-power state. */
	shell_uninit(sh, shell_uninit_cb);
	return 0;
}

static int cmd_deadlow(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);

	shell_print(sh, "UART off, NO BLE — absolute floor test");
	shell_print(sh, "Power cycle to restore shell.");

	shell_uninit(sh, shell_uninit_cb);
	return 0;
}

SHELL_STATIC_SUBCMD_SET_CREATE(sub_power,
	SHELL_CMD_ARG(sleep, NULL, "Sleep N seconds (default 5)", cmd_sleep, 1, 1),
	SHELL_CMD(idle, NULL, "Show idle/PM status", cmd_idle),
	SHELL_CMD(ultralow, NULL, "BLE adv only — kills UART, lowest power", cmd_ultralow),
	SHELL_CMD(deadlow, NULL, "No BLE, no UART — absolute floor", cmd_deadlow),
	SHELL_SUBCMD_SET_END
);
SHELL_CMD_REGISTER(power, &sub_power, "Power management", NULL);
