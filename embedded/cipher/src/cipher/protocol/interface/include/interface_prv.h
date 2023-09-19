#ifndef INTERFACE_H
#define INTERFACE_H

// Standard includes
#include <stdio.h>

// Cipher includes
#include "cipher.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Data & Types
 *---------------------------------------------------------------------------------------------------*/
typedef enum
{
    IFACE_ERROR_CREATE,
    IFACE_ERROR_SET_OPT,
    IFACE_ERROR_CONNECT,
    IFACE_ERROR_ACCEPT,
    IFACE_ERROR_CLOSE,
    IFACE_ERROR_SEND,
    IFACE_ERROR_RECV,

    IFACE_ERROR_MAX,
} iface_error_t;

void handle_interface_error(cipher_daemon_t *d, cipher_iface_t *iface, iface_error_t err);

#endif // #define INTERFACE_H