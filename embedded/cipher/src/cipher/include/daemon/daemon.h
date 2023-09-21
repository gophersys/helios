#ifndef DAEMON_CONFIG_H
#define DAEMON_CONFIG_H

// Cipher includes
#include "config/default.h"
#include "config/daemon.h"
#include "transport/transport.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Packet Layer
 *---------------------------------------------------------------------------------------------------*/

typedef struct
{
    uint8_t id;
    tal_config_t *cfg;
    bool connected;
    struct k_sem conn_sem;
    struct k_sem disconn_sem;
} cipher_iface_t;

// Connection manager thread for the given interface
typedef struct
{
    k_tid_t id;
    struct k_thread data;
    K_THREAD_STACK_MEMBER(stack, CONNECTION_THREAD_STACK_SIZE);
} cipher_connection_thread_info_t;

// Send and Recv threads are identical
typedef struct
{
    k_tid_t id;
    struct k_thread data;
    K_THREAD_STACK_MEMBER(stack, TRANSPORT_THREAD_STACK_SIZE);
} cipher_transport_thread_info_t;

// Interface thread group (connect, send and recv)
typedef struct
{
    cipher_iface_t iface;
    cipher_connection_thread_info_t connection_t;
    cipher_transport_thread_info_t send_t;
    cipher_transport_thread_info_t recv_t;
} cipher_interface_thread_group_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Deamon
 *---------------------------------------------------------------------------------------------------*/
typedef struct
{
    // user config
    cipher_daemon_config_t *cfg;

    // Device Unique Id
    uint16_t device_id;

    // Daemon Instance Id
    uint8_t id;

    // Controller thread info
    k_tid_t ctrl_t_id;
    struct k_thread ctrl_t_data;
    K_THREAD_STACK_MEMBER(ctrl_t_stack, 1024);

    // Service discovery thread info
    k_tid_t sd_t_id;
    struct k_thread sd_t_data;
    K_THREAD_STACK_MEMBER(sd_t_stack, 1024);

    // Router thread info
    k_tid_t router_t_id;
    struct k_thread router_t_data;
    K_THREAD_STACK_MEMBER(router_t_stack, 1024);

    // RPC thread info
    k_tid_t rpc_t_id;
    struct k_thread rpc_t_data;
    K_THREAD_STACK_MEMBER(rpc_t_stack, 1024);

    // Event thread info
    k_tid_t event_t_id;
    struct k_thread event_t_data;
    K_THREAD_STACK_MEMBER(event_t_stack, 1024);

    // Uplink thread groups
    cipher_interface_thread_group_t uplink_t_g[CONFIG_UP_LINK_INTERFACE_COUNT];

    // Downlink thread groups
    cipher_interface_thread_group_t downlink_t_g[CONFIG_DOWN_LINK_INTERFACE_COUNT];

    // Queues
    struct k_fifo send_queue;
    struct k_fifo controller_event_queue;
    struct k_fifo service_discovery_queue;
    struct k_fifo unrouted_packets_queue;
    struct k_fifo rpc_queue;
    struct k_fifo event_queue;

    /**
     * @brief Heap pool to receive and send network packets using send() and recv()
     *
     * @allocator: I-RT, I-ST
     * @deallocator:
     */
    struct k_heap net_packets_heap;
    uint8_t __aligned(8) net_packets_heap_mem[CONFIG_NET_PACKET_HEAP_SIZE];

    /**
     * @brief Heap pool to keep partial packets stored, until the rest arrives on the network
     *
     * @allocator:
     * @deallocator:
     */
    struct k_heap net_partial_packets_heap;
    uint8_t __aligned(8) net_partial_packets_heap_mem[CONFIG_NET_PART_PACKET_HEAP_SIZE];

    /**
     * @brief Heap pool to keep unrouted packets until they're routed on the network again
     *
     * @allocator:
     * @deallocator:
     */
    struct k_heap unrouted_packets_heap;
    uint8_t __aligned(8) unrouted_packets_heap_mem[CONFIG_UNROUTED_PACKETS_HEAP_SIZE];

    /**
     * @brief Heap pool to keep local deserialized packets ready for processing
     *
     * @allocator:
     * @deallocator:
     */
    struct k_heap local_packets_heap;
    uint8_t __aligned(8) local_packets_heap_mem[CONFIG_LOCAL_PACKETS_HEAP_SIZE];

} cipher_daemon_t;

#endif // DAEMON_CONFIG_H