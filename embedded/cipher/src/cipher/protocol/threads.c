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
LOG_MODULE_DECLARE(protocol, LOG_LEVEL_DBG);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

// Listener thread
#define LISTENER_THREAD_PRIORITY 5
#define LISTENER_THREAD_STACK_SIZE 500
K_THREAD_STACK_DEFINE(listener_thread_stack_area, LISTENER_THREAD_STACK_SIZE);
struct k_thread listener_thread_data;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/
static void cipher_listener_thread(void *arg0, void *arg1, void *arg2);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/
bool cipher_threads_init(cipher_daemon_t *daemon)
{
    bool status = false;

    daemon->listener_thread_id = k_thread_create(&listener_thread_data,
                                                 listener_thread_stack_area,
                                                 K_THREAD_STACK_SIZEOF(listener_thread_stack_area),
                                                 cipher_listener_thread,
                                                 NULL, NULL, NULL,
                                                 5,
                                                 0,
                                                 K_NO_WAIT);

    return status;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                      Private Function Implementation
 *---------------------------------------------------------------------------------------------------*/

static void cipher_listener_thread(void *arg0, void *arg1, void *arg2)
{
    while (1)
    {
        LOG("Listener thread is running\n");
        k_msleep(500);
    }
}