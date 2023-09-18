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

K_HEAP_DEFINE(recv_buffers_heap, CONFIG_CIPHER_RECV_BUFFER_SIZE *CONFIG_CIPHER_RECV_BUFFERS);
K_HEAP_DEFINE(unrouted_packets_heap, 2048);
K_HEAP_DEFINE(local_packets_heap, 2048);

#define CONTROLLER_THREAD_PRIORITY 100
#define CONTROLLER_THREAD_STACK_SIZE 1024
K_THREAD_STACK_DEFINE(controller_thread_stack, CONTROLLER_THREAD_STACK_SIZE);
struct k_thread controller_thread_data;

#define LISTENER_THREAD_PRIORITY 100
#define LISTENER_THREAD_STACK_SIZE 1024
K_THREAD_STACK_DEFINE(listener_thread_stack, LISTENER_THREAD_STACK_SIZE);
struct k_thread listener_thread_data;

#define SD_THREAD_PRIORITY 100
#define SD_THREAD_STACK_SIZE 1024
K_THREAD_STACK_DEFINE(sd_thread_stack, SD_THREAD_STACK_SIZE);
struct k_thread sd_thread_data;

#define ROUTER_THREAD_PRIORITY 100
#define ROUTER_THREAD_STACK_SIZE 1024
K_THREAD_STACK_DEFINE(router_thread_stack, ROUTER_THREAD_STACK_SIZE);
struct k_thread router_thread_data;

#define RPC_THREAD_PRIORITY 100
#define RPC_THREAD_STACK_SIZE 1024
K_THREAD_STACK_DEFINE(rpc_thread_stack, RPC_THREAD_STACK_SIZE);
struct k_thread rpc_thread_data;

#define EVENT_THREAD_PRIORITY 100
#define EVENT_THREAD_STACK_SIZE 1024
K_THREAD_STACK_DEFINE(event_thread_stack, EVENT_THREAD_STACK_SIZE);
struct k_thread event_thread_data;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                          Work Queues
 *---------------------------------------------------------------------------------------------------*/

// Controller
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

// Service Discovery
struct k_fifo service_discovery_queue;

// Routing
struct k_fifo unrouted_packets_queue;

// RPC
struct k_fifo rpc_queue;

// Events
struct k_fifo event_queue;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

static void cipher_controller_thread(void *arg0, void *arg1, void *arg2);
static void cipher_listener_thread(void *arg0, void *arg1, void *arg2);
static void cipher_sd_thread(void *arg0, void *arg1, void *arg2);
static void cipher_router_thread(void *arg0, void *arg1, void *arg2);
static void cipher_rpc_thread(void *arg0, void *arg1, void *arg2);
static void cipher_event_thread(void *arg0, void *arg1, void *arg2);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/

bool cipher_threads_init(cipher_daemon_t *daemon)
{
    k_fifo_init(&controller_event_queue);
    k_fifo_init(&service_discovery_queue);
    k_fifo_init(&unrouted_packets_queue);
    k_fifo_init(&rpc_queue);
    k_fifo_init(&event_queue);

    daemon->controller_tid = k_thread_create(&controller_thread_data,
                                             controller_thread_stack,
                                             K_THREAD_STACK_SIZEOF(controller_thread_stack),
                                             cipher_controller_thread,
                                             (void *)daemon, NULL, NULL,
                                             CONTROLLER_THREAD_PRIORITY,
                                             0,
                                             K_FOREVER);
    k_thread_name_set(daemon->controller_tid, "cipher_controller");

    daemon->uplink_listener_tid = k_thread_create(&listener_thread_data,
                                                  listener_thread_stack,
                                                  K_THREAD_STACK_SIZEOF(listener_thread_stack),
                                                  cipher_listener_thread,
                                                  (void *)daemon, (void *)&daemon->uplink_cfg, NULL,
                                                  LISTENER_THREAD_PRIORITY,
                                                  0,
                                                  K_FOREVER);
    k_thread_name_set(daemon->uplink_listener_tid, "cipher_listener");

    daemon->router_tid = k_thread_create(&router_thread_data,
                                         router_thread_stack,
                                         K_THREAD_STACK_SIZEOF(router_thread_stack),
                                         cipher_router_thread,
                                         (void *)daemon, NULL, NULL,
                                         ROUTER_THREAD_PRIORITY,
                                         0,
                                         K_FOREVER);
    k_thread_name_set(daemon->router_tid, "cipher_router");

    daemon->sd_tid = k_thread_create(&sd_thread_data,
                                     sd_thread_stack,
                                     K_THREAD_STACK_SIZEOF(sd_thread_stack),
                                     cipher_sd_thread,
                                     (void *)daemon, NULL, NULL,
                                     SD_THREAD_PRIORITY,
                                     0,
                                     K_FOREVER);
    k_thread_name_set(daemon->sd_tid, "cipher_sd");

    daemon->rpc_tid = k_thread_create(&rpc_thread_data,
                                      rpc_thread_stack,
                                      K_THREAD_STACK_SIZEOF(rpc_thread_stack),
                                      cipher_rpc_thread,
                                      (void *)daemon, NULL, NULL,
                                      RPC_THREAD_PRIORITY,
                                      0,
                                      K_FOREVER);
    k_thread_name_set(daemon->rpc_tid, "cipher_rpc");

    daemon->event_tid = k_thread_create(&event_thread_data,
                                        event_thread_stack,
                                        K_THREAD_STACK_SIZEOF(event_thread_stack),
                                        cipher_event_thread,
                                        (void *)daemon, NULL, NULL,
                                        EVENT_THREAD_PRIORITY,
                                        0,
                                        K_FOREVER);
    k_thread_name_set(daemon->event_tid, "cipher_event");

    k_thread_start(daemon->controller_tid);
    k_thread_start(daemon->uplink_listener_tid);
    k_thread_start(daemon->sd_tid);
    k_thread_start(daemon->router_tid);
    k_thread_start(daemon->rpc_tid);
    k_thread_start(daemon->event_tid);

    // TODO: how do we verify all threads were initialized ok?
    return true;
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

            k_thread_abort(daemon->sd_tid);
            k_thread_abort(daemon->uplink_listener_tid);
            k_thread_abort(daemon->router_tid);

            tal_close(&daemon->uplink_cfg);

            DBG("Exiting");

            k_thread_abort(k_current_get());

            break;

        default:
            ERROR("Unknown controller event type: %d", event->type);
        }
    }
}
/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Listener Thread
 *---------------------------------------------------------------------------------------------------*/

