// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/logging/log.h>
#include <zephyr/kernel.h>
#include <zephyr/random/rand32.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "utils/err.h"

// Private include
#include "threads.h"

LOG_MODULE_REGISTER(daemon, DAEMON_LOG_LEVEL);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

static void assert_config(const cipher_daemon_config_t *cfg);
static void print_daemon_stats(cipher_daemon_t *d);
static void setup_ids(cipher_daemon_t *d);
static void init_objects(cipher_daemon_t *d);
static void init_registries(cipher_daemon_t *d);
static void init_interfaces(cipher_daemon_t *d);
static void init_threads(cipher_daemon_t *d);

static void initialize_interface_group(cipher_daemon_t *d, cipher_iface_thread_group_t *t_group, size_t num);

char *cipher_t_name(const char *prefix, uint8_t d_id, char *buffer, size_t buflen);
char *iface_t_name(const char *prefix, uint8_t d_id, uint8_t iface_id, char *buffer, size_t buflen);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/
void cipher_init_daemon(cipher_daemon_config_t *cfg, cipher_daemon_t *d)
{
    __ASSERT(cfg != NULL, "Daemon cfg pointer must not be NULL");
    __ASSERT(d != NULL, "Daemon struct pointer must not be NULL");

    assert_config(cfg);
    d->cfg = cfg;

    print_daemon_stats(d);

    setup_ids(d);
    init_objects(d);
    init_registries(d);
    init_interfaces(d);
    init_threads(d);

    DBG("Daemon instance %d, initialized OK, device id: %d", d->id, d->device_id);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Assert config
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Verify that the user configuration passed is valid
 *
 * @param cfg The user config
 * @return true If the configuration passed was valid
 * @return false If an invalid field or configuration are passed
 */
static void assert_config(const cipher_daemon_config_t *cfg)
{
    // TODO: What checks can be done here?
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Print Size
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Prints useful debug information such as stack sizes, heap pool sizes, number of interfaces,
 * etc
 *
 * @param d The daemon
 */
static void print_daemon_stats(cipher_daemon_t *d)
{
#if DAEMON_LOG_LEVEL == LOG_LEVEL_DBG
    LOG_RAW("\nDaemon instance %d stats:\n", d->id);
    LOG_RAW("\tcipher_daemon_t size: %d bytes\n", sizeof(cipher_daemon_t));

    // Heaps
    LOG_RAW("%s", "\nHEAPS:\n");
    LOG_RAW("\tnet_packets_heap: %d bytes\n", CONFIG_NET_PACKET_HEAP_SIZE);
    LOG_RAW("\tnet_partial_packets_heap: %d bytes\n", CONFIG_NET_PART_PACKET_HEAP_SIZE);
    LOG_RAW("\tunrouted_packets_heap: %d bytes\n", CONFIG_UNROUTED_PACKETS_HEAP_SIZE);
    LOG_RAW("\tlocal_packets_heap: %d bytes\n", CONFIG_LOCAL_PACKETS_HEAP_SIZE);

    LOG_RAW("%s", "\n\n");
#endif
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                            Setup Ids
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Set the up ids of daemon instance and the device
 *
 * @param d The daemon
 */
static void setup_ids(cipher_daemon_t *d)
{
    static uint8_t instances = 0;
    static uint16_t device_id = 0;
    static bool initialized = false;

    if (!initialized)
    {

        // All interfaces will broadcast the same device Id
        sys_rand_get(&device_id, sizeof(device_id)); // TODO: What happens if remote end has same Id?
        initialized = true;
    }

    d->device_id = device_id;
    d->id = instances++;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Objects
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Initialize queues, heaps, semaphores and mutexes used by the daemon
 *
 * @param d The daemon
 */
static void init_objects(cipher_daemon_t *d)
{
    k_fifo_init(&d->send_queue);
    k_fifo_init(&d->ctrl_event_queue);
    k_fifo_init(&d->sd_packet_queue);
    k_fifo_init(&d->unrouted_packets_queue);
    k_fifo_init(&d->admin_packet_queue);
    k_fifo_init(&d->rpc_packet_queue);
    k_fifo_init(&d->event_packet_queue);

    k_heap_init(&d->ctrl_events_heap, d->ctrl_events_heap_mem, sizeof(d->ctrl_events_heap_mem));
    k_heap_init(&d->net_packets_heap, d->net_packets_heap_mem, sizeof(d->net_packets_heap_mem));
    k_heap_init(&d->net_partial_packets_heap, d->net_partial_packets_heap_mem, sizeof(d->net_partial_packets_heap_mem));
    k_heap_init(&d->unrouted_packets_heap, d->unrouted_packets_heap_mem, sizeof(d->unrouted_packets_heap_mem));
    k_heap_init(&d->local_packets_heap, d->local_packets_heap_mem, sizeof(d->local_packets_heap_mem));
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Registries
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Initializes service registries, devices registries, etc. used by the daemon
 *
 * @param d The daemon
 */
static void init_registries(cipher_daemon_t *d)
{
    memset(&d->service_registry, 0, sizeof(d->service_registry));
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Threads
 *---------------------------------------------------------------------------------------------------*/
/**
 * @brief Initialize all daemon and interface threads
 *
 * @param d The daemon
 */
static void init_threads(cipher_daemon_t *d)
{

    // Initialize all daemon threads
    char name_buf[32];
    d->ctrl_t_id = k_thread_create(&d->ctrl_t_data,
                                   d->ctrl_t_stack,
                                   K_THREAD_STACK_SIZEOF(d->ctrl_t_stack),
                                   cipher_ctrl_thread,
                                   (void *)d, NULL, NULL,
                                   CONTROLLER_THREAD_PRIORITY,
                                   0,
                                   K_FOREVER);
    k_thread_name_set(d->ctrl_t_id, cipher_t_name("cipher_controller", d->id, name_buf, sizeof(name_buf)));

    d->sd_t_id = k_thread_create(&d->sd_t_data,
                                 d->sd_t_stack,
                                 K_THREAD_STACK_SIZEOF(d->sd_t_stack),
                                 cipher_sd_thread,
                                 (void *)d, NULL, NULL,
                                 SD_THREAD_PRIORITY,
                                 0,
                                 K_FOREVER);
    k_thread_name_set(d->sd_t_id, cipher_t_name("cipher_sd", d->device_id, name_buf, sizeof(name_buf)));

    d->router_t_id = k_thread_create(&d->router_t_data,
                                     d->router_t_stack,
                                     K_THREAD_STACK_SIZEOF(d->router_t_stack),
                                     cipher_router_thread,
                                     (void *)d, NULL, NULL,
                                     ROUTER_THREAD_PRIORITY,
                                     0,
                                     K_FOREVER);
    k_thread_name_set(d->router_t_id, cipher_t_name("cipher_router", d->device_id, name_buf, sizeof(name_buf)));

    d->rpc_t_id = k_thread_create(&d->rpc_t_data,
                                  d->rpc_t_stack,
                                  K_THREAD_STACK_SIZEOF(d->rpc_t_stack),
                                  cipher_rpc_thread,
                                  (void *)d, NULL, NULL,
                                  RPC_THREAD_PRIORITY,
                                  0,
                                  K_FOREVER);
    k_thread_name_set(d->rpc_t_id, cipher_t_name("cipher_rpc", d->device_id, name_buf, sizeof(name_buf)));

    d->event_t_id = k_thread_create(&d->event_t_data,
                                    d->event_t_stack,
                                    K_THREAD_STACK_SIZEOF(d->event_t_stack),
                                    cipher_event_thread,
                                    (void *)d, NULL, NULL,
                                    EVENT_THREAD_PRIORITY,
                                    0,
                                    K_FOREVER);
    k_thread_name_set(d->event_t_id, cipher_t_name("cipher_event", d->device_id, name_buf, sizeof(name_buf)));

    // Start all dameon threads
    k_thread_start(d->ctrl_t_id);
    k_thread_start(d->sd_t_id);
    k_thread_start(d->router_t_id);
    k_thread_start(d->rpc_t_id);
    k_thread_start(d->event_t_id);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Interfaces
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Initializes all the interfaces of the daemon instance
 *
 * @param d The daemon
 */
static void init_interfaces(cipher_daemon_t *d)
{
    uint8_t num_up_link_ifaces = CONFIG_UP_LINK_IFACE_COUNT;
    uint8_t num_down_link_ifaces = CONFIG_UP_LINK_IFACE_COUNT;

    // Assign an interface to each thread group
    uint8_t iface_id = 0;
    for (uint8_t i = 0; i < num_up_link_ifaces; i++)
    {
        d->uplink_t_g[i].iface.id = iface_id++;
        d->uplink_t_g[i].iface.cfg = &d->cfg->uplink_ifaces[i];
    }

    for (uint8_t i = 0; i < num_down_link_ifaces; i++)
    {
        d->downlink_t_g[i].iface.id = iface_id++;
        d->downlink_t_g[i].iface.cfg = &d->cfg->downlink_ifaces[i];
    }

    // Initialize & Start all interfaces
    initialize_interface_group(d, d->uplink_t_g, num_up_link_ifaces);
    initialize_interface_group(d, d->downlink_t_g, num_down_link_ifaces);
}

/**
 * @brief Initialize a connection, send and recv thread for an interface group.
 *
 * @param d The daemon
 * @param ifaces The interface group
 * @param num The number of interfaces in the group
 * @param t_group The thread group
 */
static void initialize_interface_group(cipher_daemon_t *d, cipher_iface_thread_group_t *t_group, size_t num)
{
    char name_buf[32];
    uint8_t conn_t_prio = TRANSPORT_THREAD_BASE_PRIORITY - 1;
    uint8_t send_t_prio = TRANSPORT_THREAD_BASE_PRIORITY;
    uint8_t recv_t_prio = TRANSPORT_THREAD_BASE_PRIORITY;

    for (uint8_t i = 0; i < num; i++)
    {
        cipher_iface_thread_info_t *conn_t = &t_group[i].connection_t;
        conn_t->id = k_thread_create(&conn_t->data,
                                     conn_t->stack,
                                     K_THREAD_STACK_SIZEOF(conn_t->stack),
                                     cipher_interface_conn_thread,
                                     (void *)d, (void *)&t_group[i].iface, NULL,
                                     conn_t_prio,
                                     0,
                                     K_FOREVER);
        k_thread_name_set(conn_t->id, iface_t_name("iface_conn", d->id, t_group[i].iface.id, name_buf, sizeof(name_buf)));

        cipher_iface_thread_info_t *send_t = &t_group[i].send_t;
        send_t->id = k_thread_create(&send_t->data,
                                     send_t->stack,
                                     K_THREAD_STACK_SIZEOF(send_t->stack),
                                     cipher_interface_send_thread,
                                     (void *)d, (void *)&t_group[i].iface, NULL,
                                     send_t_prio,
                                     0,
                                     K_FOREVER);
        k_thread_name_set(send_t->id, iface_t_name("iface_send", d->id, t_group[i].iface.id, name_buf, sizeof(name_buf)));

        cipher_iface_thread_info_t *recv_t = &t_group[i].recv_t;
        recv_t->id = k_thread_create(&recv_t->data,
                                     recv_t->stack,
                                     K_THREAD_STACK_SIZEOF(recv_t->stack),
                                     cipher_interface_recv_thread,
                                     (void *)d, (void *)&t_group[i].iface, NULL,
                                     recv_t_prio,
                                     0,
                                     K_FOREVER);
        k_thread_name_set(recv_t->id, iface_t_name("iface_recv", d->id, t_group[i].iface.id, name_buf, sizeof(name_buf)));

        k_thread_start(conn_t->id);
        k_thread_start(send_t->id);
        k_thread_start(recv_t->id);
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Helpers
 *---------------------------------------------------------------------------------------------------*/
char *cipher_t_name(const char *prefix, uint8_t d_id, char *buffer, size_t buflen)
{
    uint16_t last_4_digits = d_id % 10000;
    snprintf(buffer, buflen, "%s_%02u", prefix, last_4_digits);
    return buffer;
}

char *iface_t_name(const char *prefix, uint8_t d_id, uint8_t iface_id, char *buffer, size_t buflen)
{
    snprintf(buffer, buflen, "%s_%02u_%03u", prefix, d_id, iface_id);
    return buffer;
}