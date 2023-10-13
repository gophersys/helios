#ifndef DAEMON_CONFIG_H
#define DAEMON_CONFIG_H

// Cipher includes
#include "config/daemon.h"
#include "config/default.h"
#include "daemon/iface.h"
#include "daemon/service.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Deamon
 *---------------------------------------------------------------------------------------------------*/

typedef struct {
    k_tid_t sd_t_id;
    struct k_thread sd_t_data;
    K_THREAD_STACK_MEMBER(sd_t_stack, SD_THREAD_STACK_SIZE);

    struct k_fifo sd_packet_queue;

    struct k_fifo sd_iface_conn_queue;  ///< Queue used by the service discovery thread to
                                        ///< receive connected interface updates
                                        ///< @param cipher_iface_t *
                                        ///< @heap No heap, passing pointer

    struct k_fifo sd_iface_disconn_queue;  ///< Queue used by the service discovery thread to
                                           ///< receive disconnected interface updates
                                           ///< @param cipher_iface_t *
                                           ///< @heap No heap, passing pointer

} cipher_daemon_sd_info_t;

typedef struct {
    // Thread info
    k_tid_t rpc_t_id;
    struct k_thread rpc_t_data;
    K_THREAD_STACK_MEMBER(rpc_t_stack, RPC_THREAD_STACK_SIZE);

    // RPC
    struct k_fifo rpc_packet_event_queue;
    struct k_fifo rpc_ctrl_event_queue;
    struct k_fifo rpc_local_request_event_queue;

    /**
     * @brief Heap pool to send events to daemon controller thread
     */
    struct k_heap rpc_heap;
    uint8_t __aligned(8) rpc_heap_mem[CONFIG_RPC_EVENTS_HEAP_SIZE];

} cipher_daemon_rpc_info_t;

typedef struct {
    // user config
    cipher_daemon_config_t *cfg;

    // Device Unique Id
    uint16_t device_id;

    // Daemon Instance Id
    uint8_t id;

    /*-----------------------------------------------
     *                                        Threads
     *---------------------------------------------*/

    k_tid_t ctrl_t_id;
    struct k_thread ctrl_t_data;
    K_THREAD_STACK_MEMBER(ctrl_t_stack, CTRL_THREAD_STACK_SIZE);

    k_tid_t event_t_id;
    struct k_thread event_t_data;
    K_THREAD_STACK_MEMBER(event_t_stack, EVENT_THREAD_STACK_SIZE);

    k_tid_t stream_t_id;
    struct k_thread stream_t_data;
    K_THREAD_STACK_MEMBER(stream_t_stack, STREAM_THREAD_STACK_SIZE);

    /*-----------------------------------------------
     *                                         Ifaces
     *---------------------------------------------*/

    // Uplink thread groups
    cipher_iface_thread_group_t uplink_t_g[CONFIG_UP_LINK_IFACE_COUNT];

    // Downlink thread groups
    cipher_iface_thread_group_t downlink_t_g[CONFIG_DOWN_LINK_IFACE_COUNT];

    /*-----------------------------------------------
     *                                         Queues
     *---------------------------------------------*/

    // Controller
    struct k_fifo ctrl_event_queue;
    struct k_fifo admin_packet_queue;

    // Events
    struct k_fifo events_packet_event_queue;

    // Streams
    struct k_fifo stream_packet_event_queue;

    cipher_daemon_sd_info_t sd;
    cipher_daemon_rpc_info_t rpc;

    /*-----------------------------------------------
     *                                          Heaps
     *---------------------------------------------*/

    /**
     * @brief Heap pool to send events to daemon controller thread
     */
    struct k_heap ctrl_events_heap;
    uint8_t __aligned(8) ctrl_events_heap_mem[CONFIG_CTRL_EVENTS_HEAP_SIZE];

    /**
     * @brief Heap pool to receive and send network packets using send() and recv()
     */
    struct k_heap net_buffers_heap;
    uint8_t __aligned(8) net_buffers_heap_mem[CONFIG_NET_PACKET_HEAP_SIZE];

    /**
     * @brief Heap pool to keep local deserialized packets ready for processing
     */
    struct k_heap local_packets_heap;
    uint8_t __aligned(8) local_packets_heap_mem[CONFIG_LOCAL_PACKETS_HEAP_SIZE];

    /**
     * @brief Heap pool to keep partial packets stored, until the rest arrives on the network
     */
    struct k_heap partial_packets_heap;
    uint8_t __aligned(8) net_partial_packets_heap_mem[CONFIG_NET_PART_PACKET_HEAP_SIZE];

    /**
     * @brief Heap pool to keep unrouted packets until they're routed on the network again
     */
    struct k_heap unrouted_packets_heap;
    uint8_t __aligned(8) unrouted_packets_heap_mem[CONFIG_UNROUTED_PACKETS_HEAP_SIZE];

    /*-----------------------------------------------
     *                                     Registries
     *---------------------------------------------*/
    cipher_service_registry_t service_registry;
    cipher_rpc_registry_t rpc_registry;

} cipher_daemon_t;

#endif  // DAEMON_CONFIG_H