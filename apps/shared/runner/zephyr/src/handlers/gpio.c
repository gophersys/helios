// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/cipher/cipher.h>
#include <dut_gpio_config_drv.h>

// Protocol includes
#include "protos/mtib_runner_zephyr/mtib_runner_zephyr.cipher.h"

// App includes
#include "app/app.h"

LOG_MODULE_DECLARE(handlers);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Private Helpers
 *---------------------------------------------------------------------------------------------------*/
bool _check_configure_inputs(GpioConfigurePinRequest *p_request, GpioConfigurePinResponse *p_response,
                             gpio_flags_t *p_flag_buf);

bool _check_set_inputs(GpioSetPinRequest *p_request, GpioSetPinResponse *p_response);

bool _check_read_inputs(GpioReadPinRequest *p_request, GpioReadPinResponse *p_response);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                            Configure
 *---------------------------------------------------------------------------------------------------*/
GpioConfigurePinResponse MtibRunnerZephyr_GpioConfigurePinHandler(GpioConfigurePinRequest request)
{
    uint32_t start_time = k_uptime_get_32();

    GpioConfigurePinResponse response =
    {
        .success = false,
    };

    gpio_flags_t flag = 0;
    int32_t success = 0;
    if (!_check_configure_inputs(&request, &response, &flag))
    {
        LOG_WRN("%s", response.error);
    }
    else
    {
        LOG_INF("Configuring pin %d as %s", request.pin_number, request.direction == GpioDirection_INPUT ? "input" : "output");
        if (!app_gpio_configure(app_get_ptr(), request.pin_number, flag, &success))
        {
            char err[] = "Could not configure pin, internal error";
            memcpy(response.error, err, sizeof(response.error));
            LOG_WRN("%s", response.error);
        }
        else
        {
            response.success = true;
        }
    }

    LOG_INF("%s executed in %ums", __func__, k_uptime_get_32() - start_time);
    return response;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  Set
 *---------------------------------------------------------------------------------------------------*/
GpioSetPinResponse MtibRunnerZephyr_GpioSetPinHandler(GpioSetPinRequest request)
{
    uint32_t start_time = k_uptime_get_32();

    GpioSetPinResponse response =
    {
        .success = false,
    };

    int32_t success = 0;
    if (!_check_set_inputs(&request, &response))
    {
        LOG_WRN("%s", response.error);
    }
    else
    {
        LOG_INF("Writting pin %d to %s", request.pin_number, request.value == GpioValue_HIGH ? "HIGH" : "LOW");
        if (!app_gpio_set(app_get_ptr(), request.pin_number, request.value, &success))
        {
            char err[] = "Could not set pin value, internal error";
            memcpy(response.error, err, sizeof(response.error));
            LOG_WRN("%s", response.error);
        }
        else
        {
            response.success = true;
        }
    }

    LOG_INF("%s executed in %ums", __func__, k_uptime_get_32() - start_time);
    return response;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                 Read
 *---------------------------------------------------------------------------------------------------*/
GpioReadPinResponse MtibRunnerZephyr_GpioReadPinHandler(GpioReadPinRequest request)
{
    uint32_t start_time = k_uptime_get_32();

    GpioReadPinResponse response =
    {
        .success = false,
    };

    int32_t success = 0;
    if (!_check_read_inputs(&request, &response))
    {
        LOG_WRN("%s", response.error);
    }
    else
    {
        if (!app_gpio_read(app_get_ptr(), request.pin_number, &success))
        {
            response.value = GpioValue_LOW;
        }
        else
        {
            response.value = GpioValue_HIGH;
        }

        LOG_INF("Read pin %d, value: %d", request.pin_number, response.value);

        response.success = true;
    }

    LOG_INF("%s executed in %ums", __func__, k_uptime_get_32() - start_time);
    return response;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                               Helpers Implementation
 *---------------------------------------------------------------------------------------------------*/
bool _check_configure_inputs(GpioConfigurePinRequest *p_request, GpioConfigurePinResponse *p_response, gpio_flags_t *p_flag_buf)
{
    // Check pin
    if (p_request->pin_number >= max_num_dut_gpios_e)
    {
        snprintf(p_response->error, sizeof(p_response->error), "Invalid pin number in request: %d", p_request->pin_number);
        return false;
    }

    // Check the direction
    if (p_request->direction == GpioDirection_INPUT)
    {
        *p_flag_buf = GPIO_INPUT;
    }
    else if (p_request->direction == GpioDirection_OUTPUT)
    {
        *p_flag_buf = GPIO_OUTPUT;
    }
    else
    {
        snprintf(p_response->error, sizeof(p_response->error), "Invalid pin direction in request: %d", p_request->direction);
        return false;
    }

    // Check the resistor
    if (p_request->resistor == GpioConfigureResistorConfig_RESISTOR_PULL_UP)
    {
        *p_flag_buf |= GPIO_PULL_UP;
    }
    else if (p_request->resistor == GpioConfigureResistorConfig_RESISTOR_PULL_DOWN)
    {
        *p_flag_buf |= GPIO_PULL_DOWN;
    }
    else
    {
        snprintf(p_response->error, sizeof(p_response->error), "Invalid resistor config in request: %d", p_request->resistor);
        return false;
    }

    return true;
}

bool _check_set_inputs(GpioSetPinRequest *p_request, GpioSetPinResponse *p_response)
{
    // Check pin
    if (p_request->pin_number >= max_num_dut_gpios_e)
    {
        snprintf(p_response->error, sizeof(p_response->error), "Invalid pin number in request: %d", p_request->pin_number);
        return false;
    }

    // Check the value
    if (p_request->value > _GpioValue_MAX)
    {
        snprintf(p_response->error, sizeof(p_response->error), "Invalid pin state value in request: %d", p_request->value);
        return false;
    }

    return true;
}

bool _check_read_inputs(GpioReadPinRequest *p_request, GpioReadPinResponse *p_response)
{
    // Check pin
    if (p_request->pin_number >= max_num_dut_gpios_e)
    {
        snprintf(p_response->error, sizeof(p_response->error), "Invalid pin number in request: %d", p_request->pin_number);
        return false;
    }

    return true;
}