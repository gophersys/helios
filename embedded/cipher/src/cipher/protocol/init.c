#include "cipher.h"

// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/logging/log.h>
#include <zephyr/kernel.h>
#include <zephyr/random/rand32.h>
#include <zephyr/net/socket.h>

// Private includes
#include "tal.h"
#include "utils.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/
LOG_MODULE_REGISTER(cipher, LOG_LEVEL_DBG);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

// Check configurations
static bool cipher_assert_daemon(cipher_daemon_t *d);

// Objects
static bool cipher_init_objects(cipher_daemon_t *d);

// Interfaces
static void initialize_interface_group(cipher_daemon_t *d, tal_config_t *interfaces, size_t num,
                                       cipher_interface_thread_group_t *t_g);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/
bool init_cipher_daemon(cipher_daemon_t *d)
{
    sys_rand_get(&d->device_id, sizeof(d->device_id));
    bool status = cipher_init_objects(d);

    if (status)
        status = cipher_init_threads(d);

    return status;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Assert config
 *---------------------------------------------------------------------------------------------------*/
static bool cipher_assert_daemon(cipher_daemon_t *d)
{
    bool status = true;

    for (uint8_t i = 0; i < CONFIG_UP_LINK_INTERFACE_COUNT && status; i++)
    {
        if (&d->uplink_interface_cfg[i] == NULL)
        {
            WARN("Uplink interface %d not defined, see CONFIG_UP_LINK_INTERFACE_COUNT", i);
            status = false;
        }
    }

    for (uint8_t i = 0; i < CONFIG_DOWN_LINK_INTERFACE_COUNT && status; i++)
    {
        if (&d->downlink_interface_cfg[i] == NULL)
        {
            WARN("Downlink interface %d not defined, see CONFIG_DOWN_LINK_INTERFACE_COUNT", i);
            status = false;
        }
    }

    return status;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Objects
 *---------------------------------------------------------------------------------------------------*/
static bool cipher_init_objects(cipher_daemon_t *d)
{
    bool status = false;

    k_fifo_init(&d->controller_event_queue);
    k_fifo_init(&d->service_discovery_queue);
    k_fifo_init(&d->unrouted_packets_queue);
    k_fifo_init(&d->rpc_queue);
    k_fifo_init(&d->event_queue);

    k_heap_init(&d->recv_buffers_heap, d->recv_buffers_heap_mem, sizeof(d->recv_buffers_heap_mem));
    k_heap_init(&d->unrouted_packets_heap, d->unrouted_packets_heap_mem, sizeof(d->unrouted_packets_heap_mem));
    k_heap_init(&d->local_packets_heap, d->local_packets_heap_mem, sizeof(d->local_packets_heap_mem));

    return status;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Threads
 *---------------------------------------------------------------------------------------------------*/
bool cipher_init_threads(cipher_daemon_t *d)
{
    // TODO: Add Ids to the thread names to make them easy to identify
    d->ctrl_t_id = k_thread_create(&d->ctrl_t_data,
                                   d->ctrl_t_stack,
                                   K_THREAD_STACK_SIZEOF(d->ctrl_t_stack),
                                   cipher_controller_thread,
                                   (void *)d, NULL, NULL,
                                   CONTROLLER_THREAD_PRIORITY,
                                   0,
                                   K_FOREVER);
    k_thread_name_set(d->ctrl_t_id, "cipher_controller");

    d->sd_t_id = k_thread_create(&d->sd_t_data,
                                 d->sd_t_stack,
                                 K_THREAD_STACK_SIZEOF(d->sd_t_stack),
                                 cipher_sd_thread,
                                 (void *)d, NULL, NULL,
                                 SD_THREAD_PRIORITY,
                                 0,
                                 K_FOREVER);
    k_thread_name_set(d->sd_t_id, "cipher_sd");

    d->router_t_id = k_thread_create(&d->router_t_data,
                                     d->router_t_stack,
                                     K_THREAD_STACK_SIZEOF(d->router_t_stack),
                                     cipher_router_thread,
                                     (void *)d, NULL, NULL,
                                     ROUTER_THREAD_PRIORITY,
                                     0,
                                     K_FOREVER);
    k_thread_name_set(d->router_t_id, "cipher_router");

    d->rpc_t_id = k_thread_create(&d->rpc_t_data,
                                  d->rpc_t_stack,
                                  K_THREAD_STACK_SIZEOF(d->rpc_t_stack),
                                  cipher_rpc_thread,
                                  (void *)d, NULL, NULL,
                                  RPC_THREAD_PRIORITY,
                                  0,
                                  K_FOREVER);
    k_thread_name_set(d->rpc_t_id, "cipher_rpc");

    d->event_t_id = k_thread_create(&d->event_t_data,
                                    d->event_t_stack,
                                    K_THREAD_STACK_SIZEOF(d->event_t_stack),
                                    cipher_event_thread,
                                    (void *)d, NULL, NULL,
                                    EVENT_THREAD_PRIORITY,
                                    0,
                                    K_FOREVER);
    k_thread_name_set(d->event_t_id, "cipher_event");

    initialize_interface_group(d, d->uplink_interface_cfg, CONFIG_UP_LINK_INTERFACE_COUNT, d->uplink_t_g);
    initialize_interface_group(d, d->downlink_interface_cfg, CONFIG_DOWN_LINK_INTERFACE_COUNT, d->downlink_t_g);

    k_thread_start(d->ctrl_t_id);
    k_thread_start(d->sd_t_id);
    k_thread_start(d->router_t_id);
    k_thread_start(d->rpc_t_id);
    k_thread_start(d->event_t_id);

    // TODO: how do we verify all threads were initialized ok?
    return true;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Interfaces
 *---------------------------------------------------------------------------------------------------*/
static void initialize_interface_group(cipher_daemon_t *d, tal_config_t *interfaces, size_t num,
                                       cipher_interface_thread_group_t *t_g)
{
    for (uint8_t i = 0; i < num; i++)
    {
        cipher_connection_thread_info_t *conn_t = &t_g[i].connection_t;
        conn_t->id = k_thread_create(&conn_t->data,
                                     conn_t->stack,
                                     K_THREAD_STACK_SIZEOF(conn_t->stack),
                                     cipher_interface_conn_thread,
                                     (void *)d, (void *)&interfaces[i], NULL,
                                     CONNECTION_THREAD_PRIORITY,
                                     0,
                                     K_FOREVER);
        k_thread_name_set(conn_t->id, "cipher_int_conn");

        cipher_transport_thread_info_t *send_t = &t_g[i].send_t;
        send_t->id = k_thread_create(&send_t->data,
                                     send_t->stack,
                                     K_THREAD_STACK_SIZEOF(send_t->stack),
                                     cipher_interface_send_thread,
                                     (void *)d, (void *)&interfaces[i], NULL,
                                     TRANSPORT_THREAD_PRIORITY,
                                     0,
                                     K_FOREVER);
        k_thread_name_set(send_t->id, "cipher_int_send");

        cipher_transport_thread_info_t *recv_t = &t_g[i].recv_t;
        recv_t->id = k_thread_create(&recv_t->data,
                                     recv_t->stack,
                                     K_THREAD_STACK_SIZEOF(recv_t->stack),
                                     cipher_interface_recv_thread,
                                     (void *)d, (void *)&interfaces[i], NULL,
                                     TRANSPORT_THREAD_PRIORITY,
                                     0,
                                     K_FOREVER);
        k_thread_name_set(recv_t->id, "cipher_int_recv");

        k_thread_start(conn_t->id);
        k_thread_start(send_t->id);
        k_thread_start(recv_t->id);
    }
}
