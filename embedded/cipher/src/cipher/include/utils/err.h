#ifndef ERR_H
#define ERR_H

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/logging/log_ctrl.h>

// Logging and Debugging
#define LOG(fmt, ...) LOG_INF("%s: " fmt, "", ##__VA_ARGS__)
#define DBG(fmt, ...) LOG_DBG("%s: " fmt, "", ##__VA_ARGS__)
#define WARN(fmt, ...) LOG_WRN("%s: " fmt, __func__, ##__VA_ARGS__)
#define ERROR(fmt, ...)                               \
    {                                                 \
        LOG_ERR("%s: " fmt, __func__, ##__VA_ARGS__); \
        log_panic();                                  \
        k_fatal_halt(0);                              \
    }

// Malloc helpers
#define CHECK_MALLOC(ptr) __ASSERT((ptr) != NULL, "k_heap_alloc failed in %s at %s:%d", __func__, __FILE__, __LINE__)

#endif // ERR_H