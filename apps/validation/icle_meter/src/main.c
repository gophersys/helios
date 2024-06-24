// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/net_ip.h>
#include <zephyr/net/socket.h>
#include <zephyr/net/sntp.h>
#include <zephyr/net/http/client.h>
#include <zephyr/posix/time.h>

// CoreKinect includes
#include <corekinect/wifi/wifi.h>

LOG_MODULE_REGISTER(app);

// Configuration
#define SSID "ICLE_HERE"
#define PSK  "icle4testing"
#define SERVER_ADDR4 "10.4.2.229"
#define SERVER_PORT 3000
#define SNTP_SERVER "10.4.6.1:123"

// Buffer to store the HTTP response payload
#define MAX_RECV_BUF_LEN 512
static uint8_t recv_buf_ipv4[MAX_RECV_BUF_LEN];

// We use a semaphore to unblock the main thread on a server reponse
static K_SEM_DEFINE(http_req_sem, 0, 1);

int sntp_sync_time(void);
static int connect_socket(sa_family_t family, const char *server, int port, int *sock, struct sockaddr *addr, socklen_t addr_len);
static bool read_and_upload_ina219_data(const struct device *ina, int ina_id, int *sock);

int main(void)
{
    if (!wifi_init())
    {
        LOG_ERR("Could not initialize Wi-Fi interface for %s", CONFIG_BOARD);
        k_fatal_halt(0);
    }

    static struct wifi_connect_req_params conn_params =
    {
        .ssid = SSID,
        .ssid_length = strlen(SSID),
        .psk = PSK,
        .psk_length = strlen(PSK),
    };

    if (!wifi_connect(&conn_params))
    {
        LOG_ERR("Could not connect to Wi-Fi");
        k_fatal_halt(0);
    }

    sntp_sync_time();

    int sock4 = -1;
    struct sockaddr_in addr4;
    if (connect_socket(AF_INET, SERVER_ADDR4, SERVER_PORT, &sock4, (struct sockaddr *)&addr4, sizeof(addr4)) < 0)
    {
        LOG_ERR("Could not connect to HTTP server at %s", SERVER_ADDR4);
        k_fatal_halt(0);
    }

    LOG_INF("Connected to HTTP Server at %s:%d", SERVER_ADDR4, SERVER_PORT);

    const struct device *inas[] =
    {
        DEVICE_DT_GET(DT_NODELABEL(ina219_41)),
        DEVICE_DT_GET(DT_NODELABEL(ina219_44)),
        DEVICE_DT_GET(DT_NODELABEL(ina219_45))
    };

    for (int i = 0; i < sizeof(inas) / sizeof(inas[0]); i++)
    {
        if (!device_is_ready(inas[i]))
        {
            LOG_ERR("Device %s is not ready.\n", inas[i]->name);
            return 0;
        }
    }

    while (true)
    {
        for (int i = 0; i < sizeof(inas) / sizeof(inas[0]); i++)
        {
            read_and_upload_ina219_data(inas[i], i, &sock4);
        }
        k_sleep(K_SECONDS(1));
    }

    return 0;
}

int sntp_sync_time(void)
{
    int rc;
    struct sntp_time now;
    struct timespec tspec;

    rc = sntp_simple(SNTP_SERVER, SYS_FOREVER_MS, &now);
    if (rc == 0)
    {
        tspec.tv_sec = now.seconds;
        tspec.tv_nsec = ((uint64_t)now.fraction * (1000lu * 1000lu * 1000lu)) >> 32;

        clock_settime(CLOCK_REALTIME, &tspec);

        LOG_INF("Acquired time from NTP server: %u", (uint32_t)tspec.tv_sec);
    }
    else
    {
        LOG_ERR("Failed to acquire SNTP, code %d\n", rc);
    }
    return rc;
}

