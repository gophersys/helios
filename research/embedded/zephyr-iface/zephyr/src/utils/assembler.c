#include "assembler.h"
#include <corekinect/iface/iface.h>

// Standard includes
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/crc.h>
#include <zephyr/sys/ring_buffer.h>

// Lib private includes
#include "protocol.h"

LOG_MODULE_REGISTER(uart_assembler, CONFIG_CK_IFACE_LIB_ASSEMBLER_DEBUG_LEVEL);

/**
 * @def ASSEMBLER_ALLOC_TIMEOUT_MS
 * @brief Timeout in milliseconds for assembler allocation operations.
 */
#define ASSEMBLER_ALLOC_TIMEOUT_MS 10

/**
 * @brief Returns a free entry in the array of packets of the assembler
 *
 * @param[in] p_assembler The assembler object
 * @return assembler_packet_entry_t* Pointer to free entry
 */
static assembler_packet_entry_t *_fp_new_recv_entry(assembler_t *p_assembler);
// static int _get_entry_index_from_packet(assembler_t *p_assembler, iface_packet_t *p_packet);

/**
 * @brief Returns the entry to which a specific interface packet belongs.
 *
 * This function exists so that when the user free's a packet, we can locate
 * the entry that this packet belongs to in the assembler
 *
 * @param[in] packet The iface packet passed by the user
 * @return assembler_packet_entry_t* Pointer to packet entry
 */
static assembler_packet_entry_t *_fp_get_entry_from_packet(iface_packet_t *p_packet);

/**
 * @defgroup AssemblerStateFunctions Assembler State Handlers
 * @brief Functions handling each state of the assembler.
 *
 * These functions are part of the assembler's state machine, with each handling a specific state.
 * They collectively manage the assembly process of incoming data, validation, and finalization.
 */

/**
 * @ingroup AssemblerStateFunctions
 */
static bool _assemble_delimiter(assembler_t *p_assembler);

/**
 * @ingroup AssemblerStateFunctions
 */
static bool _assemble_header(assembler_t *p_assembler);

/**
 * @ingroup AssemblerStateFunctions
 */
static bool _assemble_data(assembler_t *p_assembler);

/**
 * @ingroup AssemblerStateFunctions
 */
static bool _validate_data(assembler_t *p_assembler);

/**
 * @ingroup AssemblerStateFunctions
 */
static bool _assemble_complete(assembler_t *p_assembler);

bool assembler_init(assembler_t *p_assembler)
{
    ASSERT_NOT_NULL(p_assembler);

    if (!p_assembler->initialized)
    {
        p_assembler->state = ASSEMBLER_STATE_START_DELIMITER;
        k_heap_init(&p_assembler->heap, p_assembler->heap_mem, sizeof(p_assembler->heap_mem));
        k_msgq_init(&p_assembler->recv_msgq, p_assembler->recv_msgq_buffer, sizeof(assembler_packet_entry_t *), CONFIG_CK_IFACE_NUM_PACKET_BUFFERS);
        ring_buf_init(&p_assembler->ring_buffer, sizeof(p_assembler->ring_buffer_storage), p_assembler->ring_buffer_storage);
        k_sem_init(&p_assembler->entries_sem, 1, 1);
        p_assembler->initialized = true;
    }

    return true;
}

bool assembler_reset(assembler_t *p_assembler)
{
    ASSERT_NOT_NULL(p_assembler);
    ASSERT_INITIALIZED(p_assembler->initialized);

    // Free any allocated p_data in each packet entry
    for (int i = 0; i < ARRAY_SIZE(p_assembler->packets); i++)
    {
        if (p_assembler->packets[i].packet.p_data != NULL)
        {
            k_heap_free(&p_assembler->heap, p_assembler->packets[i].packet.p_data);
            p_assembler->packets[i].packet.p_data = NULL; // Reset pointer after freeing
        }
    }

    // Reset the state
    p_assembler->state = ASSEMBLER_STATE_START_DELIMITER;

    // Reinitialize the heap
    // k_heap_init(&p_assembler->heap, p_assembler->heap_mem, sizeof(p_assembler->heap_mem));

    // Reset the message queue by purging all remaining messages
    k_msgq_purge(&p_assembler->recv_msgq);

    // Reinitialize the message queue
    // k_msgq_init(&p_assembler->recv_msgq, p_assembler->recv_msgq_buffer, sizeof(assembler_packet_entry_t *), CONFIG_CK_IFACE_NUM_PACKET_BUFFERS);

    // Reset and reinitialize the ring buffer
    ring_buf_reset(&p_assembler->ring_buffer);
    // ring_buf_init(&p_assembler->ring_buffer, sizeof(p_assembler->ring_buffer_storage), p_assembler->ring_buffer_storage);

    return true;
}

