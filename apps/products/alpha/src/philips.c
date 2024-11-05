// Standard includes
#include <stdbool.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Philips external library
#include "../lib/inc/fx_datatypes.h"
#include "../lib/inc/psp.h"

LOG_MODULE_REGISTER(app, 4);

const char *psp_error_string(PSP_ERROR err);

int main(void) {
    while (true) {
        // The library will tell us how much memory it needs to use
        static PSP_INST_PARAMS inst_params = {0};
        PSP_ERROR err = PSP_GetDefaultParams(&inst_params);
        if (err != PSP_ERROR_NONE) {
            LOG_ERR("Could not get the default parameters for Phillips library: %s", psp_error_string(err));
            k_fatal_halt(0);
        }

        // Allocate memory to call the library
        inst_params.pMem = k_malloc(inst_params.memorySize);
        if (inst_params.pMem == NULL) {
            LOG_ERR("Could not allocated %d bytes of memory for instance needed by Phillips library", inst_params.memorySize);
            k_fatal_halt(0);
        }

        inst_params.pSourceID = k_malloc(inst_params.sourceIDSize);
        if (inst_params.pMem == NULL) {
            LOG_ERR("Could not allocated %d bytes of memory for source ID needed by Phillips library", inst_params.sourceIDSize);
            k_fatal_halt(0);
        }

        // Create a new library instance
        static PPSP_INST inst = {0};
        err = PSP_Initialise(&inst_params, &inst);
        if (err != PSP_ERROR_NONE) {
            LOG_ERR("Could not initialize Phillips library: %s", psp_error_string(err));
            k_fatal_halt(0);
        }

        LOG_INF("Hello world!");
        k_msleep(1000);
    }

    return 0;
}

const char *psp_error_string(PSP_ERROR err) {
    switch (err) {
        case PSP_ERROR_NONE:
            return "No error";
        case PSP_ERROR_NOT_ENOUGH_MEMORY:
            return "Not enough memory provided";
        case PSP_ERROR_INITIALISATION_FAILED:
            return "Initialisation failed";
        case PSP_ERROR_SIZE_CONFLICT:
            return "Metric data conflicts with size definition";
        case PSP_ERROR_METRIC_NOT_SUPPORTED:
            return "Undefined metric ID used";
        case PSP_ERROR_MODULE_NOT_INITIALISED:
            return "Module not initialised";
        case PSP_ERROR_MEMORY_CORRUPTED:
            return "Memory corrupted";
        case PSP_ERROR_INVALID_PARAMS:
            return "Invalid parameters provided";
        case PSP_ERROR_MULTIPLE_SET:
            return "Attempting to set metric multiple times";
        case PSP_ERROR_DATA_INCOMPLETE:
            return "Metric data is incomplete";
        default:
            return "Unknown error code";
    }
}