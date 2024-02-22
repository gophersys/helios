// Standard includes

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/cipher/cipher.h>

// App includes
#include "app/app.h"

// Protocol includes
#include "protos/mtib_pi_stm/mtib-pi-stm.cipher.h"

LOG_MODULE_REGISTER(handlers, LOG_LEVEL_DBG);

AdcReadChannelResponse MtibPiStm_AdcReadChannelHandler(AdcReadChannelRequest request)
{
    AdcReadChannelResponse response = {0};
    uint32_t start_time = k_uptime_get_32();

    // Validate inputs
    if (request.channel_number > _ChannelNumber_MAX)
    {
        response.success = false;
        char err[] = "Invalid channel number";
        memcpy(response.error, err, sizeof(err));
    }
    else
    {
        uint32_t adc_value = 0;
        if (!app_read_sn74lv4051a_channel(app_get_ptr(), (mux_channel_t)request.channel_number, &adc_value, request.delay_ms))
        {
            char err[] = "Unable to read ADC channel";
            LOG_ERR("%s", err);

            response.success = false;
            memcpy(response.error, err, sizeof(err));
        }
        else
        {
            // Populate the response
            response.success = true;
            response.voltage = (adc_value / 1000);

            LOG_INF("ADC[%d] value: %dmv", request.channel_number, adc_value);
        }
    }

    LOG_INF("%s executed in %ums", __func__, k_uptime_get_32() - start_time);

    return response;
}

AdcReadAllChannelsResponse MtibPiStm_AdcReadAllChannelsHandler(AdcReadAllChannelsRequest request)
{
    AdcReadAllChannelsResponse response = {0};
    uint32_t start_time = k_uptime_get_32();

    // Read all channels
    uint32_t readings[CHANNEL_MAX] = {0};
    app_read_sn74lv4051a_all_channels(app_get_ptr(), readings, request.delay_ms);

    // Copy values into response
    for (uint8_t i = 0; i < ARRAY_SIZE(readings); i++)
    {
        response.voltage_count++;
        response.voltage[i] = readings[i] / 1000;
        LOG_INF("ADC[%d] value: %dmv", i, readings[i]);
    }

    LOG_INF("%s executed in %ums", __func__, k_uptime_get_32() - start_time);

    response.success = true;
    return response;
}
