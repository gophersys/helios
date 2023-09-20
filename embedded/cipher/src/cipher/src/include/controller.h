#ifndef CIPHER_PRIV_H
#define CIPHER_PRIV_H

#include <stdbool.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "utils/err.h"

// Private include
#include "threads.h"

/**
 * @brief Ensure that node at end point matches protocol version, and exchange configs
 *
 * @param cfg The transport interface configuration
 * @return true If node was handshook correctly
 * @return false If node protocol version mismatch or connection issue occurs
 */
bool cipher_handshake(const tal_config_t *cfg);

typedef enum
{
    CONTROLLER_EVENT_TYPE_SPAWN_THREAD,
    CONTROLLER_EVENT_TYPE_EXIT,

    CONTROLLER_EVENT_TYPE_MAX,
} controller_event_type_t;

typedef struct
{
    controller_event_type_t type;
} controller_event_t;

bool cipher_controller_exit(cipher_daemon_t *daemon);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Service Discovery
 *---------------------------------------------------------------------------------------------------*/

#endif