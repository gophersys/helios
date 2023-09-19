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
    // Connection errors
    IFACE_CREATE_FAILED,
    IFACE_CONNECT_FAILED,
    IFACE_SET_OPT_FAILED,
    IFACE_ACCEPT_FAILED,
    IFACE_CLOSE_FAILED,

    IFACE_ERROR_MAX,
} iface_error_t;

void handle_interface_error(cipher_daemon_t *d, cipher_iface_t *iface, iface_error_t err);

#endif // #define INTERFACE_H