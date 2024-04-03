// Standard includes

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/cipher/cipher.h>

// Protocol includes
#include "protos/mtib_zephyr/mtib_zephyr.cipher.h"

// App includes
#include "app/app.h"

LOG_MODULE_DECLARE(handlers);

EepromReadFromMemResponse MtibZephyr_EepromReadFromMemHandler(EepromReadFromMemRequest request)
{
    uint32_t start_time = k_uptime_get_32();

    EepromReadFromMemResponse response =
    {
        .success = false,
    };

    LOG_INF("Reading %d bytes from %d", request.len, request.address);
    response.success = true;
    app_read_from_eeprom(app_get_ptr(), request.address, response.data.bytes, request.len);
    response.data.size = request.len;
    LOG_HEXDUMP_INF(response.data.bytes, response.data.size, "Data");

    LOG_INF("%s executed in %ums", __func__, k_uptime_get_32() - start_time);
    return response;
}

EepromWriteToMemResponse MtibZephyr_EepromWriteToMemHandler(EepromWriteToMemRequest request)
{
    uint32_t start_time = k_uptime_get_32();

    EepromWriteToMemResponse response =
    {
        .success = false
    };

    LOG_INF("Writting %d bytes to %d", request.data.size, request.address);
    LOG_HEXDUMP_INF(request.data.bytes, request.data.size, "Data");
    response.success = true;
    app_write_to_eeprom(app_get_ptr(), request.address, request.data.bytes, request.data.size);

    LOG_INF("%s executed in %ums", __func__, k_uptime_get_32() - start_time);
    return response;
}