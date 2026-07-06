// Standard includes
#include <stdio.h>
#include <string.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include <corekinect/cipher/protocol.h>
#include <corekinect/cipher/stream.h>
#include <corekinect/iface/iface.h>

#include "config/default.h"
#include "daemon/daemon.h"
#include "daemon/fifo.h"
#include "daemon/registry.h"
#include "utils/err.h"

// Private include
#include "interface.h"
#include "threads.h"

LOG_MODULE_REGISTER(stream, CONFIG_CK_CIPHER_STREAM_LOG_LEVEL);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

#define FNV1A_OFFSET_BASIS 2166136261u
#define FNV1A_PRIME        16777619u

// Stream reassembly + completion state is owned by the daemon
// (cipher_daemon_t::stream_state), NOT file-scope globals, so multiple daemon
// instances in one image each keep their own independent stream state. The
// mutex is initialised in cipher_daemon_init via k_mutex_init.

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Checksum
 *---------------------------------------------------------------------------------------------------*/
uint32_t cipher_stream_fnv1a(uint32_t seed, const uint8_t *data, size_t length) {
    uint32_t hash = seed;
    for (size_t i = 0; i < length; i++) {
        hash ^= data[i];
        hash *= FNV1A_PRIME;
    }
    return hash;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                 Send
 *---------------------------------------------------------------------------------------------------*/
static bool send_stream_packet(cipher_daemon_t *d, cipher_iface_t *iface, uint16_t dst,
                               uint16_t stream_id, uint8_t flag, uint16_t seq,
                               const uint8_t *payload, uint16_t payload_len) {
    cipher_packet_fifo_item_t *item = alloc_packet_fifo_item(d, payload_len);
    if (!item) {
        return false;
    }

    cipher_packet_t *packet = &item->packet;
    packet->header.source_id = d->device_id;
    packet->header.destination_id = dst;
    packet->header.service_id = stream_id;  // carries the stream id for correlation
    packet->header.operation_id = 0;
    packet->header.payload_len = payload_len;
    packet->header.sequence_num = seq;
    packet->header.type = CIPHER_PACKET_TYPE_STREAM;
    packet->header.hop_count = 0;
    packet->header.flags = flag;

    if (payload_len > 0) {
        memcpy(packet->payload, payload, payload_len);
    }

    // Back-pressured by the packet heap: alloc above blocks when the send
    // thread has not yet drained enough in-flight packets.
    k_fifo_put(&iface->decoded_packets_queue, item);
    return true;
}

int32_t cipher_stream_send(cipher_daemon_t *d, uint16_t device_id, uint16_t stream_id,
                           const uint8_t *data, uint32_t length, uint16_t chunk_size) {
    cipher_iface_t *iface = registry_get_iface(d, device_id);
    if (!iface) {
        LOG_ERR("stream: no route to device 0x%04x", device_id);
        return -1;
    }

    // Leave headroom so header + chunk stays within one framed packet.
    const uint16_t max_chunk = CONFIG_MAX_PAYLOAD_SIZE - sizeof(cipher_header_t) - 4;
    if (chunk_size == 0 || chunk_size > max_chunk) {
        chunk_size = max_chunk;
    }

    // START: total length + stream id
    uint8_t start_payload[6];
    memcpy(&start_payload[0], &length, sizeof(uint32_t));
    memcpy(&start_payload[4], &stream_id, sizeof(uint16_t));
    if (!send_stream_packet(d, iface, device_id, stream_id, CIPHER_FLAG_STREAM_START, 0,
                            start_payload, sizeof(start_payload))) {
        return -1;
    }

    // DATA: ordered chunks
    uint32_t sent = 0;
    uint16_t seq = 1;
    while (sent < length) {
        uint16_t n = (uint16_t)MIN((uint32_t)chunk_size, length - sent);
        if (!send_stream_packet(d, iface, device_id, stream_id, CIPHER_FLAG_STREAM_DATA, seq,
                                data + sent, n)) {
            return (int32_t)sent;
        }
        sent += n;
        seq++;
    }

    // END: declared length + checksum for verification
    uint32_t checksum = cipher_stream_fnv1a(FNV1A_OFFSET_BASIS, data, length);
    uint8_t end_payload[8];
    memcpy(&end_payload[0], &length, sizeof(uint32_t));
    memcpy(&end_payload[4], &checksum, sizeof(uint32_t));
    send_stream_packet(d, iface, device_id, stream_id, CIPHER_FLAG_STREAM_END, seq,
                       end_payload, sizeof(end_payload));

    return (int32_t)sent;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                          Last Stream
 *---------------------------------------------------------------------------------------------------*/
bool cipher_stream_get_last_rx(cipher_daemon_t *d, cipher_stream_rx_stats_t *out) {
    cipher_stream_state_t *s = &d->stream_state;
    bool valid;

    k_mutex_lock(&s->mutex, K_FOREVER);
    valid = s->last_rx_valid;
    if (valid) {
        *out = s->last_rx;
    }
    k_mutex_unlock(&s->mutex);

    return valid;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Receive (Reassy)
 *---------------------------------------------------------------------------------------------------*/
static void handle_stream_packet(cipher_daemon_t *d, cipher_packet_t *packet) {
    cipher_stream_state_t *s = &d->stream_state;
    const uint8_t *payload = (const uint8_t *)packet->payload;
    const uint16_t flags = packet->header.flags;

    if (flags & CIPHER_FLAG_STREAM_START) {
        k_mutex_lock(&s->mutex, K_FOREVER);
        s->rx.in_progress = true;
        memcpy(&s->rx.total_len, &payload[0], sizeof(uint32_t));
        memcpy(&s->rx.stream_id, &payload[4], sizeof(uint16_t));
        s->rx.received_len = 0;
        s->rx.num_chunks = 0;
        s->rx.checksum = FNV1A_OFFSET_BASIS;
        s->rx.start_time = k_uptime_get();
        k_mutex_unlock(&s->mutex);
        LOG_INF("stream %u START: expecting %u bytes", s->rx.stream_id, s->rx.total_len);

    } else if (flags & CIPHER_FLAG_STREAM_DATA) {
        k_mutex_lock(&s->mutex, K_FOREVER);
        s->rx.received_len += packet->header.payload_len;
        s->rx.num_chunks++;
        s->rx.checksum = cipher_stream_fnv1a(s->rx.checksum, payload, packet->header.payload_len);
        k_mutex_unlock(&s->mutex);

    } else if (flags & CIPHER_FLAG_STREAM_END) {
        uint32_t declared_len = 0;
        uint32_t declared_checksum = 0;
        memcpy(&declared_len, &payload[0], sizeof(uint32_t));
        memcpy(&declared_checksum, &payload[4], sizeof(uint32_t));

        k_mutex_lock(&s->mutex, K_FOREVER);
        int64_t duration = k_uptime_get() - s->rx.start_time;
        s->last_rx.completion_id = ++s->completion_id;
        s->last_rx.stream_id = s->rx.stream_id;
        s->last_rx.total_len = s->rx.total_len;
        s->last_rx.received_len = s->rx.received_len;
        s->last_rx.num_chunks = s->rx.num_chunks;
        s->last_rx.checksum = s->rx.checksum;
        s->last_rx.checksum_ok =
            (s->rx.checksum == declared_checksum) && (s->rx.received_len == declared_len);
        s->last_rx.duration_ms = duration;
        s->last_rx_valid = true;
        s->rx.in_progress = false;
        cipher_stream_rx_stats_t snapshot = s->last_rx;
        k_mutex_unlock(&s->mutex);

        uint32_t kbps = (duration > 0) ? (uint32_t)((int64_t)snapshot.received_len * 1000 / duration / 1024) : 0;
        LOG_INF("stream %u END: %u bytes / %u chunks in %lld ms = %u KiB/s, checksum %s",
                snapshot.stream_id, snapshot.received_len, snapshot.num_chunks,
                duration, kbps, snapshot.checksum_ok ? "OK" : "MISMATCH");
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Thread
 *---------------------------------------------------------------------------------------------------*/
void cipher_stream_thread(void *arg0, void *arg1, void *arg2) {
    ARG_UNUSED(arg1);
    ARG_UNUSED(arg2);
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;

    while (true) {
        cipher_packet_fifo_item_t *fifo_item = k_fifo_get(&d->stream_packet_event_queue, K_FOREVER);
        __ASSERT(fifo_item, "Null item on stream_packet_event_queue, daemon %d", d->id);
        handle_stream_packet(d, &fifo_item->packet);
        free_packet_fifo_item(d, fifo_item);
    }
}
