// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/logging/log.h>
#include <zephyr/kernel.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "utils/err.h"

// Private include
#include "threads.h"
#include "controller.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/
LOG_MODULE_DECLARE(daemon);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/

bool cipher_controller_exit(cipher_daemon_t *daemon)
{
    bool status = false;
    controller_event_t exit_event = {
        .type = CONTROLLER_EVENT_TYPE_EXIT,
    };
    k_fifo_alloc_put(&daemon->controller_event_queue, &exit_event);

    // TODO: me
    status = true;
    return status;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Thread
 *---------------------------------------------------------------------------------------------------*/

void cipher_controller_thread(void *arg0, void *arg1, void *arg2)
{
    LOG("Starting cipher controller thread");
    while (true)
        k_msleep(1000);
    cipher_daemon_t *daemon = (cipher_daemon_t *)arg0;

    while (true)
    {
        controller_event_t *event = k_fifo_get(&daemon->controller_event_queue, K_FOREVER);

        switch (event->type)
        {
        case CONTROLLER_EVENT_TYPE_EXIT:

            DBG("Ending dameon instance...");

            k_thread_abort(daemon->sd_t_id);
            // k_thread_abort(daemon->);
            k_thread_abort(daemon->router_t_id);

            // tal_close(&daemon->uplink_cfg);

            DBG("Exiting");

            k_thread_abort(k_current_get());

            break;

        default:
            ERROR("Unknown controller event type: %d", event->type);
        }
    }
}