static void process_packet(cipher_daemon_t *daemon, uint8_t *recv_buffer, uint16_t bytes_recv)
{
    if (bytes_recv < sizeof(cipher_header_t))
    {
        WARN("Incomplete payload");
    }
    else
    {
        cipher_header_t header = {0};
        if (!cipher_packet_parse_header(recv_buffer, bytes_recv, &header))
        {
            WARN("Unable to parse cipher header");
        }
        else
        {
            // cipher_print_header(&header);

            if (header.payload_len == bytes_recv - sizeof(header))
            {
                if (header.destination_id != daemon->device_id)
                {
                    void *unrouted_packet = k_heap_alloc(&unrouted_packets_heap, bytes_recv, K_FOREVER);
                    memcpy(unrouted_packet, recv_buffer, bytes_recv);
                    k_fifo_put(&unrouted_packets_queue, unrouted_packet);
                }
                else
                {
                    cipher_packet_t *packet = k_heap_alloc(&local_packets_heap, sizeof(cipher_packet_t), K_FOREVER);
                    packet->payload = k_heap_alloc(&local_packets_heap, bytes_recv, K_FOREVER);

                    cipher_decode_args_t args = {
                        .header = &header,
                        .raw_payload = recv_buffer,
                        .raw_payload_size = bytes_recv,
                        .decoded_payload = packet->payload,
                    };

                    cipher_error_t err = cipher_decode_packet(args);
                    if (err != CIPHER_ERROR_OK)
                        ERROR("Could not decode packet, err: %d", err);

                    switch (header.type)
                    {
                    case CIPHER_PACKET_TYPE_RPC:
                        break;
                    case CIPHER_PACKET_TYPE_EVENT:
                        break;
                    case CIPHER_PACKET_TYPE_SD:
                        k_fifo_put(&service_discovery_queue, (cipher_packet_t *)packet);
                        break;
                    default:
                        WARN("Unknow header type: %d", header.type);
                    }
                }
            }
            else
            {
                ERROR("Received incomplete packet, functionality not yet implemented");
                // TODO: COuld receive less OR more bytes so account for this
            }
        }
    }
}

static void cipher_listener_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *daemon = (cipher_daemon_t *)arg0;
    tal_config_t *interface_cfg = (tal_config_t *)arg1;

    while (1)
    {
        const size_t buffer_size = CIPHER_CONFIG_MAX_PAYLOAD_SIZE;
        uint8_t *recv_buffer = k_heap_alloc(&recv_buffers_heap, CIPHER_CONFIG_MAX_PAYLOAD_SIZE, K_FOREVER);
        uint16_t bytes_recv = 0;
        bool conn_closed = false;

        if (tal_recv(interface_cfg, recv_buffer, buffer_size, &bytes_recv, &conn_closed))
        {
            process_packet(daemon, recv_buffer, bytes_recv);
        }
        else
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
                k_fifo_alloc_put(&controller_event_queue, &exit_event);
                k_thread_suspend(k_current_get());
            }
        }

        k_heap_free(&recv_buffers_heap, recv_buffer);
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                             Service Discovery Thread
 *---------------------------------------------------------------------------------------------------*/
static void cipher_sd_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *daemon = (cipher_daemon_t *)arg0;

    while (true)
    {
        cipher_packet_t *packet = k_fifo_get(&service_discovery_queue, K_FOREVER);
        cipher_payload_sd_t *payload = (cipher_payload_sd_t *)packet->payload;
        // LOG("SD packet: ID -> %d, Hops: %d ", payload->service_id, payload->num_hops);

        k_heap_free(&local_packets_heap, packet->payload);
        k_heap_free(&local_packets_heap, packet);
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Router Thread
 *---------------------------------------------------------------------------------------------------*/
static void cipher_router_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *daemon = (cipher_daemon_t *)arg0;

    while (true)
    {
        void *packet = k_fifo_get(&unrouted_packets_queue, K_FOREVER);
        LOG("Doing something with unrouted packet");
        k_heap_free(&unrouted_packets_heap, packet);
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           RPC Thread
 *---------------------------------------------------------------------------------------------------*/
static void cipher_rpc_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *daemon = (cipher_daemon_t *)arg0;

    while (true)
    {
        void *packet = k_fifo_get(&rpc_queue, K_FOREVER);
        LOG("Doing something with RPC");
        k_heap_free(&local_packets_heap, packet);
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Event Thread
 *---------------------------------------------------------------------------------------------------*/
static void cipher_event_thread(void *arg0, void *arg1, void *arg2)
{
    cipher_daemon_t *daemon = (cipher_daemon_t *)arg0;

    while (true)
    {
        void **packet = k_fifo_get(&event_queue, K_FOREVER);
        LOG("Doing something with event");
        k_heap_free(&local_packets_heap, packet);
    }
}