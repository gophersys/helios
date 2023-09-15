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
LOG_MODULE_REGISTER(protocol, LOG_LEVEL_DBG);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

static bool cipher_interface_init(tal_config_t *cfg);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Main Event Loop
 *---------------------------------------------------------------------------------------------------*/
void init_cipher(cipher_daemon_t *daemon)
{
    LOG("Starting Cipher");

    tal_config_t uplink_cfg = {
        .interface = TAL_INTERFACE_TYPE_SOCKET,
        .link = TAL_LINK_TYPE_UPLINK,
        .host = "192.168.0.11",
        .port = 6969,
    };

    if (!cipher_interface_init(&uplink_cfg))
        ERROR("Could not initialize uplink interface");

    if (!cipher_threads_init(daemon))
        ERROR("Could not protocol threads");

    while (1)
    {
        k_msleep(1000);
        LOG("In busy loop");
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                 Init
 *---------------------------------------------------------------------------------------------------*/

static bool cipher_interface_init(tal_config_t *cfg)
{
    bool status = false;

    switch (cfg->link)
    {
    case TAL_LINK_TYPE_UPLINK:
    {
        if (!tal_connect(cfg))
        {
            WARN("Could not connect cipher link");
        }
        else
        {
            if (!cipher_handshake(cfg))
            {
                WARN("Could not handshake link");
            }
            else
            {
                LOG("Uplink interface initialized OK");
                status = true;
            }
        }
    }
    break;

    case TAL_LINK_TYPE_DOWNLINK:
        // TODO: Implement me
        break;
    default:
        ERROR("Unhandled exception");
    }

    return status;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Threads
 *---------------------------------------------------------------------------------------------------*/
