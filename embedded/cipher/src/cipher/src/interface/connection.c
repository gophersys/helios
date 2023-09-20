#include "interface_prv.h"

// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/logging/log.h>
#include <zephyr/kernel.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "config/default.h"
#include "transport/transport.h"
#include "daemon/daemon.h"
#include "utils/err.h"

// Private include
#include "threads.h"

LOG_MODULE_REGISTER(transport);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/

/**
 * What happens if an interface runs into an error?
 * If a client, do we just infinitaly keep attempting to connect?
 * If a server, do we just await on accept indefinitely?
 */

// Configuration Macros
#define TAL_CONNECT_TIMEOUT_MS 0 // Timeout in milliseconds for connection. Set to 0 for indefinite.
#define TAL_ACCEPT_TIMEOUT_MS 0  // Timeout in milliseconds for accept. Set to 0 for indefinite.
#define TAL_RETRY_DELAY_MS 0     // Delay between retry attempts.

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

// Connection
static void await_connect(cipher_daemon_t *d, cipher_iface_t *iface);
static void setup_timeouts(cipher_daemon_t *d, cipher_iface_t *iface);
static void get_connection(cipher_daemon_t *d, cipher_iface_t *iface);
static void do_handshake(cipher_daemon_t *d, cipher_iface_t *iface);

// Disconnection
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

    k_sem_init(&iface->_conn_sem, 0, 1);
    k_sem_init(&iface->_disconn_sem, 0, 1);
    iface->_connected = false;

    while (true)
    {
        await_connect(d, iface);
        k_sem_give(&iface->_conn_sem); // Signal send and recv threads to start
        await_disconnect(d, iface);
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Await Connect
 *---------------------------------------------------------------------------------------------------*/
static void await_connect(cipher_daemon_t *d, cipher_iface_t *iface)
{
    // Usually the interfaces would just wait "forever", but in case not
    setup_timeouts(d, iface);

    // Do connect() or accept() depending on config type
    get_connection(d, iface);

    // Exchange protocol versions
    do_handshake(d, iface);
}

static void setup_timeouts(cipher_daemon_t *d, cipher_iface_t *iface)
{
    // Set the timeout for the specific operation
    uint16_t timeout_opt = 0;
    switch (iface->cfg.link)
    {
    case TAL_LINK_TYPE_UPLINK:

        timeout_opt = TAL_CONNECT_TIMEOUT_MS;
        if (!tal_set_opt(&iface->cfg, TAL_OPTION_SEND_TIMEOUT, &timeout_opt, sizeof(timeout_opt)))
            handle_interface_error(d, iface, IFACE_ERROR_SET_OPT);
        break;

    case TAL_LINK_TYPE_DOWNLINK:

        timeout_opt = TAL_ACCEPT_TIMEOUT_MS;
        if (!tal_set_opt(&iface->cfg, TAL_OPTION_RECV_TIMEOUT, &timeout_opt, sizeof(timeout_opt)))
            handle_interface_error(d, iface, IFACE_ERROR_SET_OPT);

        break;
    default:
        ERROR("Unknown iface link type: %d", iface->cfg.link);
    }
}

static void get_connection(cipher_daemon_t *d, cipher_iface_t *iface)
{
    bool conn_timeout = false;

    if (!tal_create(&iface->cfg))
        handle_interface_error(d, iface, IFACE_ERROR_CREATE);

    // Continuously try to establish the connection
    uint32_t start_time = k_uptime_get_32();
    while (!iface->_connected)
    {
        switch (iface->cfg.link)
        {
        case TAL_LINK_TYPE_UPLINK:
            if (tal_connect(&iface->cfg, &conn_timeout))
            {
                iface->_connected = true;
            }
            else
            {
                if (!conn_timeout)
                    handle_interface_error(d, iface, IFACE_ERROR_SET_OPT);

                /* You requested a timeout other than "always", halting app until
                 * you figure out your connections... or your life :) */
                ERROR("Connect timeout on interface %d, daemon %d", iface->_id, d->_id);
            }
            break;

        case TAL_LINK_TYPE_DOWNLINK:
            if (tal_accept(&iface->cfg, &conn_timeout))
            {
                iface->_connected = true;
            }
            else
            {
                if (!conn_timeout)
                    handle_interface_error(d, iface, IFACE_ERROR_SET_OPT);

                /* You requested a timeout other than "always", halting app until
                 * you figure out your connections... or your life :) */
                ERROR("Accept timeout on interface %d, daemon %d", iface->_id, d->_id);
            }
            break;
        default:
            ERROR("Unknown iface link type: %d", iface->cfg.link);
        }

        // Add a small delay to avoid spamming connect/accept
        if (!iface->_connected)
            k_msleep(50);
    }

    __ASSERT(iface->_connected, "Logic error in function, must always be connected before returning");

    DBG("Daemon %d, iface %d connected (%ldms)", d->_id, iface->_id, k_uptime_get_32() - start_time);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                            Handshake
 *---------------------------------------------------------------------------------------------------*/
static void do_handshake(cipher_daemon_t *d, cipher_iface_t *iface)
{
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                     Await Disconnect
 *---------------------------------------------------------------------------------------------------*/
static void await_disconnect(cipher_daemon_t *d, cipher_iface_t *iface)
{
    k_sem_take(&iface->_disconn_sem, K_FOREVER);

    iface->_connected = false;

    if (!tal_close(&iface->cfg))
        handle_interface_error(d, iface, IFACE_ERROR_CLOSE);

    // Reset the semaphore count to ensure it's 0
    while (k_sem_take(&iface->_disconn_sem, K_NO_WAIT) == 0)
        k_yield();
}
