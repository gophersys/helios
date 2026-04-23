// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Shell Commands
 *
 * Implements the "icle" top-level shell command with subcommand groups:
 *   icle config show / set <key> <value>
 *   icle wifi status / scan
 *   icle storage stats
 *   icle power read
 *   icle log start / stop / status
 *
 * Design notes:
 * - All handlers return 0 on success, negative errno on failure.
 * - shell_print() for normal output, shell_error() for errors.
 * - No dynamic allocation; all buffers are on the stack or static.
 * - SHELL_STATIC_SUBCMD_SET_CREATE for subcommand trees.
 * - SHELL_CMD_REGISTER for the top-level "icle" command.
 */

#include "services/shell_cmds.h"
#include "icle/app.h"
#include "icle/config.h"
#include "icle/types.h"
#include "hal/storage.h"
#include "hal/power_monitor.h"
#include "services/logger.h"
#include "net/wifi.h"

#include <zephyr/shell/shell.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/wifi_mgmt.h>

LOG_MODULE_REGISTER(icle_shell, CONFIG_LOG_DEFAULT_LEVEL);

#include <zephyr/kernel.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>

/*
 * config show
 */

/**
 * @brief Handler for: icle config show
 *
 * Reads the current ZMS-backed configuration and prints all fields.
 */
static int cmd_config_show(const struct shell *sh, size_t argc, char **argv)
{
	struct icle_config cfg;
	int ret;

	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	ret = icle_config_get(&cfg);

	if (ret < 0) {
		shell_error(sh, "Failed to read config: %d", ret);
		return ret;
	}

	shell_print(sh, "ICLE Configuration:");
	shell_print(sh, "  device_id:            %s", cfg.device_id);
	shell_print(sh, "  wifi_ssid:            %s", cfg.wifi_ssid);
	shell_print(sh, "  wifi_psk:             %s",
		    (cfg.wifi_psk[0] != '\0') ? "****" : "(not set)");
	shell_print(sh, "  backend_url:          %s", cfg.backend_url);
	shell_print(sh, "  sample_interval_ms:   %u", cfg.sample_interval_ms);
	shell_print(sh, "  heartbeat_interval_ms:%u", cfg.heartbeat_interval_ms);
	shell_print(sh, "  log_format:           %s",
		    (cfg.log_format == 0) ? "binary" : "csv");

	return 0;
}

/*
 * config set <key> <value>
 */

/**
 * @brief Handler for: icle config set <key> <value>
 *
 * Supported keys:
 *   device_id       — string (max 31 chars)
 *   wifi_ssid       — string (max 32 chars)
 *   wifi_psk        — string (max 64 chars)
 *   backend_url     — string (max 127 chars)
 *   sample_interval — unsigned integer (ms)
 *   heartbeat_interval — unsigned integer (ms)
 *   log_format      — 0 (binary) or 1 (csv)
 */
static int cmd_config_set(const struct shell *sh, size_t argc, char **argv)
{
	const char *key;
	const char *value;
	const char *psk;
	const char *ssid;
	unsigned long v;
	int ret = 0;

	if (argc != 3) {
		shell_error(sh, "Usage: icle config set <key> <value>");
		return -EINVAL;
	}

	key   = argv[1];
	value = argv[2];

	if (strcmp(key, "device_id") == 0) {
		ret = icle_config_set_device_id(value);
	} else if (strcmp(key, "wifi_ssid") == 0) {
		/* Preserve existing PSK while updating SSID */
		psk = icle_config_get_wifi_psk();

		ret = icle_config_set_wifi(value, psk);
	} else if (strcmp(key, "wifi_psk") == 0) {
		/* Preserve existing SSID while updating PSK */
		ssid = icle_config_get_wifi_ssid();

		ret = icle_config_set_wifi(ssid, value);
	} else if (strcmp(key, "backend_url") == 0) {
		ret = icle_config_set_backend_url(value);
	} else if (strcmp(key, "sample_interval") == 0) {
		v = strtoul(value, NULL, 10);

		if (v == 0 || v > UINT32_MAX) {
			shell_error(sh, "Invalid interval: %s", value);
			return -EINVAL;
		}
		ret = icle_config_set_sample_interval((uint32_t)v);
	} else if (strcmp(key, "heartbeat_interval") == 0) {
		v = strtoul(value, NULL, 10);

		if (v == 0 || v > UINT32_MAX) {
			shell_error(sh, "Invalid interval: %s", value);
			return -EINVAL;
		}
		ret = icle_config_set_heartbeat_interval((uint32_t)v);
	} else if (strcmp(key, "log_format") == 0) {
		v = strtoul(value, NULL, 10);

		if (v > 1) {
			shell_error(sh, "Invalid log_format (0=binary, 1=csv)");
			return -EINVAL;
		}
		ret = icle_config_set_log_format((uint8_t)v);
	} else {
		shell_error(sh, "Unknown key: %s", key);
		shell_print(sh, "Valid keys: device_id, wifi_ssid, wifi_psk,"
			    " backend_url, sample_interval,"
			    " heartbeat_interval, log_format");
		return -EINVAL;
	}

	if (ret < 0) {
		shell_error(sh, "Failed to set %s: %d", key, ret);
		return ret;
	}

	shell_print(sh, "OK: %s updated", key);
	return 0;
}

