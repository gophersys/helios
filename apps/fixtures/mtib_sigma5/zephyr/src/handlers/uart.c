// Standard includes

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/cipher/cipher.h>

// Protocol includes
#include "protos/mtib_pi_stm/mtib-pi-stm.cipher.h"

LOG_MODULE_DECLARE(handlers);

UartMessageResponse MtibPiStm_PiToSigmaMessageHandler(UartMessageRequest request)
{
    uint32_t start_time = k_uptime_get_32();
    LOG_INF("%s executed in %ums", __func__, k_uptime_get_32() - start_time);
    UartMessageResponse response = {0};
    return response;
}