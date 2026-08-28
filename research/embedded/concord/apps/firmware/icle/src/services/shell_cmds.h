// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE Shell Commands
 *
 * Zephyr shell command registration for ICLE runtime inspection and
 * control. Commands are grouped under the top-level "icle" namespace:
 *
 *   icle config show
 *   icle config set <key> <value>
 *   icle wifi status
 *   icle wifi scan
 *   icle storage stats
 *   icle power read
 *   icle log start
 *   icle log stop
 *   icle log status
 */

#ifndef ICLE_SERVICES_SHELL_CMDS_H_
#define ICLE_SERVICES_SHELL_CMDS_H_

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Register ICLE shell commands with the Zephyr shell subsystem.
 *
 * Must be called after all subsystems (config, wifi, storage, logger,
 * power monitor) have been initialized. Safe to call from APPLICATION
 * SYS_INIT or from icle_app_init().
 *
 * @return 0 on success, negative errno on failure.
 */
int icle_shell_cmds_init(void);

#ifdef __cplusplus
}
#endif

#endif /* ICLE_SERVICES_SHELL_CMDS_H_ */