size_t assembler_get_recv_length(assembler_t *p_assembler)
{
    ASSERT_NOT_NULL(p_assembler);
    ASSERT_INITIALIZED(p_assembler->initialized);

    switch (p_assembler->state)
    {
        case ASSEMBLER_STATE_START_DELIMITER:
        case ASSEMBLER_STATE_VALIDATE:
        case ASSEMBLER_STATE_COMPLETE:
            // If the packet is being validated or is complete we can say that the next packet is ready to
            // be processed, and so we return the size of the start delimiter
            return sizeof(IFACE_PACKET_START_DELIMITER);
        case ASSEMBLER_STATE_HEADER:
            return sizeof(p_assembler->packets->packet.header);
        case ASSEMBLER_STATE_DATA:
            return p_assembler->p_current_packet->packet.header.length - p_assembler->p_current_packet->payload_progress;
        default:
            LOG_ERR("Unknown assembler state %d", p_assembler->state);
            return 0;
    }
}

bool assembler_process_data(assembler_t *p_assembler)
{
    bool should_process = true;
    while (should_process)
    {
        switch (p_assembler->state)
        {
            case ASSEMBLER_STATE_START_DELIMITER:
                LOG_DBG("%s", "ASSEMBLER_STATE_START_DELIMITER");
                if (!_assemble_delimiter(p_assembler))
                {
                    return false;
                }
                break;
            case ASSEMBLER_STATE_HEADER:
                LOG_DBG("%s", "ASSEMBLER_STATE_HEADER");
                if (!_assemble_header(p_assembler))
                {
                    return false;
                }
                break;
            case ASSEMBLER_STATE_DATA:
                LOG_DBG("%s", "ASSEMBLER_STATE_DATA");
                if (!_assemble_data(p_assembler))
                {
                    return false;
                }
                break;
            case ASSEMBLER_STATE_VALIDATE:
                LOG_DBG("%s", "ASSEMBLER_STATE_VALIDATE");
                if (!_validate_data(p_assembler))
                {
                    return false;
                }
                break;
            case ASSEMBLER_STATE_COMPLETE:
                LOG_DBG("%s", "ASSEMBLER_STATE_COMPLETE");
                if (!_assemble_complete(p_assembler))
                {
                    return false;
                }

                should_process = false; // We're done processing 1 packet so we can exit

                break;
            default:
                LOG_ERR("Unknown assembler state: %d", p_assembler->state);
                return false;
        }

        // If we're not done processing a packet, check if we should exit the loop
        if (should_process)
        {
            bool zero_data_packet = p_assembler->state == ASSEMBLER_STATE_DATA && p_assembler->p_current_packet->packet.header.length == 0 ? true : false;
            bool data_in_ring_buffer = ring_buf_size_get(&p_assembler->ring_buffer) > 0 ? true : false;
            bool finishing_packet = p_assembler->state >= ASSEMBLER_STATE_VALIDATE ? true : false;

            if (!zero_data_packet && !data_in_ring_buffer && !finishing_packet)
            {
                should_process = false;
            }
        }
    }

    return true;
}

bool assembler_get_packet(assembler_t *p_assembler, iface_packet_t **p_p_packet, uint16_t timeout_ms)
{
    ASSERT_NOT_NULL(p_assembler);
    ASSERT_NOT_NULL(p_p_packet);

    *p_p_packet = NULL;

    // Retrieve the packet p_entry from the queue with a timeout
    assembler_packet_entry_t *p_entry = NULL;
    int err = k_msgq_get(&p_assembler->recv_msgq, &p_entry, K_MSEC(timeout_ms));
    switch (err)
    {
        case 0:
            if (p_entry == NULL)
            {
                LOG_ERR("%s", "Received unexpected null entry from message queue");
                return false;
            }

            *p_p_packet = &(p_entry->packet);
            return true;

        case -ENOMSG:  // Returned without waiting
            if (timeout_ms == 0)
            {
                LOG_WRN("%s", "A timeout period of 0 was given, and no messages were available");
                return true;
            }

            LOG_WRN("%s", "Unexpected and unknown error. ENOMSG error should only be returned with a timeout of 0");
            return false;

        case -EAGAIN:  // Waiting period timed out
            return true;

        default:  // Other errors
            LOG_ERR("Error receiving message: %d, errno: %s", err, strerror(errno));
            return false;
    }
}

