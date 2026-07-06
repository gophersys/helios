#include <corekinect/analyzer/analyzer.h>

// Standard includes
#include <stdio.h>
#include <string.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/net_ip.h>
#include <zephyr/net/socket.h>

LOG_MODULE_DECLARE(ck_ana, CONFIG_CK_PKT_ANALYZER_LOG_LEVEL);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/
/**
 * Net backend: one compact JSON object per event, sent as a UDP datagram to
 * the collector (CONFIG_CK_PKT_ANALYZER_NET_HOST:PORT). UDP so observability
 * can never block or back-pressure the protocol path; drops are acceptable.
 *
 * The socket is created lazily on first use. Resolution supports numeric
 * IPv4 literals and (when the application enables a resolver) DNS names.
 */

static int ana_sock = -1;
static struct sockaddr_in ana_dest;
static struct k_mutex ana_lock;
static bool ana_init_done;
static uint32_t ana_seq;

static bool ana_net_ready(void)
{
    if (ana_sock >= 0)
    {
        return true;
    }

    if (!ana_init_done)
    {
        k_mutex_init(&ana_lock);
        ana_init_done = true;
    }

    k_mutex_lock(&ana_lock, K_FOREVER);
    if (ana_sock >= 0)  // Raced another thread
    {
        k_mutex_unlock(&ana_lock);
        return true;
    }

    memset(&ana_dest, 0, sizeof(ana_dest));
    ana_dest.sin_family = AF_INET;
    ana_dest.sin_port = net_htons(CONFIG_CK_PKT_ANALYZER_NET_PORT);

    if (zsock_inet_pton(AF_INET, CONFIG_CK_PKT_ANALYZER_NET_HOST, &ana_dest.sin_addr) != 1)
    {
        struct zsock_addrinfo hints = { .ai_family = AF_INET, .ai_socktype = SOCK_DGRAM };
        struct zsock_addrinfo *p_res = NULL;

        if (zsock_getaddrinfo(CONFIG_CK_PKT_ANALYZER_NET_HOST, NULL, &hints, &p_res) != 0 ||
            p_res == NULL)
        {
            k_mutex_unlock(&ana_lock);
            return false;  // Collector not resolvable (yet) — drop silently
        }
        ana_dest.sin_addr = ((struct sockaddr_in *)p_res->ai_addr)->sin_addr;
        zsock_freeaddrinfo(p_res);
    }

    ana_sock = zsock_socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    k_mutex_unlock(&ana_lock);

    return ana_sock >= 0;
}

static void ana_net_send(const char *json, size_t len)
{
    if (!ana_net_ready())
    {
        return;
    }

    // Fire and forget: observability must never block the data path.
    (void)zsock_sendto(ana_sock, json, len, 0, (struct sockaddr *)&ana_dest, sizeof(ana_dest));
}

void ck_ana_net_emit_cipher(ck_ana_dir_t dir, const ck_ana_cipher_meta_t *meta)
{
    char buf[192];
    int n = snprintf(buf, sizeof(buf),
                     "{\"seq\":%u,\"t\":%lld,\"layer\":\"cipher\",\"dir\":\"%s\","
                     "\"src\":%u,\"dst\":%u,\"svc\":%u,\"op\":%u,\"type\":%u,"
                     "\"len\":%u,\"flags\":%u,\"hops\":%u}",
                     ana_seq++, (long long)k_uptime_get(),
                     dir == CK_ANA_DIR_TX ? "tx" : "rx",
                     meta->source_id, meta->destination_id, meta->service_id,
                     meta->operation_id, meta->type, meta->payload_len,
                     meta->flags, meta->hop_count);
    if (n > 0)
    {
        ana_net_send(buf, MIN((size_t)n, sizeof(buf) - 1));
    }
}

void ck_ana_net_emit_iface(const char *event, int32_t detail)
{
    char buf[128];
    int n = snprintf(buf, sizeof(buf),
                     "{\"seq\":%u,\"t\":%lld,\"layer\":\"iface\",\"event\":\"%s\",\"detail\":%d}",
                     ana_seq++, (long long)k_uptime_get(), event, detail);
    if (n > 0)
    {
        ana_net_send(buf, MIN((size_t)n, sizeof(buf) - 1));
    }
}
