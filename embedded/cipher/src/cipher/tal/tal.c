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

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

// Sockets
static bool socket_connect(tal_config_t *cfg);
static bool socket_accept(tal_config_t *cfg);
static bool socket_send(const tal_config_t *cfg, const void *buffer, const size_t buffer_size, uint16_t *send_count, bool *conn_closed);
static bool socket_recv(const tal_config_t *cfg, void *buffer, const size_t buffer_size, uint16_t *recv_count, bool *conn_closed);
static bool socket_close(const tal_config_t *cfg);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/

bool tal_connect(tal_config_t *cfg)
{
    bool status = false;

    switch (cfg->type)
    {
    case TAL_INTERFACE_TYPE_SOCKET:
        status = socket_connect(cfg);
        break;
    case TAL_INTERFACE_TYPE_UART:
        // TODO: Implement me
        break;
    default:
        ERROR("Unknown or implemented interface interface: %d", cfg->type);
    }

    return status;
}

bool tal_accept(tal_config_t *cfg)
{
    bool status = false;

    switch (cfg->type)
    {
    case TAL_INTERFACE_TYPE_SOCKET:
        status = socket_accept(cfg);
        break;
    case TAL_INTERFACE_TYPE_UART:
        // TODO: Implement me
        break;
    default:
        ERROR("Unknown or implemented interface interface: %d", cfg->type);
    }

    return status;
}

bool tal_send(const tal_config_t *cfg, const void *buffer, const size_t buffer_size, uint16_t *send_count, bool *conn_closed)
{
    bool status = false;

    switch (cfg->type)
    {
    case TAL_INTERFACE_TYPE_SOCKET:
        status = socket_send(cfg, buffer, buffer_size, send_count, conn_closed);
        break;
    case TAL_INTERFACE_TYPE_UART:
        // TODO: Implement me
        break;
    default:
        ERROR("Unknown or implemented interface interface: %d", cfg->type);
    }

    return status;
}

bool tal_recv(const tal_config_t *cfg, void *buffer, const size_t buffer_size, uint16_t *recv_count, bool *conn_closed)
{
    bool status = false;

    switch (cfg->type)
    {
    case TAL_INTERFACE_TYPE_SOCKET:
        status = socket_recv(cfg, buffer, buffer_size, recv_count, conn_closed);
        break;
    case TAL_INTERFACE_TYPE_UART:
        // TODO: Implement me
        break;
    default:
        ERROR("Unknown or implemented interface interface: %d", cfg->type);
    }

    return status;
}

bool tal_close(const tal_config_t *cfg)
{
    bool status = false;

    switch (cfg->type)
    {
    case TAL_INTERFACE_TYPE_SOCKET:
        status = socket_close(cfg);
        break;
    case TAL_INTERFACE_TYPE_UART:
        // TODO: Implement me
        break;
    default:
        ERROR("Unknown or implemented interface interface: %d", cfg->type);
    }

    return status;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                Socket Implementation
 *---------------------------------------------------------------------------------------------------*/
bool socket_connect(tal_config_t *cfg)
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
                cfg->socket = sockfd;
            }
        }
    }

    return status;
}

static bool socket_accept(tal_config_t *cfg)
{
    bool status = true;
    int sockfd;

    struct sockaddr_in server_addr;
    struct sockaddr_in client_addr;
    socklen_t client_addr_len = sizeof(client_addr);

    // Create the listening socket
    int listen_sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (listen_sock < 0)
    {
        WARN("Failed to create listening socket. Error: %d", errno);
        status = false;
    }

    // If the listening socket was successfully created, continue with the bind operation
    if (status)
    {
        memset(&server_addr, 0, sizeof(server_addr));
        server_addr.sin_family = AF_INET;
        server_addr.sin_addr.s_addr = htonl(INADDR_ANY);
        server_addr.sin_port = htons(cfg->port);

        sockfd = bind(listen_sock, (struct sockaddr *)&server_addr, sizeof(server_addr));
        if (sockfd < 0)
        {
            WARN("Failed to bind to socket. Error: %d", errno);
            status = false;
        }
    }

    // Start listening
    if (status)
    {
        sockfd = listen(listen_sock, 1); // Only allowing 1 client in the queue for simplicity.
        if (sockfd < 0)
        {
            WARN("Failed to start listening on socket. Error: %d", errno);
            status = false;
        }
    }

    // Accept the incoming client connection
    if (status)
    {
        int client_sock = accept(listen_sock, (struct sockaddr *)&client_addr, &client_addr_len);
        if (client_sock < 0)
        {
            WARN("Failed to accept client connection. Error: %d", errno);
            status = false;
        }
        else
        {
            cfg->host = inet_ntoa(client_addr.sin_addr);
            cfg->port = ntohs(client_addr.sin_port);
            cfg->socket = client_sock;
        }
    }

    // Always close the listening socket
    close(listen_sock);

    return status;
}
static bool socket_send(const tal_config_t *cfg, const void *buffer, const size_t buffer_size, uint16_t *send_count, bool *conn_closed)
{
    bool status = false;

    int socket_send_count = send(cfg->socket, buffer, buffer_size, 0);
    if (socket_send_count > 0)
    {
        *send_count = (uint16_t)socket_send_count;
        status = true;
    }
    else
    {
        if (errno == ECONNRESET || errno == EPIPE)
        {
            *conn_closed = true;
        }
        else
        {
            WARN("Unknown socket send error: %d", errno);
        }
        *send_count = 0;
    }

    return status;
}

static bool socket_recv(const tal_config_t *cfg, void *buffer, const size_t buffer_size, uint16_t *recv_count, bool *conn_closed)
{
    bool status = false;

    int socket_recv_count = recv(cfg->socket, buffer, buffer_size, 0);

    if (socket_recv_count > 0)
    {
        *recv_count = (uint16_t)socket_recv_count;
        status = true;
    }
    else if (socket_recv_count == 0)
    {
        // The recv function returning 0 indicates a graceful shutdown by the peer.
        *conn_closed = true;
        *recv_count = 0;
    }
    else
    {
        if (errno == ECONNRESET)
        {
            *conn_closed = true;
        }
        *recv_count = 0;
    }

    return status;
}

static bool socket_close(const tal_config_t *cfg)
{
    close(cfg->socket);
    return true;
}