#ifndef ALT_SIM_SRVC_H
#define ALT_SIM_SRVC_H

#include <stdbool.h>
#include <stdint.h>

// Cipher includes
#include "daemon/daemon.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Message Types
 *---------------------------------------------------------------------------------------------------*/

typedef struct __attribute__((packed)) {
    enum {
        _1000_FT_PER_5_SEC = 0,
        _1000_FT_PER_10_SEC = 1
    } setting;
    double desired_altitude_ft;
} alt_setting_request_t;

typedef struct __attribute__((packed)) {
    enum {
        ALT_SIM_ERR_FATAL = 0,
        ALT_SIM_ERR_INVALID_REQUEST = 1,
    } err;
    bool success;
} alt_setting_response_t;

typedef struct __attribute__((packed)) {
    // TODO: What do do with no member structs
} readings_request_t;

typedef struct __attribute__((packed)) {
    double temperature_c;
    double pressure_inhg;
    double altitude_m;
} readings_response_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Local RPC Handler
 *---------------------------------------------------------------------------------------------------*/
alt_setting_response_t alt_sim_rpc_set_altitude_handler(alt_setting_request_t request);
readings_response_t alt_sim_rpc_get_readings_handler(readings_request_t request);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                   Remote RPC Request
 *---------------------------------------------------------------------------------------------------*/
alt_setting_response_t alt_sim_rpc_set_altitude(cipher_daemon_t* d, cipher_rpc_user_info_t* info,
                                                alt_setting_request_t request);

readings_response_t alt_sim_rpc_get_readings(cipher_daemon_t* d, cipher_rpc_user_info_t* info,
                                             readings_request_t request);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Service Registration
 *---------------------------------------------------------------------------------------------------*/
cipher_service_entry_t* alt_sim_fixture_get_services(size_t* num_services);

#endif