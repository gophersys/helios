#ifndef UTILS_H
#define UTILS_H

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/logging/log_ctrl.h>

// Cipher includes
#include "config.h"
#include "cipher_priv.h"

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