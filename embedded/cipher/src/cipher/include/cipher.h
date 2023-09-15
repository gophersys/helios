#ifndef CIPHER_H
#define CIPHER_H

#include <stdbool.h>

// CoreKinect includes
#include "tal.h"

#define CIPHER_PROTOCOL_VERSION (uint16_t)1

void init_cipher(void);

/**
 * @brief Ensure that node at end point matches protocol version, and exchange configs
 *
 * @param cfg The transport interface configuration
 * @return true If node was handshook correctly
 * @return false If node protocol version mismatch or connection issue occurs
 */
bool cipher_handshake(const tal_config_t *cfg);

#endif // RAL_H