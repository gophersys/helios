// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>
#include <zephyr/random/rand32.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "daemon/registry.h"
#include "utils/err.h"

// Private include
#include "threads.h"

LOG_MODULE_REGISTER(daemon, CONFIG_CK_CIPHER_DAEMON_LOG_LEVEL);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

static void assert_config(const cipher_daemon_config_t *cfg);
static void print_daemon_stats(cipher_daemon_t *d);
static void setup_daemon_id(cipher_daemon_t *d);
static void init_objects(cipher_daemon_t *d);
static void init_registries(cipher_daemon_t *d);
static void init_interface_objects(cipher_iface_t *iface);
static void init_interfaces(cipher_daemon_t *d);
static void init_threads(cipher_daemon_t *d);

static void initialize_interface_group(cipher_daemon_t *d, cipher_iface_thread_group_t *t_group, size_t num);
static void start_interface_group(cipher_daemon_t *d, cipher_iface_thread_group_t *t_group, size_t num);

char *cipher_t_name(const char *prefix, uint8_t d_id, char *buffer, size_t buflen);
char *iface_t_name(const char *prefix, uint8_t d_id, uint8_t iface_id, char *buffer, size_t buflen);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/
void cipher_daemon_start(cipher_daemon_config_t *cfg, cipher_daemon_t *d)
{
    __ASSERT(cfg != NULL, "Daemon cfg pointer must not be NULL");
    __ASSERT(d != NULL, "Daemon struct pointer must not be NULL");

    assert_config(cfg);
    d->cfg = cfg;
    d->device_id = cfg->device_id;

    print_daemon_stats(d);

    setup_daemon_id(d);
    init_objects(d);
    init_registries(d);
    init_interfaces(d);

    cipher_rpc_init(d);

    init_threads(d);

    DBG("Daemon instance %d, initialized OK, device id: %d", d->id, d->device_id);
}

void cipher_daemon_start(cipher_daemon_t *d)
{

    // Init Daemon threads
    k_thread_start(d->ctrl_t_id);
    k_thread_start(d->sd.t_id);

    k_thread_start(d->event_t_id);
    k_thread_start(d->stream_t_id);

    // Init interface threads
    start_interface_group(d, d->downlink_t_g, d->cfg->num_server_ifaces);
    start_interface_group(d, d->uplink_t_g, d->cfg->num_client_ifaces);
}

void cipher_register_local_services(cipher_daemon_t *d, cipher_service_entry_t *entries, size_t num_entries)
{
    for (size_t i = 0; i < num_entries; i++)
    {
        entries[i].local = true;
        if (!registry_service_add(d, &entries[i]))
        {
            ERROR("Unable to register local service %d, for daemon %d", entries[i].service.id, d->id);
        }

        cipher_service_end_point_t localhost =
        {
            .device_id = CONFIG_CIPHER_LOCAL_ADDR,
            .iface = NULL,
        };

        if (!registry_end_point_add_to_service(d, &entries[i], &localhost))
        {
            ERROR("Unable to register localhost end point for service %d, for daemon %d", entries[i].service.id, d->id);
        }
    }
}

