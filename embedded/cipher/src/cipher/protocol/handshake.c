#include "cipher.h"

// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/logging/log.h>
#include <zephyr/kernel.h>
#include <zephyr/net/socket.h>

// Private includes
#include "tal.h"
#include "utils.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/
LOG_MODULE_DECLARE(protocol);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

// TODO: How do I add unit tests to these functions?
static bool handshake_uplink(const tal_config_t *cfg);
static bool handshake_downlink(const tal_config_t *cfg);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/
bool cipher_handshake(const tal_config_t *cfg)
{
    bool status = false;

    switch (cfg->link)
    {
    case TAL_LINK_TYPE_UPLINK:
        status = handshake_uplink(cfg);
        break;
    case TAL_LINK_TYPE_DOWNLINK:
        status = handshake_downlink(cfg);
        break;
    default:
        ERROR("Unknown or implemented link type: %d", cfg->link);
    }

    return status;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                      Private Function Implementation
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
static bool handshake_uplink(const tal_config_t *cfg)
{
    bool status = false;

    DBG("Handshaking downlink node");

    uint8_t recv_buffer[sizeof(bool)] = {0};
    uint16_t bytes_recv = 0;
    uint16_t bytes_sent = 0;
    bool conn_closed = false;

    uint16_t local_node_version = htons(CIPHER_PROTOCOL_VERSION);
    if (!tal_send(cfg, &local_node_version, sizeof(local_node_version), &bytes_sent, &conn_closed))
        if (!conn_closed)
            WARN("Could not send on interface");

    if (bytes_sent != sizeof(local_node_version))
    {
        WARN("Expected to send %d bytes but only sent %d", sizeof(local_node_version), bytes_sent);
    }
    else
    {
        if (!tal_recv(cfg, recv_buffer, sizeof(recv_buffer), &bytes_recv, &conn_closed))
            if (!conn_closed)
                WARN("Could not recv on interface");

        if (bytes_recv == sizeof(bool) && !conn_closed)
        {
            bool supported = recv_buffer[0];
            if (supported)
                status = true;
            else
                WARN("Local node protocol version %d does not match remote", CIPHER_PROTOCOL_VERSION);
        }
        else
        {
            WARN("Connection timeout while sending protocol version");
        }
    }

    return status;
}

/**
 * Handshaking a downlink connection involves a server (us) awaiting a protocol version from the remote
 * node, which acts as a client. If our protocol version matches, then a boolean is sent to the remote
 * node indicating the connection status
 *
 * @param cfg Transport layer config
 * @return true If the remote node's protocol version matches
 * @return false If a version mismatch, or send/recv errors
 */
static bool handshake_downlink(const tal_config_t *cfg)
{
    bool status = false;

    DBG("Handshaking downlink node");

    uint8_t recv_buffer[sizeof(uint16_t)] = {0};
    uint16_t bytes_recv = 0;
    uint16_t bytes_sent = 0;
    bool conn_closed = false;

    if (!tal_recv(cfg, recv_buffer, sizeof(recv_buffer), &bytes_recv, &conn_closed))
        if (!conn_closed)
            WARN("Could not recv on interface");

    bool valid_packet = false;
    if (bytes_recv == sizeof(uint16_t) && !conn_closed)
        valid_packet = true;
    else
        WARN("Connection timeout while awaiting protocol version");

    if (valid_packet)
    {
        uint16_t rmt_node_version = ntohs(*(uint16_t *)recv_buffer);

        bool supported = false;
        if (rmt_node_version == CIPHER_PROTOCOL_VERSION)
        {
            supported = true;
            if (!tal_send(cfg, &supported, sizeof(supported), &bytes_sent, &conn_closed))
                if (!conn_closed)
                    WARN("Could not send on interface");
        }

        if (supported && !conn_closed)
            status = true;
        else
            WARN("Remote node attempted to connect with protocol version %d, expected %d", rmt_node_version, CIPHER_PROTOCOL_VERSION);
    }

    return status;
}