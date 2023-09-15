#ifndef UTILS_H
#define UTILS_H

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#define LOG(fmt, ...) LOG_INF("%s", fmt, "", ##__VA_ARGS__)
#define DBG(fmt, ...) LOG_DBG("%s", fmt, "", ##__VA_ARGS__)
#define WARN(fmt, ...) LOG_WRN("%s: " fmt, __func__, ##__VA_ARGS__)
#define ERROR(fmt, ...) LOG_ERR("%s: " fmt, __func__, ##__VA_ARGS__)

#endif // UTILS_H