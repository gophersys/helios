#ifndef CIPHER_CONFIG_H
#define CIPHER_CONFIG_H

// Standard includes
#include <stddef.h>

// CoreKinect includes
#include <corekinect/iface/iface.h>

/**
 * @struct cipher_daemon_config_t
 * @brief User configuration for the application daemon
 */
typedef struct {
    uint16_t device_id;                                              /**< An unique device Id for the host */
    iface_t client_ifaces[CONFIG_CK_CIPHER_CLIENT_IFACE_COUNT]; /**< The client interfaces of the host */
    size_t num_client_ifaces;                                        /**< The number of client interfaces */
    iface_t server_ifaces[CONFIG_CK_CIPHER_SERVER_IFACE_COUNT]; /**< The server interfaces of the host */
    size_t num_server_ifaces;                                        /**< The number of server interfaces */
} cipher_daemon_config_t;

#endif  // CIPHER_CONFIG_H