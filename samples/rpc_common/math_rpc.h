// Shared RPC contract between rpc_downlink (server) and rpc_uplink (client).
//
// The cipher RPC path sends request/response payloads as raw struct bytes
// (only the packet header is serdes-encoded to network byte order). Both the
// STM32 target and the x86 host/Go peer are little-endian, so packed
// fixed-width fields are wire-compatible without per-field swapping.
#ifndef MATH_RPC_H
#define MATH_RPC_H

#include <stdint.h>

#define MATH_SERVICE_ID 100
#define MATH_OP_ADD     1

typedef struct __attribute__((packed)) {
    uint32_t a;
    uint32_t b;
} math_add_request_t;

typedef struct __attribute__((packed)) {
    uint32_t sum;
} math_add_response_t;

#endif  // MATH_RPC_H
