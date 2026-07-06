#ifndef CIPHER_REGISTRY_RPC_H
#define CIPHER_REGISTRY_RPC_H

// Standard includes
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// CoreKinect includes
#include <corekinect/cipher/ops/rpc.h>

typedef struct {
    bool _used;
    uint8_t id;
    uint16_t service_id;
    uint16_t op_id;
    void *request;
    size_t request_size;
    void *response;
    size_t response_size;
    struct k_timer timer;
    struct k_sem await_sem;
    cipher_unary_rpc_user_info_t *user_info;
} cipher_registry_rpc_entry_t;

typedef struct {
    cipher_registry_rpc_entry_t *entries[CONFIG_CK_MAX_NUM_CONCURRENT_RPCS];
} cipher_registry_rpc_t;

#endif  // CIPHER_REGISTRY_RPC_H