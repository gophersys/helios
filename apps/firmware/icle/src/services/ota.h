// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE OTA Update Service
 *
 * ESP32 Over-The-Air firmware update support.
 */

#ifndef ICLE_OTA_H_
#define ICLE_OTA_H_

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief OTA update state
 */
enum icle_ota_state {
	ICLE_OTA_IDLE,
	ICLE_OTA_DOWNLOADING,
	ICLE_OTA_VERIFYING,
	ICLE_OTA_APPLYING,
	ICLE_OTA_COMPLETE,
	ICLE_OTA_ERROR,
};

/**
 * @brief OTA progress callback
 */
typedef void (*icle_ota_progress_cb_t)(uint32_t bytes_received,
				       uint32_t total_bytes,
				       void *user_data);

/**
 * @brief OTA complete callback
 */
typedef void (*icle_ota_complete_cb_t)(bool success,
				       const char *error_msg,
				       void *user_data);

/**
 * @brief Initialize OTA subsystem
 *
 * @return 0 on success, negative errno on failure
 */
int icle_ota_init(void);

/**
 * @brief Start OTA update from URL
 *
 * @param url Firmware download URL
 * @return 0 on success, negative errno on failure
 */
int icle_ota_start(const char *url);

/**
 * @brief Cancel ongoing OTA update
 *
 * @return 0 on success, negative errno on failure
 */
int icle_ota_cancel(void);

/**
 * @brief Get current OTA state
 *
 * @return Current OTA state
 */
enum icle_ota_state icle_ota_get_state(void);

/**
 * @brief Check if OTA is in progress
 *
 * @return true if OTA is active
 */
bool icle_ota_is_active(void);

/**
 * @brief Register progress callback
 *
 * @param callback Progress callback
 * @param user_data User context
 * @return 0 on success
 */
int icle_ota_set_progress_callback(icle_ota_progress_cb_t callback,
				   void *user_data);

/**
 * @brief Register complete callback
 *
 * @param callback Complete callback
 * @param user_data User context
 * @return 0 on success
 */
int icle_ota_set_complete_callback(icle_ota_complete_cb_t callback,
				   void *user_data);

/**
 * @brief Get OTA state name string
 *
 * @param state OTA state
 * @return State name string
 */
const char *icle_ota_state_name(enum icle_ota_state state);

/**
 * @brief Mark current firmware as valid (rollback protection)
 *
 * @return 0 on success, negative errno on failure
 */
int icle_ota_mark_valid(void);

/**
 * @brief Request rollback to previous firmware
 *
 * @return 0 on success (will reboot), negative errno on failure
 */
int icle_ota_rollback(void);

#ifdef __cplusplus
}
#endif

#endif /* ICLE_OTA_H_ */
