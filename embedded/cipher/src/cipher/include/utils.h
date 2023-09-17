#ifndef UTILS_H
#define UTILS_H

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/logging/log_ctrl.h>

#define CIPHER_CONFIG_PROTOCOL_VERSION (uint16_t)1
#define CIPHER_CONFIG_MAX_PAYLOAD_SIZE 1024

// Recv Buffer Pool
#define CONFIG_CIPHER_RECV_BUFFER_SIZE CIPHER_CONFIG_MAX_PAYLOAD_SIZE
#define CONFIG_CIPHER_RECV_BUFFERS 5

// Logging and Debugging
#define LOG(fmt, ...) LOG_INF("%s: " fmt, "", ##__VA_ARGS__)
#define DBG(fmt, ...) LOG_DBG(fmt, ##__VA_ARGS__)
#define WARN(fmt, ...) LOG_WRN("%s: " fmt, __func__, ##__VA_ARGS__)
#define ERROR(fmt, ...)                               \
    {                                                 \
        LOG_ERR("%s: " fmt, __func__, ##__VA_ARGS__); \
        log_panic();                                  \
        k_fatal_halt(0);                              \
    }

#endif // UTILS_H