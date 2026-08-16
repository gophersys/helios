#ifndef COREKINECT_WIFI_H
#define COREKINECT_WIFI_H

// Standard includes
#include <stdbool.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/net/wifi_mgmt.h>

bool wifi_init(void);
bool wifi_connect(struct wifi_connect_req_params *conn_params);
bool wifi_disconnect(void);

#endif // COREKINECT_WIFI_H