/*
 * wifi status
 */

/**
 * @brief Handler for: icle wifi status
 *
 * Queries the WiFi subsystem for its current connection state.
 */
static int cmd_wifi_status(const struct shell *sh, size_t argc, char **argv)
{
	struct icle_wifi_status status;
	int ret;

	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	ret = icle_wifi_get_status(&status);

	if (ret < 0) {
		shell_error(sh, "Failed to get WiFi status: %d", ret);
		return ret;
	}

	shell_print(sh, "WiFi Status:");
	shell_print(sh, "  state:          %s",
		    icle_wifi_state_name(status.state));

	if (status.state == ICLE_WIFI_STATE_CONNECTED) {
		shell_print(sh, "  ssid:           %s", status.ssid);
		shell_print(sh, "  rssi:           %d dBm", (int)status.rssi);
		shell_print(sh, "  channel:        %u", (unsigned)status.channel);
		shell_print(sh, "  ip_address:     %u.%u.%u.%u",
			    status.ip_addr[0], status.ip_addr[1],
			    status.ip_addr[2], status.ip_addr[3]);
		shell_print(sh, "  connected_ms:   %u", status.connected_time_ms);
		shell_print(sh, "  reconnects:     %u", status.reconnect_count);
	}

	return 0;
}

/*
 * wifi scan
 */

/**
 * @brief Handler for: icle wifi scan
 *
 * Posts a WiFi scan request via the app event bus. Scan results are
 * reported asynchronously through the Zephyr WiFi management layer and
 * logged by the wifi module. The shell command returns immediately after
 * posting the request.
 */
static int cmd_wifi_scan(const struct shell *sh, size_t argc, char **argv)
{
	struct net_if *iface;
	struct wifi_scan_params params;
	int ret;

	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	/*
	 * icle_wifi does not expose a direct scan API; scans are initiated
	 * at the netctl/wifi_sta layer. Post ICLE_EVENT_WIFI_SCAN_DONE
	 * is produced by the driver after scanning. For now we use the
	 * Zephyr net_mgmt scan request through the network interface.
	 */
	iface = icle_wifi_get_iface();

	if (iface == NULL) {
		shell_error(sh, "WiFi interface not available");
		return -ENODEV;
	}

	params = (struct wifi_scan_params){
		.scan_type = WIFI_SCAN_TYPE_PASSIVE,
	};

	ret = net_mgmt(NET_REQUEST_WIFI_SCAN, iface, &params,
		       sizeof(params));

	if (ret < 0) {
		shell_error(sh, "WiFi scan request failed: %d", ret);
		return ret;
	}

	shell_print(sh, "WiFi scan started — results appear in log output");
	return 0;
}

/*
 * storage stats
 */

/**
 * @brief Handler for: icle storage stats
 *
 * Reads and displays the SD card storage statistics.
 */
