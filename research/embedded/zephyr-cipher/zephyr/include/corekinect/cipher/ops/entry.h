#ifndef CIPHER_OPS_ENTRY_H
#define CIPHER_OPS_ENTRY_H

// Standard includes
#include <stdint.h>

// CoreKinect includes
#include <corekinect/cipher/ops/event.h>
#include <corekinect/cipher/ops/rpc.h>
#include <corekinect/cipher/ops/stream.h>
#include <corekinect/cipher/ops/types.h>

/**
 * @brief Used to hold ops instance info for a service
 */
typedef struct {
    uint8_t id;
    cipher_ops_type_t type;
    char name[CONFIG_CK_CIPHER_SERVICE_MAX_NAME_LEN];
    union {
        cipher_ops_rpc_t rpc;
        cipher_ops_event_t event;
        cipher_ops_stream_t stream;
    } op;
} cipher_ops_entry_t;

#endif  // CIPHER_OPS_ENTRY_H
