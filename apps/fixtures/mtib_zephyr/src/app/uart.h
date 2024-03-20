#ifndef APP_UART_H
#define APP_UART_H

// Standard includes
#include <stddef.h>
#include <stdio.h>

// Zephyr includes
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#define NUM_PORTS 2
#define RECV_CB_BUFFER_SIZE 64
#define MAX_PAYLOAD_SIZE  128

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
    uint8_t buffer[MAX_PAYLOAD_SIZE];
} uart_send_buffer_t;

bool app_uart_forwarder_init(void);

#endif // APP_UART_H