static int cmd_storage_stats(const struct shell *sh, size_t argc, char **argv)
{
	struct icle_storage_stats stats;
	uint64_t total_kib;
	uint64_t free_kib;
	uint64_t used_kib;
	int ret;

	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	ret = icle_storage_get_stats(&stats);

	if (ret < 0) {
		shell_error(sh, "Failed to get storage stats: %d", ret);
		return ret;
	}

	/* Convert bytes to KiB for readability */
	total_kib = stats.total_bytes / 1024U;
	free_kib  = stats.free_bytes / 1024U;
	used_kib  = (stats.total_bytes - stats.free_bytes) / 1024U;

	shell_print(sh, "Storage Statistics:");
	shell_print(sh, "  state:          %s",
		    icle_storage_state_name(stats.state));
	shell_print(sh, "  total:          %llu KiB", total_kib);
	shell_print(sh, "  used:           %llu KiB", used_kib);
	shell_print(sh, "  free:           %llu KiB", free_kib);
	shell_print(sh, "  log_files:      %u", stats.log_file_count);
	shell_print(sh, "  pending_sync:   %u", stats.pending_sync_count);

	if (stats.current_log_file[0] != '\0')
		shell_print(sh, "  active_log:     %s", stats.current_log_file);

	return 0;
}

/*
 * power read
 */

/**
 * @brief Handler for: icle power read
 *
 * Takes a single on-demand measurement from the INA209 power monitor
 * and prints voltage, current, and power.
 */
static int cmd_power_read(const struct shell *sh, size_t argc, char **argv)
{
	struct icle_power_data data;
	int32_t voltage_mv;
	int32_t voltage_uv_frac;
	int32_t current_ma;
	int32_t current_ua_frac;
	int32_t power_mw;
	int32_t power_uw_frac;
	int ret;

	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	ret = icle_power_read(&data);

	if (ret < 0) {
		shell_error(sh, "Power read failed: %d", ret);
		return ret;
	}

	/*
	 * Convert from microvolts/microamps/microwatts to mV/mA/mW with
	 * one decimal place for readability on a serial terminal.
	 */
	voltage_mv = data.voltage_uv / 1000;
	voltage_uv_frac = data.voltage_uv % 1000;

	current_ma = data.current_ua / 1000;
	current_ua_frac = data.current_ua % 1000;

	power_mw = data.power_uw / 1000;
	power_uw_frac = data.power_uw % 1000;

	shell_print(sh, "Power Monitor (INA209):");
	shell_print(sh, "  voltage: %d.%03d mV  (%d uV)",
		    voltage_mv, voltage_uv_frac, data.voltage_uv);
	shell_print(sh, "  current: %d.%03d mA  (%d uA)",
		    current_ma, current_ua_frac, data.current_ua);
	shell_print(sh, "  power:   %d.%03d mW  (%d uW)",
		    power_mw, power_uw_frac, data.power_uw);

	return 0;
}

/*
 * log start
 */

/**
 * @brief Handler for: icle log start
 *
 * Starts periodic power sampling using the configured sample_interval.
 * If already sampling, reports current status without error.
 */
static int cmd_log_start(const struct shell *sh, size_t argc, char **argv)
{
	uint32_t interval_ms;
	int ret;

	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	if (icle_log_is_sampling()) {
		shell_print(sh, "Logger already active (interval: %u ms)",
			    icle_log_get_interval());
		return 0;
	}

	interval_ms = icle_config_get_sample_interval();
	ret = icle_log_start_sampling(interval_ms);

	if (ret < 0) {
		shell_error(sh, "Failed to start logger: %d", ret);
		return ret;
	}

	shell_print(sh, "Logger started (interval: %u ms)", interval_ms);
	return 0;
}

/*
 * log stop
 */

/**
 * @brief Handler for: icle log stop
 *
 * Stops periodic power sampling and flushes any pending queue entries
 * to SD card.
 */
static int cmd_log_stop(const struct shell *sh, size_t argc, char **argv)
{
	int ret;

	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	if (!icle_log_is_sampling()) {
		shell_print(sh, "Logger already stopped");
		return 0;
	}

	ret = icle_log_stop_sampling();

	if (ret < 0) {
		shell_error(sh, "Failed to stop logger: %d", ret);
		return ret;
	}

	shell_print(sh, "Logger stopped");
	return 0;
}

/*
 * log status
 */

/**
 * @brief Handler for: icle log status
 *
 * Prints logger statistics: sample counts, queue depth, and write errors.
 */
