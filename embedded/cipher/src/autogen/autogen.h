#ifndef AUTOGEN_H
#define AUTOGEN_H

#include <stdbool.h>
#include <stdint.h>

// Cipher includes
#include "daemon/api.h"
#include "daemon/registry.h"
#include "utils/err.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/

#define THIS_DEVICE_ID (uint16_t)623
#define MAX_MESSAGE_LENGTH 24

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

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Payloads
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  API
 *---------------------------------------------------------------------------------------------------*/
cipher_service_entry_t* cipher_get_local_services(size_t* num_services);

#endif