bool assembler_free_packet(assembler_t *p_assembler, iface_packet_t *p_packet)
{
    ASSERT_NOT_NULL(p_assembler);
    ASSERT_NOT_NULL(p_packet);

    k_sem_take(&p_assembler->entries_sem, K_FOREVER);
    assembler_packet_entry_t *p_entry = _fp_get_entry_from_packet(p_packet);
    ASSERT_NOT_NULL(p_entry);

    k_heap_free(&p_assembler->heap, p_entry->packet.p_data);

    // Set the packet clean so it can be reused
    p_entry->in_use = false;
    p_entry->packet.p_data = NULL;

    k_sem_give(&p_assembler->entries_sem);

    return true;
}

bool assembler_create_packet(assembler_t *p_assembler, uint8_t *p_buffer, size_t buffer_size, size_t *p_bytes_packed, iface_packet_t *p_packet)
{
    ASSERT_NOT_NULL(p_assembler);
    ASSERT_NOT_NULL(p_buffer);
    ASSERT_NOT_NULL(p_bytes_packed);
    ASSERT_NOT_NULL(p_packet);

    // Calculate total packet size: header + data
    size_t total_packet_size = sizeof(iface_packet_header_t) + p_packet->header.length;
    if (buffer_size < total_packet_size)
    {
        LOG_ERR("Buffer too small. Required: %zu, Provided: %zu", total_packet_size, buffer_size);
        return false;
    }

    // Start packing the packet
    size_t offset = 0;

    // 1. Pack the Start Delimiter
    p_packet->start_delimiter = IFACE_PACKET_START_DELIMITER;
    uint32_t start_delimiter_net = htonl(p_packet->start_delimiter);
    memcpy(p_buffer + offset, &start_delimiter_net, sizeof(start_delimiter_net));
    offset += sizeof(start_delimiter_net);

    // 2. Pack the Header (excluding CRC for now)
    uint32_t crc_placeholder = 0;
    memcpy(p_buffer + offset, &crc_placeholder, sizeof(crc_placeholder));
    offset += sizeof(crc_placeholder);

    p_buffer[offset++] = p_packet->header.type;
    p_buffer[offset++] = p_packet->header.sequence_num;

    uint16_t length_net_order = htons(p_packet->header.length);
    memcpy(p_buffer + offset, &length_net_order, sizeof(length_net_order));
    offset += sizeof(length_net_order);

    // 3. Pack the Data
    memcpy(p_buffer + offset, p_packet->p_data, p_packet->header.length);
    offset += p_packet->header.length;

    // 4. Calculate and insert CRC32
    // CRC is calculated on the entire packet excluding the start delimiter
    uint32_t calculated_crc = crc32_ieee(p_buffer + sizeof(start_delimiter_net), offset - sizeof(start_delimiter_net));
    uint32_t crc_net_order = htonl(calculated_crc);
    memcpy(p_buffer + sizeof(start_delimiter_net), &crc_net_order, sizeof(crc_net_order));

    // Update the total number of bytes packed
    *p_bytes_packed = offset;

    return true;
}

static bool _assemble_delimiter(assembler_t *p_assembler)
{
    ASSERT_NOT_NULL(p_assembler);

    k_sem_take(&p_assembler->entries_sem, K_FOREVER);
    assembler_packet_entry_t *p_entry = _fp_new_recv_entry(p_assembler);
    ASSERT_NOT_NULL(p_entry);

    uint32_t peek_buffer;
    size_t bytes_processed = 0;

    while (bytes_processed <= ring_buf_size_get(&p_assembler->ring_buffer) - sizeof(peek_buffer))
    {
        // Peek four bytes from the ring buffer
        if (ring_buf_peek(&p_assembler->ring_buffer, (uint8_t *)&peek_buffer, sizeof(peek_buffer)) == sizeof(peek_buffer))
        {
            // Compare the bytes directly without byte order conversion
            if (peek_buffer == htonl(IFACE_PACKET_START_DELIMITER))
            {
                // Found the start delimiter
                p_entry->packet.start_delimiter = ntohl(peek_buffer);  // Store in host byte order

                // Discard the bytes up to and including the delimiter from the ring buffer
                ring_buf_get(&p_assembler->ring_buffer, NULL, bytes_processed + sizeof(peek_buffer));

                // Setup for next state
                p_assembler->state = ASSEMBLER_STATE_HEADER;
                p_assembler->p_current_packet = p_entry;
                p_assembler->p_current_packet->in_use = true;

                k_sem_give(&p_assembler->entries_sem);

                return true;
            }

            // Update the ring buffer position to discard one byte and try again
            uint8_t dummy;
            ring_buf_get(&p_assembler->ring_buffer, &dummy, sizeof(dummy));
            bytes_processed++;
        }
        else
        {
            // Not enough p_data for a full delimiter check, exit loop
            break;
        }
    }

    // If we reach here, the delimiter wasn't found. Discard all processed bytes
    if (bytes_processed > 0)
    {
        ring_buf_get(&p_assembler->ring_buffer, NULL, bytes_processed);
    }

    k_sem_give(&p_assembler->entries_sem);

    return true;
}

