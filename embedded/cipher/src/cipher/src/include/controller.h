#ifndef CIPHER_PRIV_H
#define CIPHER_PRIV_H

// Standard includes
#include <stdbool.h>
#include <stdint.h>

// Cipher includes
#include "daemon/daemon.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                Types
 *---------------------------------------------------------------------------------------------------*/
typedef enum {
    CTRL_EVENT_TYPE_IFACE_CONNECTED,
    CTRL_EVENT_TYPE_IFACE_DISCONNECTED,
    CTRL_EVENT_TYPE_EXIT,

    CTRL_EVENT_TYPE_MAX,
} ctrl_event_type_t;

typedef struct {
    cipher_iface_t *iface;
} ctrl_event_opt_iface_conn_t;

typedef struct {
    uintptr_t __k_reserved;

    ctrl_event_type_t type;
    uint16_t id;
    void *options;
} ctrl_event_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  API
 *---------------------------------------------------------------------------------------------------*/
void cipher_ctrl_add_event(cipher_daemon_t *d, ctrl_event_t *event);

#endif