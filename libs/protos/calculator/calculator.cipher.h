#ifndef CALCULATOR_CIPHER_H
#define CALCULATOR_CIPHER_H

#include <corekinect/cipher/cipher.h>
#include "calculator.pb.h"

// Service info registration function
cipher_service_info_t *get_calculatorservice_info(void);

// Server side handler
AddIntegersResponse Calculator_AddIntegersHandler(AddIntegersRequest request);

// Client side call
AddIntegersResponse Calculator_AddIntegersRpc(cipher_unary_rpc_user_info_t *info, AddIntegersRequest request);

#endif // CALCULATOR_CIPHER_H
