#ifndef INTERFACE_H
#define INTERFACE_H

// Standard includes
#include <stdio.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "utils/err.h"

// Private include
#include "threads.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Data & Types
 *---------------------------------------------------------------------------------------------------*/
typedef enum {
    IFACE_ERROR_CREATE,
    IFACE_ERROR_SET_OPT,
    IFACE_ERROR_CONNECT,
    IFACE_ERROR_ACCEPT,
    IFACE_ERROR_CLOSE,
    IFACE_ERROR_SEND,
    IFACE_ERROR_RECV,

    IFACE_ERROR_HANDSHAKE,

    IFACE_ERROR_SERDES,

    IFACE_ERROR_MAX,
} iface_error_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  API
 *---------------------------------------------------------------------------------------------------*/
bool interface_handshake(cipher_daemon_t *d, cipher_iface_t *iface);
void handle_iface_error(cipher_daemon_t *d, cipher_iface_t *iface, iface_error_t err,
                        void *options, size_t option_size);
void handle_iface_timeout(cipher_daemon_t *d, cipher_iface_t *iface, const char *func);
void handle_iface_disconnect(cipher_daemon_t *d, cipher_iface_t *iface, const char *func);

#endif  // #define INTERFACE_H