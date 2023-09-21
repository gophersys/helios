#ifndef CIPHER_PRIV_H
#define CIPHER_PRIV_H

#include <stdbool.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "utils/err.h"

// Private include
#include "threads.h"

typedef enum
{
    CTRL_EVENT_TYPE_IFACE_CONNECTED,
    CTRL_EVENT_TYPE_IFACE_DISCONNECTED,
    CTRL_EVENT_TYPE_EXIT,

    CTRL_EVENT_TYPE_MAX,
} ctrl_event_type_t;

typedef struct
{
    cipher_iface_t *iface;
} ctrl_event_opt_iface_conn_t;

typedef struct
{
    ctrl_event_type_t type;
    void *options;
} ctrl_event_t;

void cipher_ctrl_add_event(cipher_daemon_t *d, ctrl_event_t *event);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Service Discovery
 *---------------------------------------------------------------------------------------------------*/

#endif