#ifndef CIPHER_H
#define CIPHER_H

#include <stdbool.h>

#include <zephyr/kernel.h>

// CoreKinect includes
#include "tal.h"

#define CIPHER_PROTOCOL_VERSION (uint16_t)1

typedef struct
{
    // Threads
    k_tid_t listener_thread_id;
} cipher_daemon_t;

void init_cipher(cipher_daemon_t *daemon);

/**
 * @brief Ensure that node at end point matches protocol version, and exchange configs
 *
 * @param cfg The transport interface configuration
 * @return true If node was handshook correctly
 * @return false If node protocol version mismatch or connection issue occurs
 */
bool cipher_handshake(const tal_config_t *cfg);

bool cipher_threads_init(cipher_daemon_t *daemon);

#endif // RAL_H