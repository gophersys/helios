#include "socket.h"

#include <corekinect/iface/iface.h>

// Standard includes
#include <errno.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/net_ip.h>
#include <zephyr/net/socket.h>

LOG_MODULE_DECLARE(iface);

// Optional packet-analyzer hooks (no-ops when the analyzer is absent/disabled)
#ifdef CONFIG_CK_PKT_ANALYZER
#include <corekinect/analyzer/analyzer.h>
#else
#define CK_ANA_IFACE_EVT(event, detail) ((void)0)
#define CK_ANA_IFACE_BYTES(dir, count)  ((void)0)
#define CK_ANA_DIR_TX 0
#define CK_ANA_DIR_RX 1
#endif

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/

/**
 * We don't check for NULL interfaces in any function, since caller guarantees to not call us without a
 * valid interface pointer.
 *
 * This file uses the zsock_* socket API (and net_htons) rather than the bare BSD
 * names: NET_SOCKETS_POSIX_NAMES was removed in Zephyr 4.x, and a library should
 * not force CONFIG_POSIX_API onto its consumers.
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

    // Mark the not-yet-used fd invalid so close() can tell it apart from a real
    // fd (Zephyr fds start at 0, so a zero-initialized struct is ambiguous).
    if (iface->link == IFACE_LINK_TYPE_CLIENT)
    {
        iface->listening_socket = -1;
    }
    else
    {
        iface->client_socket = -1;  // Set by accept() later
    }

    *socket_ptr = zsock_socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (*socket_ptr < 0)
    {
        LOG_WRN("Socket creation failed: %s", strerror(errno));
        return false;
    }

    if (iface->link == IFACE_LINK_TYPE_SERVER)
    {
        // Allow fast rebinds after a close/restart; otherwise the kernel holds the
        // port in TIME_WAIT and bind() fails with EADDRINUSE.
        int reuse = 1;
        if (zsock_setsockopt(*socket_ptr, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse)) < 0)
        {
            LOG_WRN("SO_REUSEADDR failed (continuing): %s", strerror(errno));
        }

        struct sockaddr_in local_addr = {0};
        local_addr.sin_family = AF_INET;
        local_addr.sin_port = net_htons(iface->port);
        local_addr.sin_addr.s_addr = INADDR_ANY;  // Bind to all available interfaces

        if (zsock_bind(*socket_ptr, (struct sockaddr *)&local_addr, sizeof(local_addr)) < 0)
        {
            LOG_WRN("Socket bind failed: %s", strerror(errno));
            zsock_close(*socket_ptr);
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

            struct zsock_timeval tv;
            tv.tv_sec = (*(uint16_t *)option) / 1000;
            tv.tv_usec = ((*(uint16_t *)option) % 1000) * 1000;
            int optname = (type == IFACE_OPT_SEND_TIMEOUT) ? SO_SNDTIMEO : SO_RCVTIMEO;

            ret = zsock_setsockopt(socket_to_set, SOL_SOCKET, optname, &tv, sizeof(tv));
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

    struct sockaddr_in remote_addr = {0};
    remote_addr.sin_family = AF_INET;
    remote_addr.sin_port = net_htons(iface->port);

    // Fast path: p_host is a numeric IPv4 literal. Otherwise resolve it as a
    // hostname via DNS (requires CONFIG_DNS_RESOLVER in the application; .local
    // names additionally need CONFIG_MDNS_RESOLVER).
    if (zsock_inet_pton(AF_INET, iface->p_host, &remote_addr.sin_addr) != 1)
    {
        struct zsock_addrinfo hints = {
            .ai_family = AF_INET,
            .ai_socktype = SOCK_STREAM,
        };
        struct zsock_addrinfo *p_res = NULL;

        int err = zsock_getaddrinfo(iface->p_host, NULL, &hints, &p_res);
        if (err != 0 || p_res == NULL)
        {
            LOG_WRN("DNS resolution failed for '%s': err %d", iface->p_host, err);
            return false;
        }

        remote_addr.sin_addr = ((struct sockaddr_in *)p_res->ai_addr)->sin_addr;
        zsock_freeaddrinfo(p_res);
    }

    if (zsock_connect(iface->client_socket, (struct sockaddr *)&remote_addr, sizeof(remote_addr)) < 0)
    {
        if (errno == EINPROGRESS || errno == EAGAIN || errno == EWOULDBLOCK || errno == ETIMEDOUT)    // These indicate a timeout.
        {
            *timeout = true;
            return false;
        }
        LOG_WRN("Socket connect failed: %s", strerror(errno));
        return false;
    }

    *timeout = false;  // No timeout occurred.
    CK_ANA_IFACE_EVT("connect", iface->client_socket);
    return true;
}

bool socket_accept(iface_t *iface, bool *timeout)
{
    __ASSERT(timeout, "Timeout pointer cannot be NULL");

    struct sockaddr_in client_addr;
    socklen_t addr_len = sizeof(client_addr);

    // Start listening on the listening_socket
    if (zsock_listen(iface->listening_socket, 1) < 0)
    {
        LOG_WRN("Socket listen failed: %s", strerror(errno));
        return false;
    }

    int client_socket = zsock_accept(iface->listening_socket, (struct sockaddr *)&client_addr, &addr_len);
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
    CK_ANA_IFACE_EVT("accept", client_socket);
    return true;
}

bool socket_send(const iface_t *iface, const void *buffer, const size_t buffer_size,
                 uint16_t *send_count, bool *conn_closed, bool *timeout)
{
    __ASSERT(buffer, "Buffer pointer cannot be NULL");
    __ASSERT(send_count, "Send count pointer cannot be NULL");
    __ASSERT(conn_closed, "Connection closed pointer cannot be NULL");
    __ASSERT(timeout, "Timeout pointer cannot be NULL");

    int socket_send_count = zsock_send(iface->client_socket, buffer, buffer_size, 0);

    if (socket_send_count > 0)
    {
        CK_ANA_IFACE_BYTES(CK_ANA_DIR_TX, (size_t)socket_send_count);
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
}

bool socket_recv(const iface_t *iface, void *buffer, const size_t buffer_size,
                 uint16_t *recv_count, bool *conn_closed, bool *timeout)
{
    __ASSERT(buffer, "Buffer pointer cannot be NULL");
    __ASSERT(recv_count, "Receive count pointer cannot be NULL");
    __ASSERT(conn_closed, "Connection closed pointer cannot be NULL");
    __ASSERT(timeout, "Timeout pointer cannot be NULL");

    int socket_recv_count = zsock_recv(iface->client_socket, buffer, buffer_size, 0);

    if (socket_recv_count > 0)
    {
        CK_ANA_IFACE_BYTES(CK_ANA_DIR_RX, (size_t)socket_recv_count);
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
    bool ok = true;

    CK_ANA_IFACE_EVT("close", iface->client_socket);

    // client_socket is -1 on a server that never accept()ed — skip it.
    if (iface->client_socket >= 0 && zsock_close(iface->client_socket) < 0)
    {
        LOG_WRN("Failed to close the socket: %s", strerror(errno));
        ok = false;
    }

    if (iface->link == IFACE_LINK_TYPE_SERVER &&
        iface->listening_socket >= 0 && zsock_close(iface->listening_socket) < 0)
    {
        LOG_WRN("Failed to close the listening socket: %s", strerror(errno));
        ok = false;
    }

    return ok;
}
