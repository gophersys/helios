// Standard includes
#include <stdio.h>
#include <stddef.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>
#include <zephyr/net/net_ip.h>
#include <zephyr/posix/netinet/in.h>
#include <zephyr/posix/sys/socket.h>

// Cipher includes
#include "utils/err.h"
#include "transport/transport.h"

LOG_MODULE_DECLARE(tal);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/

/**
 * We don't check for NULL interfaces in any function, since TAL guarantees to not call us without a
 * valid interface pointer.
 */

/*-----------------------------------------------------------------------------------------------------
 *                                                                            Socket TAL Implementation
 *---------------------------------------------------------------------------------------------------*/
bool socket_create(tal_config_t *cfg)
{
    __ASSERT(cfg->host, "Interface host cannot be NULL");
    __ASSERT(cfg->port != 0, "Interface port cannot be zero");

    cfg->socket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (cfg->socket < 0)
    {
        WARN("Socket creation failed: %s", strerror(errno));
        return false;
    }

    // If the interface is set to DOWNLINK, we'll bind the socket to the provided port.
    // This prepares the socket to accept incoming connections.
    if (cfg->link == TAL_LINK_TYPE_DOWNLINK)
    {
        struct sockaddr_in local_addr = {0};
        local_addr.sin_family = AF_INET;
        local_addr.sin_port = htons(cfg->port);
        local_addr.sin_addr.s_addr = INADDR_ANY; // Bind to all available interfaces

        if (bind(cfg->socket, (struct sockaddr *)&local_addr, sizeof(local_addr)) < 0)
        {
            WARN("Socket bind failed: %s", strerror(errno));
            close(cfg->socket);
            return false;
        }
    }

    return true;
}

bool socket_set_opt(tal_config_t *cfg, tal_option_type_t type, void *option, size_t option_size)
{
    __ASSERT(option, "Option pointer cannot be NULL");

    int ret = -1;

    switch (type)
    {
    case TAL_OPTION_SEND_TIMEOUT:
    case TAL_OPTION_RECV_TIMEOUT:
    {
        __ASSERT(option_size == sizeof(uint16_t), "Option size mismatch for TIMEOUT options");

        struct timeval tv;
        tv.tv_sec = (*(uint16_t *)option) / 1000;
        tv.tv_usec = ((*(uint16_t *)option) % 1000) * 1000;
        int optname = (type == TAL_OPTION_SEND_TIMEOUT) ? SO_SNDTIMEO : SO_RCVTIMEO;

        ret = setsockopt(cfg->socket, SOL_SOCKET, optname, &tv, sizeof(tv));
        if (ret < 0)
        {
            WARN("Failed to set socket option: %s", strerror(errno));
            return false;
        }
    }
    break;
    default:
        WARN("Invalid option type %d provided", type);
        return false;
    }

    return true;
}

bool socket_connect(tal_config_t *cfg, bool *timeout)
{
    __ASSERT(timeout, "Timeout pointer cannot be NULL");
    __ASSERT(cfg->host, "Interface host cannot be NULL");
    __ASSERT(cfg->port != 0, "Interface port cannot be zero");

    struct sockaddr_in remote_addr;
    remote_addr.sin_family = AF_INET;
    remote_addr.sin_port = htons(cfg->port);
    inet_pton(AF_INET, cfg->host, &remote_addr.sin_addr); // Convert IP string to sockaddr_in format.

    if (connect(cfg->socket, (struct sockaddr *)&remote_addr, sizeof(remote_addr)) < 0)
    {
        if (errno == EINPROGRESS || errno == EAGAIN || errno == EWOULDBLOCK) // These indicate a timeout.
        {
            *timeout = true;
            return false;
        }
        WARN("Socket connect failed: %s", strerror(errno));
        return false;
    }

    *timeout = false; // No timeout occurred.
    return true;
}

bool socket_accept(tal_config_t *cfg, bool *timeout)
{
    __ASSERT(timeout, "Timeout pointer cannot be NULL");

    struct sockaddr_in client_addr;
    socklen_t addr_len = sizeof(client_addr);

    int client_socket = accept(cfg->socket, (struct sockaddr *)&client_addr, &addr_len);
    if (client_socket < 0)
    {
        if (errno == EAGAIN || errno == EWOULDBLOCK) // These indicate a timeout.
        {
            *timeout = true;
            return false;
        }
        WARN("Socket accept failed: %s", strerror(errno));
        return false;
    }
    *timeout = false; // No timeout occurred.

    cfg->socket = client_socket; // Update cfg->socketfd with the new connected socket.
    return true;
}

bool socket_send(const tal_config_t *cfg, const void *buffer, const size_t buffer_size,
                 uint16_t *send_count, bool *conn_closed, bool *timeout)
{
    __ASSERT(buffer, "Buffer pointer cannot be NULL");
    __ASSERT(send_count, "Send count pointer cannot be NULL");
    __ASSERT(conn_closed, "Connection closed pointer cannot be NULL");
    __ASSERT(timeout, "Timeout pointer cannot be NULL");

    int socket_send_count = send(cfg->socket, buffer, buffer_size, 0);

    if (socket_send_count > 0)
    {
        *send_count = (uint16_t)socket_send_count;
        *conn_closed = false;
        *timeout = false;
        return true;
    }
    else
    {
        *send_count = 0;
        *timeout = false; // Initialize to false

        if (errno == ECONNRESET || errno == EPIPE)
        {
            *conn_closed = true;
            DBG("Connection closed by remote peer on socket %d", cfg->socket);
        }
        else if (errno == EAGAIN || errno == EWOULDBLOCK)
        {
            *timeout = true;
        }
        else
        {
            *conn_closed = false;
            WARN("Socket send error: %s", strerror(errno));
        }

        return false;
    }
}

bool socket_recv(const tal_config_t *cfg, void *buffer, const size_t buffer_size,
                 uint16_t *recv_count, bool *conn_closed, bool *timeout)
{
    __ASSERT(buffer, "Buffer pointer cannot be NULL");
    __ASSERT(recv_count, "Receive count pointer cannot be NULL");
    __ASSERT(conn_closed, "Connection closed pointer cannot be NULL");
    __ASSERT(timeout, "Timeout pointer cannot be NULL");

    int socket_recv_count = recv(cfg->socket, buffer, buffer_size, 0);

    if (socket_recv_count > 0)
    {
        *recv_count = (uint16_t)socket_recv_count;
        *conn_closed = false;
        *timeout = false;
        return true;
    }
    else if (socket_recv_count == 0)
    {
        *recv_count = 0;
        *conn_closed = true; // Graceful shutdown by the peer.
        *timeout = false;
        DBG("Connection closed by remote peer on socket %d", cfg->socket);
        return false;
    }
    else
    {
        *recv_count = 0;
        *timeout = false; // Initialize to false

        if (errno == ECONNRESET)
        {
            *conn_closed = true;
            WARN("Connection reset by remote peer");
        }
        else if (errno == EAGAIN || errno == EWOULDBLOCK)
        {
            *timeout = true;
        }
        else
        {
            *conn_closed = false;
            WARN("Socket receive error: %s", strerror(errno));
        }

        return false;
    }
}
bool socket_close(const tal_config_t *cfg)
{
    int result = close(cfg->socket);
    if (result < 0)
    {
        WARN("Failed to close the socket: %s", strerror(errno));
        return false;
    }
    return true;
}
