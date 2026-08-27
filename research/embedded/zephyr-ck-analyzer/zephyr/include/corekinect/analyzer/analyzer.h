#ifndef COREKINECT_ANALYZER_H
#define COREKINECT_ANALYZER_H

// Standard includes
#include <stddef.h>
#include <stdint.h>

/**
 * ck_analyzer — capture hooks for the iface + cipher libraries.
 *
 * Consumers call the CK_ANA_* macros unconditionally; when the analyzer is
 * disabled (or the module absent) the macros are empty and the calls vanish.
 */

/** Direction of a captured packet */
typedef enum
{
    CK_ANA_DIR_TX,
    CK_ANA_DIR_RX,
} ck_ana_dir_t;

/**
 * Decoded cipher header metadata for one packet.
 * Mirrors cipher_header_t without importing cipher's headers (keeps the
 * analyzer dependency-free in both directions).
 */
typedef struct
{
    uint16_t source_id;
    uint16_t destination_id;
    uint16_t service_id;
    uint8_t operation_id;
    uint8_t type;
    uint16_t payload_len;
    uint16_t sequence_num;
    uint8_t flags;
    uint8_t hop_count;
} ck_ana_cipher_meta_t;

#ifdef CONFIG_CK_PKT_ANALYZER

/**
 * @brief Record a cipher packet (called at serdes encode/decode boundaries)
 *
 * @param dir TX (encode path) or RX (decode path)
 * @param meta Decoded header fields
 * @param payload Payload bytes (may be NULL)
 */
void ck_analyzer_cipher_packet(ck_ana_dir_t dir, const ck_ana_cipher_meta_t *meta,
                               const void *payload);

/**
 * @brief Record an iface transport event (connect/accept/close/error)
 *
 * @param event Short event name, e.g. "connect" — must be a string literal
 * @param detail Numeric detail (fd, error code, byte count — event-specific)
 */
void ck_analyzer_iface_event(const char *event, int32_t detail);

/**
 * @brief Record raw transport bytes moving through an iface
 */
void ck_analyzer_iface_bytes(ck_ana_dir_t dir, size_t count);

#define CK_ANA_CIPHER_PKT(dir, meta, payload) ck_analyzer_cipher_packet((dir), (meta), (payload))
#define CK_ANA_IFACE_EVT(event, detail)       ck_analyzer_iface_event((event), (detail))
#define CK_ANA_IFACE_BYTES(dir, count)        ck_analyzer_iface_bytes((dir), (count))

#else  // !CONFIG_CK_PKT_ANALYZER — everything vanishes

#define CK_ANA_CIPHER_PKT(dir, meta, payload) ((void)0)
#define CK_ANA_IFACE_EVT(event, detail)       ((void)0)
#define CK_ANA_IFACE_BYTES(dir, count)        ((void)0)

#endif  // CONFIG_CK_PKT_ANALYZER

#endif  // COREKINECT_ANALYZER_H
