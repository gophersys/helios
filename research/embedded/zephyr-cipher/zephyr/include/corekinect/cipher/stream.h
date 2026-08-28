#ifndef CIPHER_STREAM_H
#define CIPHER_STREAM_H

// Standard includes
#include <stddef.h>
#include <stdint.h>

// CoreKinect includes
#include <corekinect/cipher/config.h>

// Forward declaration — the full daemon definition lives in daemon/daemon.h,
// which the implementation includes; callers only need the pointer type.
typedef struct cipher_daemon cipher_daemon_t;

/**
 * Cipher stream API — large multi-packet data transfers.
 *
 * A stream splits a big buffer into ordered chunks carried by STREAM packets
 * (header.sequence_num = chunk index). Framing:
 *   START (flag) : payload = { uint32 total_len, uint16 stream_id }
 *   DATA  (flag) : payload = raw chunk bytes, sequence_num = index
 *   END   (flag) : payload = { uint32 total_len, uint32 fnv1a_checksum }
 *
 * The receiver (daemon stream thread) reassembles / verifies and reports
 * throughput. For benchmarking, the receiver counts bytes + folds a running
 * FNV-1a checksum instead of storing the whole blob (so a 1 MB stream does not
 * need 1 MB of RAM on the target).
 */

/**
 * @brief Send a buffer as a cipher stream to a remote device.
 *
 * Blocks until every chunk has been queued to the transport. Chunk size is
 * clamped to the protocol's max payload.
 *
 * @param d          The daemon
 * @param device_id  Remote device to stream to
 * @param stream_id  Caller-chosen id to correlate START/DATA/END
 * @param data       Source buffer
 * @param length     Number of bytes to stream
 * @param chunk_size Desired bytes per DATA packet (clamped to max payload)
 * @return Number of bytes queued, or a negative value on error.
 */
int32_t cipher_stream_send(cipher_daemon_t *d, uint16_t device_id, uint16_t stream_id,
                           const uint8_t *data, uint32_t length, uint16_t chunk_size);

/**
 * @brief Stream `length` bytes generated on the fly (deterministic pattern).
 *
 * Like cipher_stream_send but produces the payload one chunk at a time instead
 * of reading a buffer, so a memory-constrained node can send an arbitrarily
 * large stream (100 MB+) while holding only a single chunk. The checksum is
 * folded incrementally; the receiver verifies it exactly as for a buffered send.
 *
 * @return Number of bytes sent, or a negative value on error.
 */
int32_t cipher_stream_send_pattern(cipher_daemon_t *d, uint16_t device_id, uint16_t stream_id,
                                   uint32_t length, uint16_t chunk_size);

/**
 * @brief Stats for the most recently completed inbound stream.
 */
typedef struct {
    uint32_t completion_id;  /**< Monotonic per completed stream (dedup key) */
    uint16_t stream_id;
    uint32_t total_len;      /**< Bytes the sender declared in START */
    uint32_t received_len;   /**< Bytes actually received across DATA packets */
    uint32_t num_chunks;     /**< DATA packets received */
    uint32_t checksum;       /**< FNV-1a over received bytes */
    bool checksum_ok;        /**< received checksum matched END's declared value */
    int64_t duration_ms;     /**< START -> END wall time */
} cipher_stream_rx_stats_t;

/**
 * @brief Fetch stats for the last completed inbound stream (thread-safe copy).
 *
 * @param d     The daemon
 * @param out   Filled with the last stream's stats
 * @return true if a completed stream was available
 */
bool cipher_stream_get_last_rx(cipher_daemon_t *d, cipher_stream_rx_stats_t *out);

/* Phase passed to a stream RX sink. */
#define CIPHER_STREAM_PHASE_START 0
#define CIPHER_STREAM_PHASE_DATA  1
#define CIPHER_STREAM_PHASE_END   2

/**
 * @brief Sink invoked as inbound stream bytes arrive, so an application can
 *        consume the payload instead of only its checksum (the reassembler is
 *        buffer-less by design). Used by OTA to write firmware straight into the
 *        secondary flash slot.
 *
 * Called outside the daemon's stream mutex, in the stream thread context:
 *   - START: data=NULL, len=0 — begin a transfer (e.g. flash_img_init).
 *   - DATA:  data/len = one chunk, in order — append it.
 *   - END:   data = &(uint8_t checksum_ok), len=1 — finalize/commit or discard.
 *
 * @param stream_id  The stream's id (from START).
 * @param phase      CIPHER_STREAM_PHASE_{START,DATA,END}.
 * @param data       Chunk bytes (DATA) / checksum_ok flag (END) / NULL (START).
 * @param len        Byte count for this call.
 * @param ctx        Opaque pointer registered with the sink.
 */
typedef void (*cipher_stream_rx_sink_t)(uint16_t stream_id, uint8_t phase,
                                        const uint8_t *data, uint16_t len, void *ctx);

/**
 * @brief Register (or clear, with sink=NULL) the inbound stream RX sink.
 */
void cipher_stream_set_rx_sink(cipher_daemon_t *d, cipher_stream_rx_sink_t sink, void *ctx);

/**
 * @brief FNV-1a helper (public so a sender can precompute the expected value).
 */
uint32_t cipher_stream_fnv1a(uint32_t seed, const uint8_t *data, size_t length);

#endif  // CIPHER_STREAM_H
