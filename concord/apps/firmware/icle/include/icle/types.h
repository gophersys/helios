// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Shared Data Types
 */

#ifndef ICLE_TYPES_H_
#define ICLE_TYPES_H_

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Power measurement data
 */
struct icle_power_data {
	int32_t voltage_uv;      /* Bus voltage in microvolts */
	int32_t current_ua;      /* Current in microamps */
	int32_t power_uw;        /* Power in microwatts */
};

/**
 * @brief Log entry status flags
 */
enum icle_log_flags {
	ICLE_LOG_FLAG_NONE        = 0,
	ICLE_LOG_FLAG_OVERFLOW    = (1 << 0),  /* Sample queue overflow */
	ICLE_LOG_FLAG_SENSOR_ERR  = (1 << 1),  /* Sensor read error */
	ICLE_LOG_FLAG_SYNC_POINT  = (1 << 2),  /* Sync checkpoint */
	ICLE_LOG_FLAG_MODE_CHANGE = (1 << 3),  /* Operating mode changed */
};

/**
 * @brief Single log entry (power measurement sample)
 */
struct icle_log_entry {
	uint32_t timestamp_ms;   /* Uptime at sample time */
	uint32_t rtc_time;       /* RTC epoch if available, 0 otherwise */
	int32_t voltage_uv;      /* Bus voltage in microvolts */
	int32_t current_ua;      /* Current in microamps */
	int32_t power_uw;        /* Power in microwatts */
	uint8_t flags;           /* Status flags */
	uint8_t reserved[3];     /* Alignment padding */
};

/**
 * @brief Log file format
 */
enum icle_log_format {
	ICLE_LOG_FORMAT_BINARY = 0,  /* Compact binary format */
	ICLE_LOG_FORMAT_CSV = 1,     /* Human-readable CSV */
};

/**
 * @brief MUX channel selection
 */
enum icle_mux_channel {
	ICLE_MUX_CH0 = 0,
	ICLE_MUX_CH1 = 1,
	ICLE_MUX_CH2 = 2,
	ICLE_MUX_CH3 = 3,
	ICLE_MUX_CH4 = 4,
	ICLE_MUX_CH5 = 5,
	ICLE_MUX_CH6 = 6,
	ICLE_MUX_CH7 = 7,
};

/**
 * @brief LED identifiers
 */
enum icle_led {
	ICLE_LED_GREEN = 0,
	ICLE_LED_RED = 1,
};

/**
 * @brief Wake source identification
 */
enum icle_wake_source {
	ICLE_WAKE_UNKNOWN = 0,
	ICLE_WAKE_BUTTON,       /* GPIO button press */
	ICLE_WAKE_TIMER,        /* RTC timer */
	ICLE_WAKE_RESET,        /* Power-on or reset */
};

#ifdef __cplusplus
}
#endif

#endif /* ICLE_TYPES_H_ */