static int connect_socket(sa_family_t family, const char *server, int port,
                          int *sock, struct sockaddr *addr, socklen_t addr_len)
{
    const char *family_str = family == AF_INET ? "IPv4" : "IPv6";
    int ret = 0;

    // Clear the memory for sockaddr structure
    memset(addr, 0, addr_len);

    // Cast addr to the appropriate type and set its fields
    struct sockaddr_in *addr_in = (struct sockaddr_in *)addr;
    addr_in->sin_family = family;
    addr_in->sin_port = htons(port);
    if (inet_pton(family, server, &addr_in->sin_addr) <= 0)
    {
        LOG_ERR("Invalid IPv4 address");
        return -1;
    }
    // Create socket
    *sock = socket(family, SOCK_STREAM, IPPROTO_TCP);
    if (*sock < 0)
    {
        LOG_ERR("Failed to create %s socket (%d)", family_str, -errno);
        return -1;
    }

    // Attempt to connect
    ret = connect(*sock, addr, addr_len);
    if (ret < 0)
    {
        LOG_ERR("Cannot connect to %s server at %s:%d (%d)", family_str, server, port, -errno);
        close(*sock);
        return -1;
    }

    return 0;
}

static void response_cb(struct http_response *rsp, enum http_final_call final_data, void *user_data)
{
    if (final_data == HTTP_DATA_MORE)
    {
        LOG_INF("Partial data received (%zd bytes)", rsp->data_len);
    }
    else if (final_data == HTTP_DATA_FINAL)
    {
        k_sem_give(&http_req_sem); // Release semaphore on final data
    }

    LOG_INF("Response status %s", rsp->http_status);
}

static bool read_and_upload_ina219_data(const struct device *ina, int ina_id, int *sock)
{
    struct sensor_value v_bus, power, current;
    int rc = sensor_sample_fetch(ina);
    if (rc)
    {
        LOG_ERR("Could not fetch sensor data from %s.\n", ina->name);
        return false;
    }

    sensor_channel_get(ina, SENSOR_CHAN_VOLTAGE, &v_bus);
    sensor_channel_get(ina, SENSOR_CHAN_POWER, &power);
    sensor_channel_get(ina, SENSOR_CHAN_CURRENT, &current);

    int v_bus_val1_adjusted = v_bus.val1;
    int v_bus_val2_adjusted = abs(v_bus.val2);
    if (v_bus.val2 < 0 && v_bus.val1 == 0)
    {
        v_bus_val1_adjusted = -v_bus_val1_adjusted; // Adjust the integer part if the whole number is negative and close to zero
    }

    int current_val1_adjusted = current.val1;
    int current_val2_adjusted = abs(current.val2);
    if (current.val2 < 0 && current.val1 == 0)
    {
        current_val1_adjusted = -current_val1_adjusted; // Adjust the integer part if the whole number is negative and close to zero
    }

    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    struct tm *tm_now = gmtime(&ts.tv_sec);

    char time_str[25];
    strftime(time_str, sizeof(time_str), "%Y-%m-%dT%H:%M:%S.000Z", tm_now);

    char payload[256];
    snprintf(payload, sizeof(payload),
             "{\"DeviceId\":\"70B3D584C02002E6\",\"TimeStamp\":\"%s\",\"Voltage\":%d.%06d,\"Current\":%d.%06d,\"Channel\":%d}",
             time_str, v_bus_val1_adjusted, v_bus_val2_adjusted, current_val1_adjusted, current_val2_adjusted, ina_id);

    LOG_INF("%s", payload);

    struct http_request  req =
    {
        .method = HTTP_POST,
        .url = "/icle/PostPower",
        .host = "batcave",
        .port = "3000",
        .protocol = "HTTP/1.1",
        .payload = payload,
        .payload_len = strlen(payload),
        .response = response_cb,
        .recv_buf = recv_buf_ipv4,
        .recv_buf_len = sizeof(recv_buf_ipv4),
        .content_type_value = "application/json"
    };

    // Send HTTP request
    int timeout_ms = 5000;
    rc = http_client_req(*sock, &req, timeout_ms, NULL);
    if (rc < 0)
    {
        LOG_ERR("Failed to send HTTP request: %d", rc);
        return false;
    }

    // Wait for the response callback to release the semaphore
    k_sem_take(&http_req_sem, K_FOREVER);

    return true;
}