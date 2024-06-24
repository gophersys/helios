#ifndef APP_UART_H
#define APP_UART_H

// Standard includes
#include <stddef.h>
#include <stdio.h>

// Zephyr includes
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Protocol includes
#include "protos/mtib_runner_zephyr/mtib_runner_zephyr.cipher.h"

#define NUM_PORTS 2
#define RECV_CB_BUFFER_SIZE 128
#define SEND_BUFFER_SIZE  1024

typedef struct
{
    bool in_use;
    uint8_t buffer[RECV_CB_BUFFER_SIZE];
} uart_cb_buffer_t;

/**
 * @struct uart_send_buffer_t
 */
typedef struct
{
    bool in_use;
    uint8_t buffer[SEND_BUFFER_SIZE];
} uart_send_buffer_t;

/**
 * @brief Initializes the needed threads and objects to forward UART traffic
 *
 * @return true Initialized OK
 * @return false An error ocurred. Look at LOG output
 */
bool app_uart_forwarder_init(void);

bool app_uart_forwarder_enable(UartDeviceType device);
bool app_uart_forwarder_disable(UartDeviceType device);

bool app_uart_forwarder_send_data(UartDeviceType device, uint8_t *data, size_t data_size);

#endif // APP_UART_H