static int cmd_log_status(const struct shell *sh, size_t argc, char **argv)
{
	struct icle_log_stats stats;
	int ret;

	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	ret = icle_log_get_stats(&stats);

	if (ret < 0) {
		shell_error(sh, "Failed to get log stats: %d", ret);
		return ret;
	}

	shell_print(sh, "Logger Status:");
	shell_print(sh, "  sampling:       %s",
		    stats.sampling_active ? "active" : "stopped");
	shell_print(sh, "  interval_ms:    %u", icle_log_get_interval());
	shell_print(sh, "  samples_taken:  %u", stats.samples_taken);
	shell_print(sh, "  samples_written:%u", stats.samples_written);
	shell_print(sh, "  samples_dropped:%u", stats.samples_dropped);
	shell_print(sh, "  queue_depth:    %u", stats.queue_depth);
	shell_print(sh, "  max_queue_depth:%u", stats.max_queue_depth);
	shell_print(sh, "  write_errors:   %u", stats.write_errors);

	return 0;
}

/*
 * Subcommand trees — built with SHELL_STATIC_SUBCMD_SET_CREATE
 */

/* icle config {show, set} */
SHELL_STATIC_SUBCMD_SET_CREATE(sub_config,
	SHELL_CMD(show, NULL,
		  "Display current configuration\n"
		  "Usage: icle config show",
		  cmd_config_show),
	SHELL_CMD_ARG(set, NULL,
		      "Set a configuration value\n"
		      "Usage: icle config set <key> <value>\n"
		      "Keys: device_id, wifi_ssid, wifi_psk, backend_url,\n"
		      "      sample_interval, heartbeat_interval, log_format",
		      cmd_config_set,
		      3,  /* min args: cmd + key + value */
		      0), /* no optional args */
	SHELL_SUBCMD_SET_END
);

/* icle wifi {status, scan} */
SHELL_STATIC_SUBCMD_SET_CREATE(sub_wifi,
	SHELL_CMD(status, NULL,
		  "Show WiFi connection status\n"
		  "Usage: icle wifi status",
		  cmd_wifi_status),
	SHELL_CMD(scan, NULL,
		  "Trigger a WiFi scan\n"
		  "Usage: icle wifi scan",
		  cmd_wifi_scan),
	SHELL_SUBCMD_SET_END
);

/* icle storage {stats} */
SHELL_STATIC_SUBCMD_SET_CREATE(sub_storage,
	SHELL_CMD(stats, NULL,
		  "Show SD card storage statistics\n"
		  "Usage: icle storage stats",
		  cmd_storage_stats),
	SHELL_SUBCMD_SET_END
);

/* icle power {read} */
SHELL_STATIC_SUBCMD_SET_CREATE(sub_power,
	SHELL_CMD(read, NULL,
		  "Read current power measurement from INA209\n"
		  "Usage: icle power read",
		  cmd_power_read),
	SHELL_SUBCMD_SET_END
);

/* icle log {start, stop, status} */
SHELL_STATIC_SUBCMD_SET_CREATE(sub_log,
	SHELL_CMD(start, NULL,
		  "Start power sampling\n"
		  "Usage: icle log start",
		  cmd_log_start),
	SHELL_CMD(stop, NULL,
		  "Stop power sampling\n"
		  "Usage: icle log stop",
		  cmd_log_stop),
	SHELL_CMD(status, NULL,
		  "Show logger statistics\n"
		  "Usage: icle log status",
		  cmd_log_status),
	SHELL_SUBCMD_SET_END
);

/*
 * Top-level "icle" command group
 */

SHELL_STATIC_SUBCMD_SET_CREATE(sub_icle,
	SHELL_CMD(config,  &sub_config,
		  "Configuration management (show/set)", NULL),
	SHELL_CMD(wifi,    &sub_wifi,
		  "WiFi management (status/scan)", NULL),
	SHELL_CMD(storage, &sub_storage,
		  "Storage statistics", NULL),
	SHELL_CMD(power,   &sub_power,
		  "Power monitor (INA209 read)", NULL),
	SHELL_CMD(log,     &sub_log,
		  "Logger control (start/stop/status)", NULL),
	SHELL_SUBCMD_SET_END
);

SHELL_CMD_REGISTER(icle, &sub_icle,
		   "ICLE device management commands", NULL);

/*
 * Module init
 */

int icle_shell_cmds_init(void)
{
	/* Shell commands are registered at build time via SHELL_CMD_REGISTER.
	 * This function is a no-op placeholder kept for callers that need a
	 * hook to confirm the shell module is linked in.
	 */
	LOG_INF("ICLE shell commands registered");
	return 0;
}
