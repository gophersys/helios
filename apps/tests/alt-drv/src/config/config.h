#ifndef APP_CONFIG_H
#define APP_CONFIG_H

#include "config/daemon.h"
#include "daemon/daemon.h"

#define THIS_DEVICE_ID 123

cipher_daemon_config_t* get_app_config(void);
cipher_daemon_t* get_app_daemon(void);

#endif