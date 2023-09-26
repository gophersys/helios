#ifndef API_H
#define API_H

#include <stdbool.h>
#include <zephyr/kernel.h>

// CoreKinect includes
#include "config/daemon.h"
#include "config/default.h"
#include "daemon/daemon.h"
#include "transport/transport.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  API
 *---------------------------------------------------------------------------------------------------*/

void cipher_init_daemon(cipher_daemon_config_t *cfg, cipher_daemon_t *d);

#endif  // API_H