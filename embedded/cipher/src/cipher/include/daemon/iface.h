#ifndef IFACE_H
#define IFACE_H

#include "config/default.h"
#include "transport/transport.h"

/**
 * @brief Objects needed by a single iface instance
 */
typedef struct {
    uint8_t id;               /*!< Unique Id for the interface */
    tal_config_t *cfg;        /*!< The TAL config for the interface */
    bool connected;           /*!< Used to indicate connection status */
    struct k_sem conn_sem;    /*!< Used to signal send/recv threads, from conn thread */
    struct k_sem disconn_sem; /*!< Used to signal conn thread, from send or recv threads */

    struct k_fifo encoded_packets_queue;  ///< Queue used by any interfaces recv thread to route
                                          ///< raw packets out on this interface
                                          ///< @param cipher_router_packet_fifo_item_t
                                          ///< @heap unrouted_packets_heap

    struct k_fifo decoded_packets_queue;  ///< Queue used by the multiple daemon threads to send
                                          ///< decoded packets on the interface
                                          ///< @param cipher_packet_fifo_item_t
                                          ///< @heap local_packets_heap
} cipher_iface_t;

/**
 * @brief Holds all thread data needed by the kernel
 */
typedef struct {
    k_tid_t id;
    struct k_thread data;
    K_THREAD_STACK_MEMBER(stack, TRANSPORT_THREAD_STACK_SIZE);
} cipher_iface_thread_info_t;

/**
 * @brief Each interface has 3 threads, and their info is grouped here
 */
typedef struct {
    cipher_iface_t iface;                    /*!< The iface that corresponds to this group */
    cipher_iface_thread_info_t connection_t; /*!< Manages connection/disconnection & cleanup */
    cipher_iface_thread_info_t send_t;       /*!< Sends encoded/decoded packages on iface */
    cipher_iface_thread_info_t recv_t;       /*!< Recvs encoded packages on iface */
} cipher_iface_thread_group_t;

#endif