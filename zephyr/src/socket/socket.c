#include "socket.h"

#include <corekinect/iface/iface.h>

// Standard includes
#include <stddef.h>
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/net_ip.h>
#include <zephyr/net/socket.h>
// #include <zephyr/posix/netinet/in.h>
// #include <zephyr/posix/sys/socket.h>

LOG_MODULE_DECLARE(iface);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/

/**
 * We don't check for NULL interfaces in any function, since caller guarantees to not call us without a
 * valid interface pointer.
 */

//TODO: Clean the living hell of this file, ASSERTS, names etc

/*-----------------------------------------------------------------------------------------------------
 *                                                                          Socket iface Implementation
 *---------------------------------------------------------------------------------------------------*/
bool socket_create(iface_t *iface)
{
    __ASSERT(iface->port != 0, "Interface port cannot be zero");
    if (iface->link == IFACE_LINK_TYPE_CLIENT)
    {
        __ASSERT(iface->p_host != NULL, "Remote host cannot be NULL");
    }

    int *socket_ptr = (iface->link == IFACE_LINK_TYPE_CLIENT) ? &iface->client_socket : &iface->listening_socket;

    *socket_ptr = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (*socket_ptr < 0)
    {
        LOG_WRN("Socket creation failed: %s", strerror(errno));
        return false;
    }

    if (iface->link == IFACE_LINK_TYPE_SERVER)
    {
        struct sockaddr_in local_addr = {0};
        local_addr.sin_family = AF_INET;
        local_addr.sin_port = htons(iface->port);
        local_addr.sin_addr.s_addr = htonl(INADDR_ANY);  // Bind to all available interfaces

        if (bind(*socket_ptr, (struct sockaddr *)&local_addr, sizeof(local_addr)) < 0)
        {
            LOG_WRN("Socket bind failed: %s", strerror(errno));
            close(*socket_ptr);
            return false;
        }
    }

    return true;
}

bool socket_set_opt(iface_t *iface, iface_opt_t type, void *option, size_t option_size)
{
    __ASSERT(option, "Option pointer cannot be NULL");

    int ret = -1;
    int socket_to_set = (iface->link == IFACE_LINK_TYPE_CLIENT) ? iface->client_socket : iface->listening_socket;

    switch (type)
    {
        case IFACE_OPT_SEND_TIMEOUT:
        case IFACE_OPT_RECV_TIMEOUT:
        {
            __ASSERT(option_size == sizeof(uint16_t), "Option size mismatch for TIMEOUT options");

            struct timeval tv;
            tv.tv_sec = (*(uint16_t *)option) / 1000;
            tv.tv_usec = ((*(uint16_t *)option) % 1000) * 1000;
            int optname = (type == IFACE_OPT_SEND_TIMEOUT) ? SO_SNDTIMEO : SO_RCVTIMEO;

            ret = setsockopt(socket_to_set, SOL_SOCKET, optname, &tv, sizeof(tv));
            if (ret < 0)
            {
                LOG_WRN("Failed to set socket option: %s", strerror(errno));
                return false;
            }
        }
        break;
        default:
            LOG_WRN("Invalid option type %d provided", type);
            return false;
    }

    return true;
}

bool socket_connect(iface_t *iface, bool *timeout)
{
    __ASSERT(timeout, "Timeout pointer cannot be NULL");
    __ASSERT(iface->p_host, "Interface host cannot be NULL");
    __ASSERT(iface->port != 0, "Interface port cannot be zero");

    struct sockaddr_in remote_addr;
    remote_addr.sin_family = AF_INET;
    remote_addr.sin_port = htons(iface->port);
    inet_pton(AF_INET, iface->p_host, &remote_addr.sin_addr);  // Convert IP string to sockaddr_in format.

    if (connect(iface->client_socket, (struct sockaddr *)&remote_addr, sizeof(remote_addr)) < 0)
    {
        if (errno == EINPROGRESS || errno == EAGAIN || errno == EWOULDBLOCK || ETIMEDOUT)    // These indicate a timeout.
        {
            *timeout = true;
            return false;
        }
        LOG_WRN("Socket connect failed: %s", strerror(errno));
        return false;
    }

    *timeout = false;  // No timeout occurred.
    return true;
}

