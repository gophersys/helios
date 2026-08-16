#include <corekinect/wifi/wifi.h>

// Standard includes
#include <stdbool.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/net_context.h>
#include <zephyr/net/net_core.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/net_mgmt.h>
#include <zephyr/net/socket.h>
#include <zephyr/net/wifi_mgmt.h>
#include <zephyr/net/wifi_utils.h>
#include <zephyr/net/dns_resolve.h>
#include <zephyr/net/net_config.h>

LOG_MODULE_DECLARE(app);

#define WIFI_MGMT_EVENTS (NET_EVENT_WIFI_SCAN_RESULT |         \
                          NET_EVENT_WIFI_SCAN_DONE |           \
                          NET_EVENT_WIFI_CONNECT_RESULT        \
                         )

// Local variables
static bool usr_network_found = false;
static struct k_sem scan_results_done_sem = {0};
static bool network_connected = false;
static struct k_sem connect_done_sem = {0};
static struct net_mgmt_event_callback wifi_mgmt_cb;
static struct wifi_connect_req_params *usr_conn_params = NULL;
struct net_if *iface = NULL;

// Useful networking information
static void print_net_addr(void);

// Event handlers
static void wifi_mgmt_event_handler(struct net_mgmt_event_callback *cb, uint32_t mgmt_event, struct net_if *iface);

bool wifi_init(void)
{
    iface = net_if_get_first_wifi();
    if (iface == NULL)
    {
        LOG_ERR("No Wi-Fi interface found for device %s", CONFIG_BOARD);
        return false;
    }

    // Register wifi network events callback
    net_mgmt_init_event_callback(&wifi_mgmt_cb, wifi_mgmt_event_handler, WIFI_MGMT_EVENTS);
    net_mgmt_add_event_callback(&wifi_mgmt_cb);

    return true;
}

bool wifi_connect(struct wifi_connect_req_params *conn_params)
{
    usr_conn_params = conn_params;

    // Finish setting up relevant input fields
    usr_conn_params->band = WIFI_FREQ_BAND_UNKNOWN;
    usr_conn_params->channel = WIFI_CHANNEL_ANY;
    usr_conn_params->security = WIFI_SECURITY_TYPE_PSK;
    usr_conn_params->mfp = WIFI_MFP_OPTIONAL;

    // Check status first to make sure we're not already connected (reset)
    struct wifi_iface_status status = {0};
    if (net_mgmt(NET_REQUEST_WIFI_IFACE_STATUS, iface, &status, sizeof(struct wifi_iface_status)))
    {
        LOG_ERR("Could not request status for iface %s", iface->config.name);
        return false;
    }

    // Start scan
    LOG_INF("Starting network scan...");
    k_sem_init(&scan_results_done_sem, 0, 1);

    struct wifi_scan_params params = {0}; // TODO: Improve this
    if (net_mgmt(NET_REQUEST_WIFI_SCAN, iface, &params, sizeof(params)))
    {
        LOG_ERR("Could not request scan for iface %s", iface->config.name);
        return false;
    }

    // Await for scan to be done or network to be found
    k_sem_take(&scan_results_done_sem, K_FOREVER);
    if (!usr_network_found)
    {
        LOG_WRN("SSID %s network not found", usr_conn_params->ssid);
        return false;
    }

    // Network has been found. Connect
    LOG_INF("Network found, connecting...");
    k_sem_init(&connect_done_sem, 0, 1);

    if (net_mgmt(NET_REQUEST_WIFI_CONNECT, iface, usr_conn_params, sizeof(struct wifi_connect_req_params)))
    {
        LOG_ERR("Could not request connection for iface %s", iface->config.name);
        return false;
    }

    // Await for a connection
    k_sem_take(&connect_done_sem, K_FOREVER);
    if (!network_connected)
    {
        LOG_WRN("Error connecting to %s", usr_conn_params->ssid);
        return false;
    }

    // Init net stack
    int err = net_config_init_by_iface(iface, "WiFi Station", 0, 5000);
    if (err != 0)
    {
        LOG_WRN("Could not initialize network, err: %s", strerror(errno));
        return false;
    }

    LOG_INF("Network initialized OK");
    print_net_addr();

    return true;
}

bool wifi_disconnect(void)
{
    LOG_ERR("%s not implemented yet", __func__);
    return false;
}

static void handle_wifi_scan_result(struct net_mgmt_event_callback *cb)
{
    const struct wifi_scan_result *entry = (const struct wifi_scan_result *)cb->info;

    // Compare to see if this entry matches the user parameters
    if (entry->ssid_length == usr_conn_params->ssid_length)
    {
        if (strcmp(entry->ssid, usr_conn_params->ssid) == 0)
        {
            LOG_INF("User SSID %s found", usr_conn_params->ssid);
            usr_network_found = true;
            k_sem_give(&scan_results_done_sem);
        }
    }
}

static void handle_wifi_scan_done(struct net_mgmt_event_callback *cb)
{
    k_sem_give(&scan_results_done_sem);
}

static void handle_wifi_connect_result(struct net_mgmt_event_callback *cb)
{
    const struct wifi_status *status = (const struct wifi_status *)cb->info;

    if (!status->status)
    {
        network_connected = true;
    }

    k_sem_give(&connect_done_sem);
}

static void wifi_mgmt_event_handler(struct net_mgmt_event_callback *cb,
                                    uint32_t mgmt_event, struct net_if *iface)
{
    switch (mgmt_event)
    {
        case NET_EVENT_WIFI_SCAN_RESULT:
            handle_wifi_scan_result(cb);
            break;
        case NET_EVENT_WIFI_SCAN_DONE:
            handle_wifi_scan_done(cb);
            break;
        case NET_EVENT_WIFI_CONNECT_RESULT:
            handle_wifi_connect_result(cb);
            break;
        default:
            break;
    }
}

static void print_net_addr(void)
{
    char buf[NET_IPV4_ADDR_LEN];

    for (size_t i = 0; i < NET_IF_MAX_IPV4_ADDR; i++)
    {
        LOG_INF("IP Addr: %s",
                net_addr_ntop(AF_INET,
                              &iface->config.ip.ipv4->unicast[i].address.in_addr,
                              buf, sizeof(buf)));

        LOG_INF("Subnet: %s",
                net_addr_ntop(AF_INET,
                              &iface->config.ip.ipv4->netmask,
                              buf, sizeof(buf)));
        LOG_INF("Router: %s",
                net_addr_ntop(AF_INET,
                              &iface->config.ip.ipv4->gw,
                              buf, sizeof(buf)));
    }

    const struct dns_resolve_context *ctx = dns_resolve_get_default();

    for (int i = 0; ctx->servers[i].dns_server.sa_family != AF_UNSPEC; ++i)
    {
        if (ctx->servers[i].dns_server.sa_family == AF_INET)
        {
            // If the address is IPV4, then print it
            struct sockaddr_in *dns_addr = (struct sockaddr_in *)&ctx->servers[i].dns_server;

            LOG_INF("Resolver [%d]: %s", i,
                    net_addr_ntop(AF_INET, &dns_addr->sin_addr, buf, sizeof(buf)));
        }
    }
}