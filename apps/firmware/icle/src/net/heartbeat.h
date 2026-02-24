/*
 * SPDX-License-Identifier: Apache-2.0
 * ICLE Backend Heartbeat Service
 *
 * Periodic heartbeat to backend with command processing.
 */

#ifndef ICLE_HEARTBEAT_H_
#define ICLE_HEARTBEAT_H_

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Heartbeat response command types
 */
enum icle_heartbeat_cmd {
	ICLE_HB_CMD_NONE = 0,
	ICLE_HB_CMD_CONFIG_UPDATE,    /* New configuration available */
	ICLE_HB_CMD_FIRMWARE_UPDATE,  /* OTA firmware update */
	ICLE_HB_CMD_REBOOT,           /* Reboot device */
	ICLE_HB_CMD_SYNC_NOW,         /* Force immediate log sync */
};

/**
 * @brief Heartbeat command callback
 */
typedef void (*icle_heartbeat_cmd_cb_t)(enum icle_heartbeat_cmd cmd,
					const char *payload,
					void *user_data);

/**
 * @brief Initialize heartbeat service
 *
 * @return 0 on success, negative errno on failure
 */
int icle_heartbeat_init(void);

/**
 * @brief Deinitialize heartbeat service
 *
 * @return 0 on success, negative errno on failure
 */
int icle_heartbeat_deinit(void);

/**
 * @brief Start heartbeat service
 *
 * @param interval_ms Heartbeat interval in milliseconds
 * @return 0 on success, negative errno on failure
 */
int icle_heartbeat_start(uint32_t interval_ms);

/**
 * @brief Stop heartbeat service
 *
 * @return 0 on success, negative errno on failure
 */
int icle_heartbeat_stop(void);

/**
 * @brief Send immediate heartbeat
 *
 * @return 0 on success, negative errno on failure
 */
int icle_heartbeat_send(void);

/**
 * @brief Check if heartbeat service is running
 *
 * @return true if running
 */
bool icle_heartbeat_is_running(void);

/**
 * @brief Register command callback
 *
 * @param callback Callback function
 * @param user_data User context
 * @return 0 on success, negative errno on failure
 */
int icle_heartbeat_register_callback(icle_heartbeat_cmd_cb_t callback,
				     void *user_data);

/**
 * @brief Set heartbeat interval
 *
 * @param interval_ms New interval in milliseconds
 * @return 0 on success, negative errno on failure
 */
int icle_heartbeat_set_interval(uint32_t interval_ms);

/**
 * @brief Get last heartbeat timestamp
 *
 * @return Uptime timestamp of last successful heartbeat
 */
uint32_t icle_heartbeat_get_last_time(void);

#ifdef __cplusplus
}
#endif

#endif /* ICLE_HEARTBEAT_H_ */
