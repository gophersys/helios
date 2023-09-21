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
#include "interface.h"

LOG_MODULE_REGISTER(iface, IFACE_LOG_LEVEL);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/

// TODO: Somehow include these timeouts in the tal_cfg_t interface
#define TAL_CONNECT_TIMEOUT_MS 500 // Timeout in milliseconds for connection. Set to 0 for indefinite.
#define TAL_ACCEPT_TIMEOUT_MS 500  // Timeout in milliseconds for accept. Set to 0 for indefinite.
#define TAL_RETRY_DELAY_MS 0       // Delay between retry attempts.
#define IFACE_CLOSE_WAIT_TIME_MS 3000

// Timeouts
#define HANDSHAKE_TIMEOUT_MS 500
#define NORMAL_TIMEOUT_MS 3000

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

// Connection
static void await_connect(cipher_daemon_t *d, cipher_iface_t *iface);
static void get_connection(cipher_daemon_t *d, cipher_iface_t *iface);
static void do_handshake(cipher_daemon_t *d, cipher_iface_t *iface);
static void set_send_recv_timeouts(cipher_daemon_t *d, cipher_iface_t *iface, uint16_t send_t, uint16_t recv_t);

// Signaling
static void signal_send_recv(cipher_daemon_t *d, cipher_iface_t *iface);

// Disconnection
static void await_disconnect(cipher_daemon_t *d, cipher_iface_t *iface);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Connection Thread
 *---------------------------------------------------------------------------------------------------*/
void cipher_interface_conn_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;
    cipher_iface_t *iface = (cipher_iface_t *)arg1;

    __ASSERT(d != NULL, "Daemon struct pointer must not be NULL");
    __ASSERT(iface != NULL, "Interface pointer must not be NULL");

    k_sem_init(&iface->conn_sem, 0, 2);
    k_sem_init(&iface->disconn_sem, 0, 1);
    iface->connected = false;

    k_fifo_init(&iface->encoded_packets_queue);
    k_fifo_init(&iface->decoded_packets_queue);

    while (true)
    {
        await_connect(d, iface);
        signal_send_recv(d, iface);
        await_disconnect(d, iface);
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Await Connect
 *---------------------------------------------------------------------------------------------------*/
static void await_connect(cipher_daemon_t *d, cipher_iface_t *iface)
{
    get_connection(d, iface);
    set_send_recv_timeouts(d, iface, HANDSHAKE_TIMEOUT_MS, HANDSHAKE_TIMEOUT_MS);
    do_handshake(d, iface);
    set_send_recv_timeouts(d, iface, NORMAL_TIMEOUT_MS, NORMAL_TIMEOUT_MS);
}

static void get_connection(cipher_daemon_t *d, cipher_iface_t *iface)
{
    bool conn_timeout = false;

    if (!tal_create(iface->cfg))
        handle_interface_error(d, iface, IFACE_ERROR_CREATE);

    // Continuously try to establish the connection
    uint32_t start_time = k_uptime_get_32();
    while (!iface->connected) // TODO: Zephyr's sockets dont yet support a connect() timeout
    {
        switch (iface->cfg->link)
        {
        case TAL_LINK_TYPE_UPLINK:
            if (tal_connect(iface->cfg, &conn_timeout))
            {
                iface->connected = true;
            }
            else
            {
                if (!conn_timeout)
                    handle_interface_error(d, iface, IFACE_ERROR_SET_OPT);
            }
            break;

        case TAL_LINK_TYPE_DOWNLINK:
            if (tal_accept(iface->cfg, &conn_timeout))
            {
                iface->connected = true;
            }
            else
            {
                if (!conn_timeout)
                    handle_interface_error(d, iface, IFACE_ERROR_SET_OPT);

                /* You requested a timeout other than "always", halting app until
                 * you figure out your connections... or your life :) */
                ERROR("Accept timeout on interface %d, daemon %d", iface->id, d->id);
            }
            break;
        default:
            ERROR("Unknown iface link type: %d", iface->cfg->link);
        }

        // Add a small delay to avoid spamming connect/accept
        if (!iface->connected)
            k_msleep(50);
    }

    __ASSERT(iface->connected, "Logic error in function, must always be connected before returning");

    uint32_t connection_time = k_uptime_get_32() - start_time;
    // DBG("Daemon %d, iface %d connected (%u ms)", d->id, iface->id, connection_time);
}

static void set_send_recv_timeouts(cipher_daemon_t *d, cipher_iface_t *iface, uint16_t send_t, uint16_t recv_t)
{
    if (!tal_set_opt(iface->cfg, TAL_OPTION_SEND_TIMEOUT, &send_t, sizeof(send_t)))
        handle_interface_error(d, iface, IFACE_ERROR_SET_OPT);

    if (!tal_set_opt(iface->cfg, TAL_OPTION_RECV_TIMEOUT, &recv_t, sizeof(recv_t)))
        handle_interface_error(d, iface, IFACE_ERROR_SET_OPT);
}

static void do_handshake(cipher_daemon_t *d, cipher_iface_t *iface)
{
    if (!interface_handshake(d, iface))
        handle_interface_error(d, iface, IFACE_ERROR_HANDSHAKE);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                     Signal Send/Recv
 *---------------------------------------------------------------------------------------------------*/
static void signal_send_recv(cipher_daemon_t *d, cipher_iface_t *iface)
{
    // Signal send and recv threads to start
    k_sem_give(&iface->conn_sem);
    k_sem_give(&iface->conn_sem);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                     Await Disconnect
 *---------------------------------------------------------------------------------------------------*/
static void await_disconnect(cipher_daemon_t *d, cipher_iface_t *iface)
{
    k_sem_take(&iface->disconn_sem, K_FOREVER);

    DBG("Daemon %d, iface %d disconnected", d->id, iface->id);

    iface->connected = false;

    if (!tal_close(iface->cfg))
        handle_interface_error(d, iface, IFACE_ERROR_CLOSE);

    k_msleep(IFACE_CLOSE_WAIT_TIME_MS);

    // Reset the semaphore count to ensure it's 0
    while (k_sem_take(&iface->disconn_sem, K_NO_WAIT) == 0)
        k_yield();
}