void cipher_register_remote_services(cipher_daemon_t *d, cipher_service_entry_t *entries, size_t num_entries)
{
    for (size_t i = 0; i < num_entries; i++)
    {
        entries[i].local = false;
        if (!registry_service_add(d, &entries[i]))
        {
            ERROR("Unable to register remote service %d, for daemon %d", entries[i].service.id, d->id);
        }

        // Host end points are associated with a specific service at run time
    }
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
#if CONFIG_CK_CIPHER_DAEMON_LOG_LEVEL == LOG_LEVEL_DBG
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
 * @brief Set the up id of daemon instance
 *
 * @param d The daemon
 */
static void setup_daemon_id(cipher_daemon_t *d)
{
    static uint8_t instances = 0;
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
    k_fifo_init(&d->admin_packet_queue);
    k_fifo_init(&d->ctrl_event_queue);

    k_fifo_init(&d->sd.packets_event_queue);
    k_fifo_init(&d->sd.iface_conn_queue);
    k_fifo_init(&d->sd.iface_disconn_queue);

    k_fifo_init(&d->events_packet_event_queue);

    k_heap_init(&d->ctrl_events_heap, d->ctrl_events_heap_mem, sizeof(d->ctrl_events_heap_mem));

    k_heap_init(&d->net_buffers_heap, d->net_buffers_heap_mem, sizeof(d->net_buffers_heap_mem));
    k_heap_init(&d->partial_packets_heap, d->net_partial_packets_heap_mem, sizeof(d->net_partial_packets_heap_mem));
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
    memset(&d->rpc_registry.entries, 0, ARRAY_SIZE(d->rpc_registry.entries));
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
    char name_buf[32];
    d->ctrl_t_id = k_thread_create(&d->ctrl_t_data,
                                   d->ctrl_t_stack,
                                   K_THREAD_STACK_SIZEOF(d->ctrl_t_stack),
                                   cipher_ctrl_thread,
                                   (void *)d, NULL, NULL,
                                   CTRL_THREAD_PRIORITY,
                                   0,
                                   K_FOREVER);
    k_thread_name_set(d->ctrl_t_id, cipher_t_name("cipher_controller", d->id, name_buf, sizeof(name_buf)));

    d->sd.t_id = k_thread_create(&d->sd.t_data,
                                 d->sd.t_stack,
                                 K_THREAD_STACK_SIZEOF(d->sd.t_stack),
                                 cipher_sd_thread,
                                 (void *)d, NULL, NULL,
                                 SD_THREAD_PRIORITY,
                                 0,
                                 K_FOREVER);
    k_thread_name_set(d->sd.t_id, cipher_t_name("cipher_sd", d->device_id, name_buf, sizeof(name_buf)));

    d->event_t_id = k_thread_create(&d->event_t_data,
                                    d->event_t_stack,
                                    K_THREAD_STACK_SIZEOF(d->event_t_stack),
                                    cipher_event_thread,
                                    (void *)d, NULL, NULL,
                                    EVENT_THREAD_PRIORITY,
                                    0,
                                    K_FOREVER);
    k_thread_name_set(d->event_t_id, cipher_t_name("cipher_event", d->device_id, name_buf, sizeof(name_buf)));

    d->stream_t_id = k_thread_create(&d->stream_t_data,
                                     d->stream_t_stack,
                                     K_THREAD_STACK_SIZEOF(d->stream_t_stack),
                                     cipher_stream_thread,
                                     (void *)d, NULL, NULL,
                                     STREAM_THREAD_PRIORITY,
                                     0,
                                     K_FOREVER);
    k_thread_name_set(d->event_t_id, cipher_t_name("cipher_stream", d->device_id, name_buf, sizeof(name_buf)));
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Interfaces
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Initializes interface semaphores and queues
 *
 * @param iface The interface
 */
static void init_interface_objects(cipher_iface_t *iface)
{
    k_sem_init(&iface->conn_sem, 0, CONFIG_IFACE_CONN_SEM_COUNT);
    k_sem_init(&iface->disconn_sem, 0, 1);
    k_fifo_init(&iface->encoded_packets_queue);
    k_fifo_init(&iface->decoded_packets_queue);
}

/**
 * @brief Initializes all the interfaces of the daemon instance
 *
 * @param d The daemon
 */
static void init_interfaces(cipher_daemon_t *d)
{
    // Assign an interface to each thread group
    uint8_t iface_id = 0;
    for (uint8_t i = 0; i < d->cfg->num_server_ifaces; i++)
    {
        d->downlink_t_g[i].iface.id = iface_id++;
        d->downlink_t_g[i].iface.cfg = &d->cfg->server_ifaces[i];
        d->downlink_t_g[i].iface.connected = false;
        init_interface_objects(&d->downlink_t_g[i].iface);
    }

    for (uint8_t i = 0; i < d->cfg->num_client_ifaces; i++)
    {
        d->uplink_t_g[i].iface.id = iface_id++;
        d->uplink_t_g[i].iface.cfg = &d->cfg->client_ifaces[i];
        d->uplink_t_g[i].iface.connected = false;
        init_interface_objects(&d->uplink_t_g[i].iface);
    }

    // Initialize all interfaces
    initialize_interface_group(d, d->downlink_t_g, d->cfg->num_server_ifaces);
    initialize_interface_group(d, d->uplink_t_g, d->cfg->num_client_ifaces);
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
    }
}

static void start_interface_group(cipher_daemon_t *d, cipher_iface_thread_group_t *t_group, size_t num)
{
    for (uint8_t i = 0; i < num; i++)
    {
        cipher_iface_thread_info_t *conn_t = &t_group[i].connection_t;
        cipher_iface_thread_info_t *send_t = &t_group[i].send_t;
        cipher_iface_thread_info_t *recv_t = &t_group[i].recv_t;
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