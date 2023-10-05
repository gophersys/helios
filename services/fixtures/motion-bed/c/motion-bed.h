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
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/

#define THIS_DEVICE_ID (uint16_t)623
#define MAX_MESSAGE_LENGTH 24

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           User Types
 *---------------------------------------------------------------------------------------------------*/
typedef struct {
    enum {
        DIRECTION_X = 0,
        DIRECTION_Y = 1,
        DIRECTION_Z = 2
    } Direction;
    float force;
    float interval;
} MotionRequest_t;

typedef struct {
    bool success;
    char message[MAX_MESSAGE_LENGTH];
} MotionResponse_t;

typedef struct {
    float x, y, z;
    uint64_t timestamp;
} AccelerometerData_t;

// this is the handler for the local rpc, that a remote host calls
MotionResponse_t accel_command_motion_handler(MotionRequest_t request);

// this is the function that localhost can call on a remote host to exectue an RPC
MotionResponse_t accel_command_motion_rpc(cipher_daemon_t* d, cipher_rpc_user_info_t* info, MotionRequest_t request);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                       Protocol Types
 *---------------------------------------------------------------------------------------------------*/
typedef enum {
    OP_ID_RPC_MOTION_COMMAND,

    OP_ID_MAX,
} cipher_operation_id_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Payloads
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  API
 *---------------------------------------------------------------------------------------------------*/
cipher_service_entry_t* cipher_get_local_services(size_t* num_services);

#endif