#ifndef COREKINECT_IFACE_UTILS_ASSEMBLER_H
#define COREKINECT_IFACE_UTILS_ASSEMBLER_H

// Standard includes
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/sys/ring_buffer.h>

// Private Library includes
#include "utils/protocol.h"
#include "utils/assert.h"

/**
 * @enum assembler_state_t
 * @brief Enumerates state for an p_assembler instance.
 *
 * This enumeration is used internally by the module to handle assembly
 * steps sequentially.
 */
typedef enum
{
    ASSEMBLER_STATE_START_DELIMITER, /**< Searching for the packet 4-byte start delimiter. */
    ASSEMBLER_STATE_HEADER,          /**< Searching for the iface packet header. */
    ASSEMBLER_STATE_DATA,            /**< Searching for the user paylaod as defined in the header length. */
    ASSEMBLER_STATE_VALIDATE,        /**< Calculating crc32 on the packet to ensure data validity. */
    ASSEMBLER_STATE_COMPLETE,        /**< Packet assembled and ready to be consumed by caller. */

    ASSEMBLER_STATE_MAX
} assembler_state_t;

/**
 * @struct assembler_packet_entry_t
 * @brief Structure holding an iface packet and required metadata.
 */
typedef struct
{
    bool in_use;             /**< Used internally to keep track of used entries. */
    size_t payload_progress; /**< Indicates how much of the user payload has been processed. */
    iface_packet_t packet;   /**< Iface packet entry itself. */
} assembler_packet_entry_t;

/**
 * @struct assembler_t
 * @brief Structure holding objects needed for succesful packet assembly from a stream.
 *
 * This object is designed to assemble packets from a stream. This stream is represented by a ring buffer
 * to which the user can append to as they get chunks of data on an interface.
 *
 * When a packet is ready to be consumed it is added to the recv_msq, if the recv_msq is full, an
 * error will be printed to the LOG
 */
typedef struct
{
    bool initialized;
    assembler_state_t state; /**< Used to keep track of the assembler state. */

    assembler_packet_entry_t *p_current_packet;                           /**< Used to keep track of the current packet being worked on. */
    assembler_packet_entry_t packets[CONFIG_CK_IFACE_NUM_PACKET_BUFFERS]; /**< List of packet entries used by an assembler to place processed packets. */
    struct k_sem entries_sem;
    struct k_mutex queue_mutex;

    struct k_heap heap;                                                  /**< Heap used to allocated the packet's data field. */
    uint8_t __aligned(8) heap_mem[CONFIG_CK_IFACE_UART_STACK_HEAP_SIZE]; /**< Heap memory storage. */

    char recv_msgq_buffer[CONFIG_CK_IFACE_NUM_PACKET_BUFFERS * sizeof(assembler_packet_entry_t *)]; /**< Used to store pointers to processed packets. */
    struct k_msgq recv_msgq;                                                                        /**< Used to pass fully recevied packets to the user. */

    struct ring_buf ring_buffer;                                       /**< Used by the caller of the interface to place stream chunks. */
    uint8_t ring_buffer_storage[CONFIG_CK_IFACE_RECV_RING_BUFER_SIZE]; /**< Size of the ring buffer itself. */
} assembler_t;

/**
 * @brief Initializes all objects used by the assembler
 *
 * @param[in] p_assembler The assembler object
 * @return true If all objects were initialized succesfully
 * @return false If an error occurred, or an argument is null. Logged to console as ERR
 */
bool assembler_init(assembler_t *p_assembler);

/**
 * @brief Resets all objects used by the assembler and empties buffers
 *
 * @param[in] p_assembler The assembler object
 * @return true If the assembler was reset succesfully
 * @return false If an error occurred, or an argument is null. Logged to console as ERR
 */
bool assembler_reset(assembler_t *p_assembler);

/**
 * @brief Returns minimum data size needed in ring buffer to call assembler
 *
 * This allows the user to call process_event only when there's enough data for the
 * assembler to process, saving cycles on unecessary calls to the assembler when there's
 * not enough data to process
 *
 * @param[in] p_assembler The assembler object
 * @return size_t 0 if a NULL assembler was passed, expected size otherwise
 */
size_t assembler_get_recv_length(assembler_t *p_assembler);

/**
 * @brief Processes any data available in the ring buffer, 1 packet at the time
 *
 * The call will return after processing 1 packet, regardless of there being
 * more data in the ring buffer itself. This is so that this function doesn't
 * loop indefinitely and the caller has control over it
 *
 * @param[in] p_assembler The assembler object
 * @return true If the assembler processed the data in the ring buffer
 * @return false If an error occurred, or an argument is null. Logged to console as ERR
 */
bool assembler_process_data(assembler_t *p_assembler);

/**
 * @brief Get a fully assembled interface packet.
 *
 * This function sets a pointer to the next entry in the received packets list
 * so that the caller can process it.
 *
 * The packet must be freed after its not needed.
 *
 * @param[in]   p_assembler The assembler object
 * @param[out]  p_p_packet  The address of the pointer to be set
 * @param[in]   timeout_ms  Receive timeout
 * @return true If a packet was received succesfully, or a timeout occurred, in which case p_p_packet will be NULL
 * @return false If an error occurred, or an argument is null. Logged to console as ERR
 */
bool assembler_get_packet(assembler_t *p_assembler, iface_packet_t **p_p_packet, uint16_t timeout_ms);

/**
 * @brief Frees a packet entry in the assembler
 *
 * This function will deallocate the data field from the assemblers heap, and set
 * the entry to "not in use", so that it can be reused for future packets.
 *
 * @note Must be called after every call to @ref assembler_get_packet()
 *
 * @param[in] p_assembler The assembler object
 * @param[in] p_packet    The packet to be freed
 * @return true
 * @return false If an error occurred, or an argument is null. Logged to console as ERR
 */
bool assembler_free_packet(assembler_t *p_assembler, iface_packet_t *p_packet);

/**
 * @brief Packs an interface packet into a buffer, ready to be sent over the network
 *
 * @note Function calculates the crc32 of the payload and sets the field in the header
 *
 * @param[in]  p_assembler     The assembler object
 * @param[out] p_buffer        The buffer where the message will be packed
 * @param[in]  buffer_size     Size of the buffer where the message will be packed
 * @param[out] p_bytes_packed  The number of bytes packed into the buffer
 * @param[in]  p_packet        The packet we want to pack into the buffer
 * @return true If the packet was packed into the buffer
 * @return false If an error occurred, or an argument is null. Logged to console as ERR
 */
bool assembler_create_packet(assembler_t *p_assembler, uint8_t *p_buffer, size_t buffer_size, size_t *p_bytes_packed, iface_packet_t *p_packet);

#endif  // COREKINECT_IFACE_UTILS_ASSEMBLER_H