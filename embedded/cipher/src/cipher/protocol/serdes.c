#include "cipher.h"

// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/logging/log.h>
#include <zephyr/kernel.h>
#include <zephyr/net/socket.h>

// Private includes
#include "tal.h"
#include "utils.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/
LOG_MODULE_REGISTER(serdes, LOG_LEVEL_DBG);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                 Private Data & Types
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                          Work Queues
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Public API
 *---------------------------------------------------------------------------------------------------*/
cipher_error_t cipher_encode_packet(cipher_encode_args_t args)
{
    cipher_error_t status = CIPHER_ERROR_OK;
    return status;
}
cipher_error_t cipher_decode_packet(cipher_decode_args_t args)
{
    cipher_error_t status = CIPHER_ERROR_OK;
    if (!cipher_packet_parse_header(args.raw_payload, args.raw_payload_size, args.header))
    {
        status = CIPHER_ERROR_INVALID_HEADER;
    }
    else
    {
        const uint8_t *payload_buffer = args.raw_payload + sizeof(cipher_header_t);

        cipher_payload_sd_t *decoded_payload = (cipher_payload_sd_t *)args.decoded_payload;
        decoded_payload->service_id = *payload_buffer;
        payload_buffer += sizeof(uint8_t);
        decoded_payload->num_hops = ntohs(*(uint16_t *)payload_buffer);
        payload_buffer += sizeof(uint16_t);
    }

    return status;
}