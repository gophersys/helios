#ifndef RAL_H
#define RAL_H

#include <stdbool.h>
#include <stdint.h>

#include <zephyr/logging/log.h>

typedef enum
{
    TAL_INTERFACE_TYPE_SOCKET,
    TAL_INTERFACE_TYPE_UART,

    TAL_INTERFACE_TYPE_MAX
} tal_interface_type_t;

typedef enum
{
    TAL_LINK_TYPE_UPLINK,
    TAL_LINK_TYPE_DOWNLINK,

    TAL_LINK_TYPE_MAX,
} tal_link_type_t;

typedef struct
{
    tal_interface_type_t interface;
    tal_link_type_t link;

    // Socket connection info
    uint16_t port;
    char *host;

    // Uart info
} tal_config_t;

// TODO: Add functions to set timeouts for send/recv
bool tal_connect(const tal_config_t *cfg);
bool tal_accept(const tal_config_t *cfg);
bool tal_send(const tal_config_t *cfg, const void *buffer, const size_t buffer_size, uint16_t *send_count, bool *conn_closed);
bool tal_recv(const tal_config_t *cfg, void *buffer, const size_t buffer_size, uint16_t *recv_count, bool *conn_closed);
bool tal_close(const tal_config_t *cfg);

#endif // RAL_H