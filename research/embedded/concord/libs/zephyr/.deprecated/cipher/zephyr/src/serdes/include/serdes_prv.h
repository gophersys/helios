#ifndef SERDES_PRV_H
#define SERDES_PRV_H

#include <corekinect/cipher/serdes/types.h>

#include "daemon/daemon.h"

typedef serdes_error_t (*encode_func)(serdes_encode_args_t *args);
typedef serdes_error_t (*decode_func)(serdes_decode_args_t *args);

encode_func admin_lookup_encode_func(serdes_encode_args_t *args);
decode_func admin_lookup_decode_func(serdes_decode_args_t *args);

encode_func sd_lookup_encode_func(serdes_encode_args_t *args);
decode_func sd_lookup_decode_func(serdes_decode_args_t *args);

encode_func rpc_lookup_encode_func(cipher_daemon_t *d, serdes_encode_args_t *args);
decode_func rpc_lookup_decode_func(cipher_daemon_t *d, serdes_decode_args_t *args);

encode_func event_lookup_encode_func(serdes_encode_args_t *args);
decode_func event_lookup_decode_func(serdes_decode_args_t *args);

encode_func event_lookup_encode_func(serdes_encode_args_t *args);
decode_func event_lookup_decode_func(serdes_decode_args_t *args);

#endif