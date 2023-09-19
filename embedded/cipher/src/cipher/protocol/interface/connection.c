#include "interface.h"

// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/logging/log.h>
#include <zephyr/kernel.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "tal.h"
#include "utils.h"
#include "cipher.h"

LOG_MODULE_DECLARE(cipher);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/

/**
 * What happens if an interface runs into an error?
 * If a client, do we just infinitaly keep attempting to connect?
 * If a server, do we just await on accept indefinitely?
 */

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

// Connect Helpers
static void await_connect(cipher_daemon_t *d, cipher_iface_t *iface);
static void await_disconnect(cipher_daemon_t *d, cipher_iface_t *iface);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Connection Thread
 *---------------------------------------------------------------------------------------------------*/
void cipher_interface_conn_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;
    cipher_iface_t *iface = (cipher_iface_t *)arg1;

    __ASSERT(d != NULL, "null daemon passed to thread");
    __ASSERT(iface != NULL, "null interface passed to thread");

    while (true)
    {
        await_connect(d, iface);
        // Signal send and recv threads to start
        await_disconnect(d, iface);
    }
}

static void await_connect(cipher_daemon_t *d, cipher_iface_t *iface)
{
    if (!tal_create(&iface->cfg))
        handle_interface_error(d, iface, IFACE_CREATE_FAILED);

    bool conn_timeout = false;
    switch (iface->cfg.link)
    {
    case TAL_LINK_TYPE_UPLINK:

        if (!tal_connect(&iface->cfg, &conn_timeout))
            if (!conn_timeout)
                handle_interface_error(d, iface, IFACE_CONNECT_FAILED);

        break;
    case TAL_LINK_TYPE_DOWNLINK:

        if (!tal_accept(&iface->cfg, &conn_timeout))
            if (!conn_timeout)
                handle_interface_error(d, iface, IFACE_CONNECT_FAILED);

        break;
    default:
        ERROR("Unknown iface link type: %d", iface->cfg.link);
    }

    DBG("Interface connected");
}

static void await_disconnect(cipher_daemon_t *d, cipher_iface_t *iface)
{

    if (!tal_close(&iface->cfg))
        handle_interface_error(d, iface, IFACE_CLOSE_FAILED);
}
