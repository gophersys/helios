#ifndef MTIB_CONTROLLER_CIPHER_H
#define MTIB_CONTROLLER_CIPHER_H

#include <corekinect/cipher/cipher.h>
#include "mtib_controller.pb.h"

// Service info registration function
cipher_service_info_t *get_mtibcontrollerservice_info(void);

// Server side handler
HealthCheckResponse MtibController_HealthCheckHandler(HealthCheckRequest request);

// Client side call
HealthCheckResponse MtibController_HealthCheckRpc(cipher_unary_rpc_user_info_t *info, HealthCheckRequest request);

#endif // MTIB_CONTROLLER_CIPHER_H
