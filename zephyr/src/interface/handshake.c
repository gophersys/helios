// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include <corekinect/iface/iface.h>
#include "utils/err.h"

// Private include
#include "interface.h"
#include "threads.h"

LOG_MODULE_DECLARE(iface);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/
static bool handshake_uplink(cipher_daemon_t *d, iface_t *iface);
static bool handshake_downlink(cipher_daemon_t *d, iface_t *iface);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/
bool interface_handshake(cipher_daemon_t *d, cipher_iface_t *iface) {
    bool status = false;

    switch (iface->cfg->link) {
        case IFACE_LINK_TYPE_CLIENT:
            status = handshake_uplink(d, iface->cfg);
            break;
        case IFACE_LINK_TYPE_SERVER:
            status = handshake_downlink(d, iface->cfg);
            break;
        default:
            ERROR("Unknown or implemented link type: %d", iface->cfg->link);
    }

    return status;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Uplink
 *---------------------------------------------------------------------------------------------------*/

/**
 * Handshaking an uplink connection involves a client (us) sending our protocol version to the remote
 * node, which acts as a server. The server will respond back with a boolean indicating a the connection
 * status
 *
 * @param cfg Transport layer config
 * @return true If the remote node's protocol version matches
 * @return false If a version mismatch, or send/recv errors
 */
static bool handshake_uplink(cipher_daemon_t *d, iface_t *cfg) {
    LOG("Handshaking uplink node");

    uint16_t bytes_sent = 0;
    bool conn_closed = false;
    bool timeout = false;

    uint16_t local_node_version = htons(CIPHER_CONFIG_PROTOCOL_VERSION);
    if (!iface_send(cfg, &local_node_version, sizeof(local_node_version), &bytes_sent, &conn_closed, &timeout)) {
        if (timeout)
            WARN("Timeout trying to send protocol version to server");
        else if (conn_closed)
            WARN("Connection closed trying to send protocol version to server");
        else
            WARN("Interface send error");

        return false;
    }

    if (bytes_sent != sizeof(local_node_version)) {
        WARN("Expected to send %d bytes but sent %d", sizeof(local_node_version), bytes_sent);
        return false;
    }

    uint16_t bytes_recv = 0;
    const size_t recv_buffer_size = CONFIG_MAX_PAYLOAD_SIZE;
    uint8_t *recv_buffer = k_heap_alloc(&d->net_buffers_heap, recv_buffer_size, K_FOREVER);
    CHECK_MALLOC(recv_buffer);

    if (!iface_recv(cfg, recv_buffer, recv_buffer_size, &bytes_recv, &conn_closed, &timeout)) {
        if (timeout)
            WARN("Timeout trying to recv server response");
        else if (conn_closed)
            WARN("Connection closed trying to recv server response");
        else
            WARN("Interface recv error");

        k_heap_free(&d->net_buffers_heap, recv_buffer);
        return false;
    }

    if (bytes_recv != sizeof(bool)) {
        WARN("Expected to recv %d bytes but recv %d", sizeof(bool), bytes_recv);

        k_heap_free(&d->net_buffers_heap, recv_buffer);
        return false;
    }

    bool supported = recv_buffer[0];
    k_heap_free(&d->net_buffers_heap, recv_buffer);

    if (!supported) {
        WARN("Local node protocol version %d does not match server's", CIPHER_CONFIG_PROTOCOL_VERSION);
        return false;
    }

    LOG("Uplink handshake succesful");
    return true;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Downlink
 *---------------------------------------------------------------------------------------------------*/
/**
 * Handshaking a downlink connection involves a server (us) awaiting a protocol version from the remote
 * node, which acts as a client. If our protocol version matches, then a boolean is sent to the remote
 * node indicating the connection status
 *
 * @param cfg Transport layer config
 * @return true If the remote node's protocol version matches
 * @return false If a version mismatch, or send/recv errors
 */
static bool handshake_downlink(cipher_daemon_t *d, iface_t *cfg) {
    LOG("Handshaking downlink node");

    uint16_t bytes_recv = 0;
    uint16_t bytes_sent = 0;
    bool conn_closed = false;
    bool timeout = false;
    const size_t recv_buffer_size = CONFIG_MAX_PAYLOAD_SIZE;
    uint8_t *recv_buffer = k_heap_alloc(&d->net_buffers_heap, recv_buffer_size, K_FOREVER);
    CHECK_MALLOC(recv_buffer);

    if (!iface_recv(cfg, recv_buffer, recv_buffer_size, &bytes_recv, &conn_closed, &timeout)) {
        if (timeout)
            WARN("Timeout trying to recv client protocol version");
        else if (conn_closed)
            WARN("Connection closed trying to recv client protocol version");
        else
            WARN("Interface recv error");

        k_heap_free(&d->net_buffers_heap, recv_buffer);
        return false;
    }

    if (bytes_recv != sizeof(uint16_t)) {
        WARN("Expected to recv %d bytes but recv %d", sizeof(uint16_t), bytes_recv);

        k_heap_free(&d->net_buffers_heap, recv_buffer);
        return false;
    }

    uint16_t rmt_node_version = ntohs(*(uint16_t *)recv_buffer);
    k_heap_free(&d->net_buffers_heap, recv_buffer);

    bool supported = (rmt_node_version == CIPHER_CONFIG_PROTOCOL_VERSION) ? true : false;

    if (!iface_send(cfg, &supported, sizeof(supported), &bytes_sent, &conn_closed, &timeout)) {
        if (timeout)
            WARN("Timeout trying to send response %d to client", supported);
        else if (conn_closed)
            WARN("Connection closed trying to send response %d to client", supported);
        else
            WARN("Interface send error");

        return false;
    }

    if (bytes_sent != sizeof(supported)) {
        WARN("Expected to send %d bytes but sent %d", sizeof(supported), bytes_sent);
        return false;
    }

    if (!supported) {
        WARN("Remote node attempted to connect with protocol version %d, expected %d", rmt_node_version, CIPHER_CONFIG_PROTOCOL_VERSION);
        return false;
    }

    LOG("Downlink handshake succesful");
    return true;
}