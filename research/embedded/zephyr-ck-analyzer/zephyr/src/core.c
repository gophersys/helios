#include <corekinect/analyzer/analyzer.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(ck_ana, CONFIG_CK_PKT_ANALYZER_LOG_LEVEL);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/
/**
 * Capture core: decodes events into human-readable log lines (log backend)
 * and forwards raw events to the net backend when enabled. Counters are kept
 * for cheap "how much traffic" introspection regardless of backend.
 */

// Implemented in backend_net.c
#ifdef CONFIG_CK_PKT_ANALYZER_BACKEND_NET
void ck_ana_net_emit_cipher(ck_ana_dir_t dir, const ck_ana_cipher_meta_t *meta);
void ck_ana_net_emit_iface(const char *event, int32_t detail);
#endif

static const char *type_str(uint8_t type)
{
    switch (type)
    {
        case 0: return "ADMIN";
        case 1: return "SD";
        case 2: return "RPC";
        case 3: return "EVENT";
        case 4: return "STREAM";
        default: return "?";
    }
}

// Traffic counters (exposed for future shell/telemetry use)
static atomic_t cipher_tx_count;
static atomic_t cipher_rx_count;
static atomic_t iface_tx_bytes;
static atomic_t iface_rx_bytes;

void ck_analyzer_cipher_packet(ck_ana_dir_t dir, const ck_ana_cipher_meta_t *meta,
                               const void *payload)
{
    atomic_inc(dir == CK_ANA_DIR_TX ? &cipher_tx_count : &cipher_rx_count);

#ifdef CONFIG_CK_PKT_ANALYZER_BACKEND_LOG
    LOG_INF("cipher %s 0x%04x->0x%04x svc=%u op=%u %s len=%u flags=0x%02x hops=%u",
            dir == CK_ANA_DIR_TX ? "TX" : "RX",
            meta->source_id, meta->destination_id,
            meta->service_id, meta->operation_id,
            type_str(meta->type), meta->payload_len,
            meta->flags, meta->hop_count);

#ifdef CONFIG_CK_PKT_ANALYZER_HEXDUMP
    if (payload != NULL && meta->payload_len > 0)
    {
        LOG_HEXDUMP_INF(payload, meta->payload_len, "payload");
    }
#endif
#endif
    ARG_UNUSED(payload);

#ifdef CONFIG_CK_PKT_ANALYZER_BACKEND_NET
    ck_ana_net_emit_cipher(dir, meta);
#endif
}

void ck_analyzer_iface_event(const char *event, int32_t detail)
{
#ifdef CONFIG_CK_PKT_ANALYZER_BACKEND_LOG
    LOG_INF("iface event=%s detail=%d", event, detail);
#endif

#ifdef CONFIG_CK_PKT_ANALYZER_BACKEND_NET
    ck_ana_net_emit_iface(event, detail);
#endif
}

void ck_analyzer_iface_bytes(ck_ana_dir_t dir, size_t count)
{
    atomic_add(dir == CK_ANA_DIR_TX ? &iface_tx_bytes : &iface_rx_bytes, count);

#ifdef CONFIG_CK_PKT_ANALYZER_BACKEND_LOG
    LOG_DBG("iface %s %u bytes", dir == CK_ANA_DIR_TX ? "TX" : "RX", (unsigned)count);
#endif
}
