#include "tal.h"

// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "utils.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/
LOG_MODULE_REGISTER(tal);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

// Sockets
static bool socket_connect(const tal_config_t *cfg);
static bool socket_send(const tal_config_t *cfg, const void *buffer, const size_t buffer_size, uint16_t *send_count, bool *conn_closed);
static bool socket_recv(const tal_config_t *cfg, void *buffer, const size_t buffer_size, uint16_t *recv_count, bool *conn_closed);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/
bool tal_connect(const tal_config_t *cfg)
{
    bool status = false;

    switch (cfg->interface)
    {
    case TAL_INTERFACE_TYPE_SOCKET:
        status = socket_connect(cfg);
        break;
    case TAL_INTERFACE_TYPE_UART:
        // TODO: Implement me
        break;
    default:
        ERROR("Unknown or implemented interface interface: %d", cfg->interface);
    }

    return status;
}

bool tal_recv(const tal_config_t *cfg, void *buffer, const size_t buffer_size, uint16_t *recv_count, bool *conn_closed)
{
    bool status = false;

    switch (cfg->interface)
    {
    case TAL_INTERFACE_TYPE_SOCKET:
        status = socket_recv(cfg, buffer, buffer_size, recv_count, conn_closed);
        break;
    case TAL_INTERFACE_TYPE_UART:
        // TODO: Implement me
        break;
    default:
        ERROR("Unknown or implemented interface interface: %d", cfg->interface);
    }

    return status;
}

bool tal_send(const tal_config_t *cfg, const void *buffer, const size_t buffer_size, uint16_t *send_count, bool *conn_closed)
{
    bool status = false;

    switch (cfg->interface)
    {
    case TAL_INTERFACE_TYPE_SOCKET:
        status = socket_send(cfg, buffer, buffer_size, send_count, conn_closed);
        break;
    case TAL_INTERFACE_TYPE_UART:
        // TODO: Implement me
        break;
    default:
        ERROR("Unknown or implemented interface interface: %d", cfg->interface);
    }

    return status;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                Socket Implementation
 *---------------------------------------------------------------------------------------------------*/
bool socket_connect(const tal_config_t *cfg)
{
    bool status = false;

    int sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sockfd < 0)
    {
        WARN("Error creating socket");
    }
    else
    {
        struct sockaddr_in serv_addr;
        memset(&serv_addr, 0, sizeof(serv_addr));

        serv_addr.sin_family = AF_INET;
        serv_addr.sin_port = htons(cfg->port);

        if (inet_pton(AF_INET, cfg->host, &serv_addr.sin_addr) <= 0)
        {
            WARN("Invalid IP address/not supported");
            close(sockfd);
        }
        else
        {
            if (connect(sockfd, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) < 0)
            {
                WARN("connect() failed");
                close(sockfd);
            }
            else
            {
                status = true; // Succesful connection
            }
        }
    }

    return status;
}

static bool socket_send(const tal_config_t *cfg, const void *buffer, const size_t buffer_size, uint16_t *send_count, bool *conn_closed)
{
    bool status = false;
    // TODO: Me
    return status;
}

static bool socket_recv(const tal_config_t *cfg, void *buffer, const size_t buffer_size, uint16_t *recv_count, bool *conn_closed)
{
    bool status = false;
    // TODO: Me
    return status;
}