#ifndef CIPHER_OPS_TYPES_H
#define CIPHER_OPS_TYPES_H

/**
 * @brief Operations supported by the daemon
 */
typedef enum {
    CIPHER_OPS_TYPE_RPC,
    CIPHER_OPS_TYPE_EVENT,
    CIPHER_OPS_TYPE_STREAM,

    CIPHER_OPS_TYPE_MAX,
} cipher_ops_type_t;

#endif  // CIPHER_OPS_TYPES_H