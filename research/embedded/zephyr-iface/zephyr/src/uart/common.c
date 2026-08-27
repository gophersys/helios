#include "common.h"

// Standard includes
#include <stdbool.h>

// Private library includes
#include "stack/stack.h"

//TODO: comment what this does
#define INTERNAL_SEND_TIMEOUT_MS 500
#define INTERNAL_RECV_TIMEOUT_MS 500

static uart_stack_t _uart_stack = {0};
static uart_stack_config_t _uart_net_cfg =
{
    .transport_type = UART_TRANSPORT_TYPE_UDP,  //  Only UDP-like transport is supported right now
};


uart_stack_t *uart_get_stack(void)
{
    return &_uart_stack;
}

uart_stack_config_t *uart_get_stack_cfg(void)
{
    return &_uart_net_cfg;
}


uint16_t uart_get_internal_send_timeout(void)
{
    return INTERNAL_SEND_TIMEOUT_MS;
}

uint16_t uart_get_internal_recv_timeout(void)
{
    return INTERNAL_RECV_TIMEOUT_MS;
}