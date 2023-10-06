#ifndef SERVICE_H
#define SERVICE_H

#include "config/default.h"
#include "daemon/iface.h"
#include "daemon/ops.h"

/**
 * @brief Service definition
 */
typedef struct {
    uint16_t id;                       /*!< ID of the service */
    char name[CONFIG_CIPHER_NAME_LEN]; /*!< Name of the service */
    uint8_t allowed_hops;              /*!< How many hosts the request can jump through */
    cipher_ops_entry_t *ops;           /*!< List of ops, only needed for local services */
    uint8_t num_ops;                   /*!< Number of ops in local service */
} cipher_service_t;

typedef struct {
    bool _used;
    uint16_t device_id; /*!< The device where the service is located. Localhost is valid */
    cipher_iface_t *iface;
} cipher_service_end_point_t;

typedef struct {
    bool _used;
    bool local;
    cipher_service_end_point_t end_points[CONFIG_MAX_END_POINTS_PER_SERVICE];
    cipher_service_t service;
} cipher_service_entry_t;

typedef struct {
    bool _used;
    uint8_t id;
    uint16_t service_id;
    uint16_t op_id;
    void *request;
    size_t request_size;
    void *response;
    size_t response_size;
    struct k_timer timer;
    struct k_sem await_sem;
    cipher_rpc_user_info_t *user_info;
} cipher_rpc_entry_t;

typedef struct {
    cipher_service_entry_t entries[CONFIG_MAX_NUM_SERVICES];
} cipher_service_registry_t;

typedef struct {
    cipher_rpc_entry_t *entries[CONFIG_MAX_NUM_CONCURRENT_RPCS];
} cipher_rpc_registry_t;

#endif
