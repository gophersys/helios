#ifndef SERVICE_H
#define SERVICE_H

#include "config/default.h"
#include "daemon/iface.h"
#include "daemon/ops.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Services
 *---------------------------------------------------------------------------------------------------*/

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

/**
 * @brief All metadata related to an end point offering a service
 */
typedef struct {
    bool _used;            /*!< Used internally by registry */
    uint16_t device_id;    /*!< The device where the service is located. Localhost is valid */
    cipher_iface_t *iface; /*!< The interface where the device is located */
} cipher_service_end_point_t;

/**
 * @brief Service metadata used by the daemon
 */
typedef struct {
    bool _used;                                                               /*!< Used internally by registry */
    bool local;                                                               /*!< Set to true if it's a local service */
    cipher_service_end_point_t end_points[CONFIG_MAX_END_POINTS_PER_SERVICE]; /*!< List of all end points for service */
    cipher_service_t service;                                                 /*!< The service itself */
} cipher_service_entry_t;

/**
 * @brief The registry used by each application daemon
 */
typedef struct {
    cipher_service_entry_t entries[CONFIG_MAX_NUM_SERVICES]; /*!< A list of all services known to the host */
} cipher_service_registry_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                 RPCs
 *---------------------------------------------------------------------------------------------------*/
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
    cipher_rpc_entry_t *entries[CONFIG_MAX_NUM_CONCURRENT_RPCS];
} cipher_rpc_registry_t;

#endif
