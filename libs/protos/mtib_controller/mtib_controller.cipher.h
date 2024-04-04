#ifndef MTIB_CONTROLLER_CIPHER_H
#define MTIB_CONTROLLER_CIPHER_H

#include <corekinect/cipher/cipher.h>
#include "mtib_controller.pb.h"

// Service info registration function
cipher_service_info_t *get_mtibcontrollerservice_info(void);

// Server side handler
ResetResponse MtibController_ResetHandler(ResetRequest request);

// Client side call
ResetResponse MtibController_ResetRpc(cipher_unary_rpc_user_info_t *info, ResetRequest request);

// Server side handler
HealthCheckResponse MtibController_HealthCheckHandler(HealthCheckRequest request);

// Client side call
HealthCheckResponse MtibController_HealthCheckRpc(cipher_unary_rpc_user_info_t *info, HealthCheckRequest request);

// Server side handler
GetClusterMetadataResponse MtibController_GetClusterMetadataHandler(GetClusterMetadataRequest request);

// Client side call
GetClusterMetadataResponse MtibController_GetClusterMetadataRpc(cipher_unary_rpc_user_info_t *info, GetClusterMetadataRequest request);

// Server side handler
ListTestsResponse MtibController_ListTestsHandler(ListTestsRequest request);

// Client side call
ListTestsResponse MtibController_ListTestsRpc(cipher_unary_rpc_user_info_t *info, ListTestsRequest request);

// Server side handler
ExecuteBoardTestResponse MtibController_ExecuteBoardTestHandler(ExecuteBoardTestRequest request);

// Client side call
ExecuteBoardTestResponse MtibController_ExecuteBoardTestRpc(cipher_unary_rpc_user_info_t *info, ExecuteBoardTestRequest request);

// Server side handler
ExecutePanelTestResponse MtibController_ExecutePanelTestHandler(ExecutePanelTestRequest request);

// Client side call
ExecutePanelTestResponse MtibController_ExecutePanelTestRpc(cipher_unary_rpc_user_info_t *info, ExecutePanelTestRequest request);

#endif // MTIB_CONTROLLER_CIPHER_H
