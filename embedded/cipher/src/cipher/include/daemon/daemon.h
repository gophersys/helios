#ifndef DAEMON_CONFIG_H
#define DAEMON_CONFIG_H

// Cipher includes
#include "config/daemon.h"
#include "config/default.h"
#include "protocol/protocol.h"
#include "transport/transport.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Interfaces
 *---------------------------------------------------------------------------------------------------*/
typedef struct {
    uint8_t id;               /*!< Unique Id for the interface */
    tal_config_t *cfg;        /*!< The TAL config for the interface */
    bool connected;           /*!< Used to indicate connection status */
    struct k_sem conn_sem;    /*!< Used to signal send/recv threads, from conn thread */
    struct k_sem disconn_sem; /*!< Used to signal conn thread, from send or recv threads */

    struct k_fifo encoded_packets_queue;  ///< Queue _used by the router thread to send encoded
                                          ///< packets out on the interface
                                          ///< @param cipher_packet_t
                                          ///< @heap unrouted_packets_heap

    struct k_fifo decoded_packets_queue;  ///< Queue used by the multiple daemon threads to send
                                          ///< decoded packets on the interface
                                          ///< @param cipher_packet_fifo_item_t
                                          ///< @heap local_packets_heap
} cipher_iface_t;

// Send and Recv threads are identical
typedef struct {
    k_tid_t id;
    struct k_thread data;
    K_THREAD_STACK_MEMBER(stack, TRANSPORT_THREAD_STACK_SIZE);
} cipher_iface_thread_info_t;

// Interface thread group (connect, send and recv)
typedef struct {
    cipher_iface_t iface;
    cipher_iface_thread_info_t connection_t;
    cipher_iface_thread_info_t send_t;
    cipher_iface_thread_info_t recv_t;
} cipher_iface_thread_group_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Registry
 *---------------------------------------------------------------------------------------------------*/
typedef struct {
    char name[CONFIG_CIPHER_NAME_LEN];
    uint16_t service_id;
    uint16_t device_id;
    uint8_t num_ops;
    uint8_t allowed_hops;
} cipher_service_t;

typedef struct {
    bool _used;
    bool local;
    cipher_iface_t *iface;
    cipher_service_t service;
} cipher_service_entry_t;

typedef struct {
    cipher_service_entry_t entries[CONFIG_MAX_NUM_SERVICES];
} cipher_service_registry_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Fifo Types
 *---------------------------------------------------------------------------------------------------*/

// Used to signal daemon threads of where a packet came from
typedef struct {
    uintptr_t __k_reserved;
    cipher_packet_t packet;
    cipher_iface_t *iface;
} cipher_packet_fifo_item_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Deamon
 *---------------------------------------------------------------------------------------------------*/
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
    K_THREAD_STACK_MEMBER(ctrl_t_stack, 4096);

    k_tid_t sd_t_id;
    struct k_thread sd_t_data;
    K_THREAD_STACK_MEMBER(sd_t_stack, 2048);

    k_tid_t router_t_id;
    struct k_thread router_t_data;
    K_THREAD_STACK_MEMBER(router_t_stack, 2048);

    k_tid_t rpc_t_id;
    struct k_thread rpc_t_data;
    K_THREAD_STACK_MEMBER(rpc_t_stack, 2048);

    k_tid_t event_t_id;
    struct k_thread event_t_data;
    K_THREAD_STACK_MEMBER(event_t_stack, 2048);

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
    struct k_fifo admin_packet_queue;

    /**
     * @implements ctrl_event_t
     */
    struct k_fifo ctrl_event_queue;

    // Services
    struct k_fifo sd_packet_queue;

    struct k_fifo sd_iface_conn_queue;  ///< Queue used by the service discovery thread to
                                        ///< receive connected interface updates
                                        ///< @param cipher_iface_t *
                                        ///< @heap No heap, passing pointer

    struct k_fifo sd_iface_disconn_queue;  ///< Queue used by the service discovery thread to
                                           ///< receive disconnected interface updates
                                           ///< @param cipher_iface_t *
                                           ///< @heap No heap, passing pointer

    // Router
    struct k_fifo unrouted_packets_queue;

    // RPC
    struct k_fifo rpc_packet_queue;

    // Events
    struct k_fifo event_packet_queue;

    /*-----------------------------------------------
     *                                          Heaps
     *---------------------------------------------*/

    /**
     * @brief Heap pool to send events to daemon controller thread
     *
     * @allocator: I-RT, I-ST
     * @deallocator:
     */
    struct k_heap ctrl_events_heap;
    uint8_t __aligned(8) ctrl_events_heap_mem[1024];

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

    /*-----------------------------------------------
     *                                     Registries
     *---------------------------------------------*/
    cipher_service_registry_t service_registry;
} cipher_daemon_t;

#endif  // DAEMON_CONFIG_H