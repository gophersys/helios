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
static void process_egress_packet(cipher_daemon_t *d, uint8_t *send_buffer, uint16_t send_bytes);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                          Send Thread
 *---------------------------------------------------------------------------------------------------*/
void cipher_interface_send_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;
    cipher_iface_t *iface = (cipher_iface_t *)arg1;

    __ASSERT(d != NULL, "null daemon passed to thread");
    __ASSERT(iface != NULL, "null interface passed to thread");

    LOG("Starting iface send thread");
    while (true)
        k_msleep(1000);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Egress
 *---------------------------------------------------------------------------------------------------*/
static void process_egress_packet(cipher_daemon_t *d, uint8_t *send_buffer, uint16_t send_bytes)
{
}
