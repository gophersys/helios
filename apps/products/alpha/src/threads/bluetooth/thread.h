#ifndef THREADS_BLUETOOTH_H
#define THREADS_BLUETOOTH_H

// Standard includes
#include <stdbool.h>

// Thread includes
#include "types.h"

/**
 * @brief Initialize the bluetooth thread
 *
 * @param p_config  The configuration for the bluetooth thread
 * @param p_thread  The thread structure to initialize
 * @return true     If the thread was initialized successfully
 * @return false    If the thread was not initialized successfully
 */
bool bluetooth_thread_init(const bluetooth_thread_config_t *p_config, bluetooth_thread_t *p_thread);

/**
 * @brief Send ppg data to the bluetooth thread
 *
 * @param p_thread  The thread to send the data to
 * @param p_data    The data to send
 * @param length    The length of the data
 * @return true     If the data was sent successfully
 * @return false    If the data was not sent successfully
 */
bool bluetooth_send_sensor_data(bluetooth_thread_data_type_t type, uint8_t *p_data, size_t length);

#endif  // THREADS_BLUETOOTH_H