static bool _assemble_header(assembler_t *p_assembler)
{
    ASSERT_NOT_NULL(p_assembler);
    ASSERT_NOT_NULL(p_assembler->p_current_packet);

    size_t header_size = sizeof(iface_packet_header_t);

    // Ensure there's enough p_data for the entire header
    if (ring_buf_size_get(&p_assembler->ring_buffer) < header_size)
    {
        return true;
    }

    uint8_t header_buffer[header_size];
    if (ring_buf_peek(&p_assembler->ring_buffer, header_buffer, header_size) == header_size)
    {
        // Get the current packet entry
        assembler_packet_entry_t *p_entry = p_assembler->p_current_packet;

        // Extract and store the header fields in host byte order
        p_entry->packet.header.crc32 = ntohl(*(uint32_t *)(header_buffer));       // First 4 bytes: CRC32
        p_entry->packet.header.type = header_buffer[4];                           // Next byte: Type
        p_entry->packet.header.sequence_num = header_buffer[5];                   // Next byte: Sequence Number
        p_entry->packet.header.length = ntohs(*(uint16_t *)(header_buffer + 6));  // Last 2 bytes: Length

        // Discard the header bytes from the ring buffer
        ring_buf_get(&p_assembler->ring_buffer, NULL, header_size);

        // Setup for next state
        p_assembler->state = ASSEMBLER_STATE_DATA;

        LOG_DBG("Type: %d, Seq: %d, Len: %d crc32: %u",
                p_entry->packet.header.type,
                p_entry->packet.header.sequence_num,
                p_entry->packet.header.length,
                p_entry->packet.header.crc32);
    }

    return true;
}

static bool _assemble_data(assembler_t *p_assembler)
{
    ASSERT_NOT_NULL(p_assembler);
    ASSERT_NOT_NULL(p_assembler->p_current_packet);

    assembler_packet_entry_t *p_entry = p_assembler->p_current_packet;

    if (p_entry->packet.header.length > 0)
    {
        size_t payload_size = p_entry->packet.header.length;
        size_t buffer_size = ring_buf_size_get(&p_assembler->ring_buffer);
        size_t remaining_payload = payload_size - p_entry->payload_progress;
        size_t bytes_to_copy = MIN(remaining_payload, buffer_size);

        // Check if buffer allocation is needed
        if (p_entry->packet.p_data == NULL)
        {
            p_entry->packet.p_data = k_heap_alloc(&p_assembler->heap, payload_size, K_FOREVER);
            if (p_entry->packet.p_data == NULL)
            {
                LOG_ERR(
                    "Malloc failed for packet payload with timeout %d ms."
                    "Increase Kconfig option CONFIG_CK_IFACE_UART_STACK_HEAP_SIZE, current value: %d",
                    ASSEMBLER_ALLOC_TIMEOUT_MS,
                    CONFIG_CK_IFACE_UART_STACK_HEAP_SIZE);

                return false;
            }
        }

        // Copy the payload bytes into the buffer
        size_t copied_bytes = ring_buf_get(&p_assembler->ring_buffer, p_entry->packet.p_data + p_entry->payload_progress, bytes_to_copy);
        p_entry->payload_progress += copied_bytes;

        // Check if the entire payload has been copied
        if (p_entry->payload_progress == payload_size)
        {
            // Setup for next state
            p_assembler->state = ASSEMBLER_STATE_VALIDATE;
        }
    }
    else
    {
        // No payload packet, just move on to the next state
        p_assembler->state = ASSEMBLER_STATE_VALIDATE;
    }

    return true;
}

