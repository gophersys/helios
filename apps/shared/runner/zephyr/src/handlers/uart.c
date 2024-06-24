// Standard includes

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/cipher/cipher.h>

// App includes
#include "app/uart.h"

// Protocol includes
#include "protos/mtib_runner_zephyr/mtib_runner_zephyr.cipher.h"

LOG_MODULE_DECLARE(handlers);

UartPortStateChangeResponse MtibRunnerZephyr_UartPortEnableHandler(UartPortStateChangeRequest request)
{
    UartPortStateChangeResponse response = {0};

    // Check that the request logic makes sense
    if (!request.enable)
    {
        char err[] = "Enable request received with enable set to false";
        memcpy(response.error, err, sizeof(err));
        return response;
    }

    // Call app
    if (!app_uart_forwarder_enable(request.device))
    {
        char err[] = "Application returned an error whilst trying to enable UART device";
        memcpy(response.error, err, sizeof(err));
        return response;
    }

    return response;
}

UartPortStateChangeResponse MtibRunnerZephyr_UartPortDisableHandler(UartPortStateChangeRequest request)
{
    UartPortStateChangeResponse response = {0};

    // Check that the request logic makes sense
    if (request.enable)
    {
        char err[] = "Disable request received with enable set to true";
        memcpy(response.error, err, sizeof(err));
        return response;
    }

    // Call app
    if (!app_uart_forwarder_disable(request.device))
    {
        char err[] = "Application returned an error whilst trying to disable UART device";
        memcpy(response.error, err, sizeof(err));
        return response;
    }

    return response;
}

UartMessageResponse MtibRunnerZephyr_PiToSigmaMessageHandler(UartMessageRequest request)
{
    uint32_t start_time = k_uptime_get_32();

    UartMessageResponse response = {0};

    if (!app_uart_forwarder_send_data(request.device, request.data.bytes, request.data.size))
    {
        char err[] = "Could not send UART data to device";
        memcpy(response.error, err, sizeof(err));
        return response;
    }

    LOG_INF("%s executed in %ums", __func__, k_uptime_get_32() - start_time);

    return response;
}