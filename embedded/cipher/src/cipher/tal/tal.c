#include "tal.h"

// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "utils.h"
#include "socket.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/
// TODO:  Assert that none of the passed configs are null
// TODO: Asset all inputs to all functions make sure they're not null or invalid

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/
LOG_MODULE_REGISTER(tal, LOG_LEVEL_DBG);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/
typedef struct
{
    bool (*connect)(tal_config_t *cfg);
    bool (*accept)(tal_config_t *cfg);
    bool (*send)(const tal_config_t *cfg, const void *buffer, const size_t buffer_size, uint16_t *send_count, bool *conn_closed);
    bool (*recv)(const tal_config_t *cfg, void *buffer, const size_t buffer_size, uint16_t *recv_count, bool *conn_closed);
    bool (*close)(const tal_config_t *cfg);
} tal_interface_ops_t;

static const tal_interface_ops_t tal_ops[] = {
    [TAL_INTERFACE_TYPE_SOCKET] = {
        .connect = socket_connect,
        .accept = socket_accept,
        .send = socket_send,
        .recv = socket_recv,
        .close = socket_close,
    },
    [TAL_INTERFACE_TYPE_UART] = {
        // TODO: Implement UART
    },
};

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/
bool tal_connect(tal_config_t *cfg)
{
    if (cfg->type >= sizeof(tal_ops) / sizeof(tal_ops[0]) || !tal_ops[cfg->type].connect)
        ERROR("Unknown or unimplemented interface: %d", cfg->type);

    return tal_ops[cfg->type].connect(cfg);
}

bool tal_accept(tal_config_t *cfg)
{
    if (cfg->type >= sizeof(tal_ops) / sizeof(tal_ops[0]) || !tal_ops[cfg->type].accept)
        ERROR("Unknown or unimplemented interface: %d", cfg->type);

    return tal_ops[cfg->type].accept(cfg);
}

bool tal_send(const tal_config_t *cfg, const void *buffer, const size_t buffer_size, uint16_t *send_count, bool *conn_closed)
{
    if (cfg->type >= sizeof(tal_ops) / sizeof(tal_ops[0]) || !tal_ops[cfg->type].send)
        ERROR("Unknown or unimplemented interface: %d", cfg->type);

    return tal_ops[cfg->type].send(cfg, buffer, buffer_size, send_count, conn_closed);
}

bool tal_recv(const tal_config_t *cfg, void *buffer, const size_t buffer_size, uint16_t *recv_count, bool *conn_closed)
{
    if (cfg->type >= sizeof(tal_ops) / sizeof(tal_ops[0]) || !tal_ops[cfg->type].recv)
        ERROR("Unknown or unimplemented interface: %d", cfg->type);

    return tal_ops[cfg->type].recv(cfg, buffer, buffer_size, recv_count, conn_closed);
}

bool tal_close(const tal_config_t *cfg)
{
    if (cfg->type >= sizeof(tal_ops) / sizeof(tal_ops[0]) || !tal_ops[cfg->type].close)
        ERROR("Unknown or unimplemented interface: %d", cfg->type);

    return tal_ops[cfg->type].close(cfg);
}