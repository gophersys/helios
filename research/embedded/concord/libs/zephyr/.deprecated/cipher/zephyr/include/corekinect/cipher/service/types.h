#ifndef CIPHER_SERVICE_TYPES_H
#define CIPHER_SERVICE_TYPES_H

// Standard includes
#include <stdbool.h>
#include <stdint.h>

// CoreKinect includes
#include <corekinect/cipher/iface.h>
#include <corekinect/cipher/ops/entry.h>

/**
 * @brief Service definition
 */
typedef struct {
    uint16_t id;                                      /*!< ID of the service */
    char name[CONFIG_CK_CIPHER_SERVICE_MAX_NAME_LEN]; /*!< Name of the service */
    uint8_t allowed_hops;                             /*!< How many hosts the request can jump through */
    cipher_ops_entry_t *ops;                          /*!< List of ops, only needed for local services */
    uint8_t num_ops;                                  /*!< Number of ops in local service */
} cipher_service_t;

/**
 * @brief All metadata related to an end point offering a service
 */
typedef struct {
    bool _used;            /*!< Used internally by registry */
    uint16_t device_id;    /*!< The device where the service is located. Localhost is valid */
    cipher_iface_t *iface; /*!< The interface where the device is located */
} cipher_service_end_point_t;

#endif  // CIPHER_SERVICE_TYPES_H