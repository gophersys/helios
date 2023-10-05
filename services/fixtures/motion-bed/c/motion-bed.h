#ifndef MOTION_BED_H
#define MOTION_BED_H

#include <stdbool.h>
#include <stdint.h>

// Cipher includes
#include "daemon/api.h"
#include "daemon/daemon.h"
#include "daemon/registry.h"
#include "utils/err.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Message Types
 *---------------------------------------------------------------------------------------------------*/
typedef struct {
    enum {
        DIRECTION_X = 0,
        DIRECTION_Y = 1,
        DIRECTION_Z = 2
    } direction;
    float force;
    float interval;
} motion_request_t;

typedef struct {
    enum {
        ERR_MOTOR = 0,
        ERR_UNKNOWN = 1
    } error_code;
    bool success;
} motion_response_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Local RPC Handler
 *---------------------------------------------------------------------------------------------------*/
motion_response_t accel_bench_rpc_command_motion_handler(motion_request_t request);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                   Remote RPC Request
 *---------------------------------------------------------------------------------------------------*/
motion_response_t accel_bench_rpc_command_motion(cipher_daemon_t* d, cipher_rpc_user_info_t* info, motion_request_t request);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Service Registration
 *---------------------------------------------------------------------------------------------------*/
cipher_service_entry_t* accel_fixture_get_services(size_t* num_services);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                  Serdes Registration
 *---------------------------------------------------------------------------------------------------*/
//TODO: me

#endif