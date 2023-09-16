#ifndef UTILS_H
#define UTILS_H

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#define CIPHER_CONFIG_PROTOCOL_VERSION (uint16_t)1
#define CIPHER_CONFIG_MAX_PAYLOAD_SIZE 1024

#define LOG(fmt, ...) LOG_INF("%s: " fmt, "", ##__VA_ARGS__)
#define DBG(fmt, ...) LOG_DBG(fmt, ##__VA_ARGS__)
#define WARN(fmt, ...) LOG_WRN("%s: " fmt, __func__, ##__VA_ARGS__)
#define ERROR(fmt, ...) LOG_ERR("%s: " fmt, __func__, ##__VA_ARGS__) // TODO: Halt the app too

#endif // UTILS_H