#ifndef CIPHER_IFACE_H
#define CIPHER_IFACE_H

// Standard includes
#include <stdbool.h>
#include <stddef.h>

// Zephyr includes
#include <zephyr/kernel.h>

// CoreKinect includes
#include <corekinect/iface/iface.h>

/**
 * @struct cipher_iface_t
 * @brief Objects needed by a single iface instance
 */
typedef struct {
    uint8_t id;               /*!< Unique Id for the interface */
    iface_t *cfg;        /*!< The TAL config for the interface */
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
 * @struct cipher_iface_thread_info_t
 * @brief Holds all thread data needed by the kernel
 */
typedef struct {
    k_tid_t id;
    struct k_thread data;
    K_THREAD_STACK_MEMBER(stack, CONFIG_CK_CIPHER_IFACE_THREAD_STACK_SIZE);
} cipher_iface_thread_info_t;

/**
 * @struct cipher_iface_device_entry_t
 * @brief
 */
typedef struct {
    bool _used;
    uint16_t device_id;
} cipher_iface_device_entry_t;  // TODO: Is this struct really needed?

/**
 * @brief Each interface has 3 threads, and their info is grouped here
 */
typedef struct {
    cipher_iface_t iface; /*!< The iface that corresponds to this group */
    cipher_iface_device_entry_t device_entries[CONFIG_CK_CIPHER_MAX_NUM_DEVICES_PER_IFACE];
    cipher_iface_thread_info_t connection_t; /*!< Manages connection/disconnection & cleanup */
    cipher_iface_thread_info_t send_t;       /*!< Sends encoded/decoded packages on iface */
    cipher_iface_thread_info_t recv_t;       /*!< Recvs encoded packages on iface */
} cipher_iface_thread_group_t;

#endif  // CIPHER_IFACE_H