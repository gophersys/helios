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
LOG_MODULE_REGISTER(protocol);

#define CIPHER_PROTOCOL_VERSION 1

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

// Init
bool cipher_interface_init(tal_config_t *cfg);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Main Event Loop
 *---------------------------------------------------------------------------------------------------*/
void init_cipher(void)
{
    DBG("Starting Cipher");

    tal_config_t uplink_cfg = {
        .interface = TAL_INTERFACE_TYPE_SOCKET,
        .link = TAL_LINK_TYPE_UPLINK,
        .host = "192.168.0.11",
        .port = 6969,
    };

    cipher_interface_init(&uplink_cfg);

    while (1)
    {
        k_msleep(1000);
        LOG("In busy loop");
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                      Private Function Implementation
 *---------------------------------------------------------------------------------------------------*/

bool cipher_interface_init(tal_config_t *cfg)
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
                DBG("Uplink interface initialized OK");
                status = true;
            }
        }
    }
    break;

    case TAL_LINK_TYPE_DOWNLINK:
        // TODO: Implement me
        break;
    default:
        LOG_ERR("%s: unhandled exception", __func__);
    }

    return status;
}