bool socket_accept(iface_t *iface, bool *timeout)
{
    __ASSERT(timeout, "Timeout pointer cannot be NULL");

    struct sockaddr_in client_addr;
    socklen_t addr_len = sizeof(client_addr);

    // Start listening on the listening_socket
    if (listen(iface->listening_socket, 1) < 0)
    {
        LOG_WRN("Socket listen failed: %s", strerror(errno));
        return false;
    }

    int client_socket = accept(iface->listening_socket, (struct sockaddr *)&client_addr, &addr_len);
    if (client_socket < 0)
    {
        if (errno == EAGAIN || errno == EWOULDBLOCK)    // These indicate a timeout.
        {
            *timeout = true;
            return false;
        }
        LOG_WRN("Socket accept failed: %s", strerror(errno));
        return false;
    }
    *timeout = false;  // No timeout occurred.

    iface->client_socket = client_socket;  // Update iface->client_socket with the new connected socket.
    return true;
}

bool socket_send(const iface_t *iface, const void *buffer, const size_t buffer_size,
                 uint16_t *send_count, bool *conn_closed, bool *timeout)
{
    __ASSERT(buffer, "Buffer pointer cannot be NULL");
    __ASSERT(send_count, "Send count pointer cannot be NULL");
    __ASSERT(conn_closed, "Connection closed pointer cannot be NULL");
    __ASSERT(timeout, "Timeout pointer cannot be NULL");

    int socket_send_count = send(iface->client_socket, buffer, buffer_size, 0);

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
        *timeout = false;  // Initialize to false

        if (errno == ECONNRESET || errno == EPIPE)
        {
            *conn_closed = true;
            LOG_DBG("Connection closed by remote peer on socket %d", iface->client_socket);
        }
        else if (errno == EAGAIN || errno == EWOULDBLOCK)
        {
            *timeout = true;
        }
        else
        {
            *conn_closed = false;
            LOG_WRN("Socket send error: %s", strerror(errno));
        }

        return false;
    }

    return true;
}

bool socket_recv(const iface_t *iface, void *buffer, const size_t buffer_size,
                 uint16_t *recv_count, bool *conn_closed, bool *timeout)
{
    __ASSERT(buffer, "Buffer pointer cannot be NULL");
    __ASSERT(recv_count, "Receive count pointer cannot be NULL");
    __ASSERT(conn_closed, "Connection closed pointer cannot be NULL");
    __ASSERT(timeout, "Timeout pointer cannot be NULL");

    int socket_recv_count = recv(iface->client_socket, buffer, buffer_size, 0);

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
        *conn_closed = true;  // Graceful shutdown by the peer.
        *timeout = false;
        LOG_DBG("Connection closed by remote peer on socket %d", iface->client_socket);

        return false;
    }
    else
    {
        *recv_count = 0;
        *timeout = false;  // Initialize to false

        if (errno == ECONNRESET)
        {
            *conn_closed = true;
            LOG_WRN("%s", "Connection reset by remote peer");
        }
        else if (errno == EAGAIN || errno == EWOULDBLOCK)
        {
            *timeout = true;
        }
        else
        {
            *conn_closed = false;
            LOG_WRN("Socket receive error: %s", strerror(errno));
        }

        return false;
    }
}

bool socket_close(const iface_t *iface)
{
    int result = close(iface->client_socket);
    if (result < 0)
    {
        LOG_WRN("Failed to close the socket: %s", strerror(errno));
        return false;
    }

    if (iface->link == IFACE_LINK_TYPE_SERVER)
    {
        result = close(iface->listening_socket);
        if (result < 0)
        {
            LOG_WRN("Failed to close the listening socket: %s", strerror(errno));
            return false;
        }
    }
    return true;
}