static bool _validate_data(assembler_t *p_assembler)
{
    ASSERT_NOT_NULL(p_assembler);
    ASSERT_NOT_NULL(p_assembler->p_current_packet);

    assembler_packet_entry_t *p_entry = p_assembler->p_current_packet;

    // Convert necessary fields to network byte order
    uint16_t length_net_order = htons(p_entry->packet.header.length);

    // Initialize CRC calculation
    // Start with a placeholder for CRC as it's included in the calculation, even though the actual value is determined later.
    uint32_t crc_placeholder = 0;
    uint32_t calculated_crc = crc32_ieee((const uint8_t *)&crc_placeholder, sizeof(crc_placeholder));

    // Update CRC calculation sequentially for each part of the packet
    calculated_crc = crc32_ieee_update(calculated_crc, (const uint8_t *)&p_entry->packet.header.type, sizeof(p_entry->packet.header.type));
    calculated_crc = crc32_ieee_update(calculated_crc, (const uint8_t *)&p_entry->packet.header.sequence_num, sizeof(p_entry->packet.header.sequence_num));
    calculated_crc = crc32_ieee_update(calculated_crc, (const uint8_t *)&length_net_order, sizeof(length_net_order));

    // Update CRC with the actual data. Convert length back to host order for payload length as crc32_ieee_update expects the actual length
    if (p_entry->packet.header.length > 0)
    {
        calculated_crc = crc32_ieee_update(calculated_crc, (const uint8_t *)p_entry->packet.p_data, p_entry->packet.header.length);
    }

    // Compare the calculated CRC with the CRC in the header
    if (calculated_crc != p_entry->packet.header.crc32)
    {
        LOG_ERR("CRC mismatch: calculated %u, expected %u. This could indicate a packet data integrity issue",
                calculated_crc, p_entry->packet.header.crc32);

        return false;
    }

    LOG_DBG("CRC: %u", calculated_crc);

    // Setup for next state
    p_assembler->state = ASSEMBLER_STATE_COMPLETE;

    return true;
}

static bool _assemble_complete(assembler_t *p_assembler)
{
    ASSERT_NOT_NULL(p_assembler);
    ASSERT_NOT_NULL(p_assembler->p_current_packet);

    // Add pointer to packet to queue
    int err = k_msgq_put(&p_assembler->recv_msgq, &(p_assembler->p_current_packet), K_NO_WAIT);
    if (err != 0)
    {
        LOG_ERR(
            "Receive message queue is full. This means (this) host is not consuming "
            "packets on this interface as quickly as the remote end is sending packets. "
            "Increase Kconfig option CONFIG_CK_IFACE_NUM_PACKET_BUFFERS, current value: %d "
            "or decrease the data throughput of the remote end.",
            CONFIG_CK_IFACE_NUM_PACKET_BUFFERS);

        return false;
    }

    // Zero out packet bufffer & info
    // p_assembler->p_current_packet->in_use = false;
    p_assembler->p_current_packet->payload_progress = 0;
    p_assembler->p_current_packet = NULL;

    // Reset the assembler state
    p_assembler->state = ASSEMBLER_STATE_START_DELIMITER;

    return true;
}

static assembler_packet_entry_t *_fp_new_recv_entry(assembler_t *p_assembler)
{
    for (int i = 0; i < ARRAY_SIZE(p_assembler->packets); i++)
    {
        if (!p_assembler->packets[i].in_use)  // Find the first packet that is not in use
        {
            return &p_assembler->packets[i];        // Return a pointer to the packet
        }
    }

    LOG_ERR(
        "Not enough packet entries in assembler for new packet. "
        "Increase Kconfig option CONFIG_CK_IFACE_NUM_PACKET_BUFFERS, current value: %d",
        CONFIG_CK_IFACE_NUM_PACKET_BUFFERS);

    return NULL;
}

static assembler_packet_entry_t *_fp_get_entry_from_packet(iface_packet_t *p_packet)
{
    // Calculate the address of the assembler_packet_entry_t
    // This calculation depends on the memory layout of your structures
    // Here's an example assuming assembler_packet_entry_t is directly before iface_packet_t in memory
    return (assembler_packet_entry_t *)((uint8_t *)p_packet - offsetof(assembler_packet_entry_t, packet));
}