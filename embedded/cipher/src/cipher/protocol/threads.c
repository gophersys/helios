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
LOG_MODULE_REGISTER(threads, LOG_LEVEL_DBG);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

#define CONTROLLER_THREAD_PRIORITY 14
#define CONTROLLER_THREAD_STACK_SIZE 1024
K_THREAD_STACK_DEFINE(controller_thread_stack, CONTROLLER_THREAD_STACK_SIZE);
struct k_thread controller_thread_data;

#define LISTENER_THREAD_PRIORITY 14
#define LISTENER_THREAD_STACK_SIZE 1024
K_THREAD_STACK_DEFINE(listener_thread_stack, LISTENER_THREAD_STACK_SIZE);
struct k_thread listener_thread_data;
// static struct k_thread *listener_thread_data;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                          Work Queues
 *---------------------------------------------------------------------------------------------------*/

typedef enum
{
    CONTROLLER_EVENT_TYPE_EXIT,

    CONTROLLER_EVENT_TYPE_MAX,
} controller_event_type_t;

typedef struct
{
    controller_event_type_t type;
} controller_event_t;

struct k_fifo controller_event_queue;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

static void cipher_controller_thread(void *arg0, void *arg1, void *arg2);
static void cipher_listener_thread(void *arg0, void *arg1, void *arg2);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/

bool cipher_threads_init(cipher_daemon_t *daemon)
{
    bool status = false;

    k_fifo_init(&controller_event_queue);

    daemon->controller_tid = k_thread_create(&controller_thread_data,
                                             controller_thread_stack,
                                             K_THREAD_STACK_SIZEOF(controller_thread_stack),
                                             cipher_controller_thread,
                                             (void *)daemon, NULL, NULL,
                                             CONTROLLER_THREAD_PRIORITY,
                                             0,
                                             K_FOREVER);

    daemon->uplink_listener_tid = k_thread_create(&listener_thread_data,
                                                  listener_thread_stack,
                                                  K_THREAD_STACK_SIZEOF(listener_thread_stack),
                                                  cipher_listener_thread,
                                                  (void *)&daemon->uplink_cfg, NULL, NULL,
                                                  LISTENER_THREAD_PRIORITY,
                                                  0,
                                                  K_FOREVER);

    k_thread_start(daemon->controller_tid);
    k_thread_start(daemon->uplink_listener_tid);

    // TODO: how do we verify all threads were initialized ok?
    status = true;

    k_msleep(100000);

    return status;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Listener Thread
 *---------------------------------------------------------------------------------------------------*/

static void cipher_listener_thread(void *arg0, void *arg1, void *arg2)
{
    tal_config_t *interface_cfg = (tal_config_t *)arg0;

    while (1)
    {
        const size_t buffer_size = CIPHER_CONFIG_MAX_PAYLOAD_SIZE;
        uint8_t *recv_buffer = cipher_new_buffer(buffer_size);
        uint16_t bytes_recv = 0;
        bool conn_closed = false;

        if (!tal_recv(interface_cfg, recv_buffer, buffer_size, &bytes_recv, &conn_closed))
        {
            if (!conn_closed)
            {
                WARN("Could not recv on interface");
            }
            else
            {
                WARN("Remote connection closed");

                controller_event_t exit_event = {
                    .type = CONTROLLER_EVENT_TYPE_EXIT,
                };
                k_fifo_put(&controller_event_queue, &exit_event);
                // k_thread_suspend(k_current_get());
                k_msleep(100000);
            }
        }
        else
        {
            if (bytes_recv < sizeof(cipher_packet_header_t))
            {
                WARN("Incomplete payload");
            }
            else
            {
                cipher_packet_header_t header = {0};
                if (!cipher_packet_parse_header(recv_buffer, bytes_recv, &header))
                {
                    WARN("Unable to parse cipher header");
                }
                else
                {
                    // cipher_print_header(&header);

                    if (header.payload_len == bytes_recv - sizeof(header))
                    {
                        // TODO: me
                    }
                    else
                    {
                    }

                    // TODO: If payload is complete, dispatch to the right receiver
                }
            }
        }

        cipher_free_buffer(recv_buffer);
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Controller Thread
 *---------------------------------------------------------------------------------------------------*/

static void cipher_controller_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *daemon = (cipher_daemon_t *)arg0;

    while (true)
    {
        controller_event_t *event = k_fifo_get(&controller_event_queue, K_FOREVER);

        switch (event->type)
        {
        case CONTROLLER_EVENT_TYPE_EXIT:

            DBG("Ending dameon instance...");

            k_thread_abort(daemon->uplink_listener_tid);

            tal_close(&daemon->uplink_cfg);

            DBG("Exiting");
            k_thread_abort(k_current_get());

            break;

        default:
            ERROR("Unknown controller event type: %d", event->type);
        }
    }
}