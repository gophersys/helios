#include "test.h"

#include <alt_drv.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Cipher includes
#include "daemon/api.h"
#include "utils/err.h"

// App includes
#include "../config/config.h"   // Network configuration of cluster
#include "alt-drv-test-srvc.h"  // We offer this service to the runner
#include "alt-sim-srvc.h"       // We consume this service from the icle

LOG_MODULE_DECLARE(app);
static test_app_info_t app = {0};
test_app_info_t* get_app_info(void) {
    return &app;
}

// Private functions
static void altimeter_callback(void){};
static void test_app_thread(void* arg0, void* arg1, void* arg2);
static double get_altitude_from_pressure(double* pressure);

void test_app_start(void) {

    init_altimeter(altimeter_callback);

    app.t_id = k_thread_create(&app.t_data,
                               app.t_stack,
                               K_THREAD_STACK_SIZEOF(app.t_stack),
                               test_app_thread,
                               (void*)&app, NULL, NULL,
                               APP_THREAD_PRIORITY,
                               0,
                               K_NO_WAIT);

    k_thread_name_set(app.t_id, "alt_drv_test_thread");
}

static void test_app_thread(void* arg0, void* arg1, void* arg2) {
    test_app_info_t* app = (test_app_info_t*)arg0;

    while (true) {
        if (check_altimeter_connectivity() != 0) {
            LOG("Not connected");
        } else {
            if (did_altimeter_interrupt()) {
                measure_temp_and_pressure();

                app->temperature = alt_get_current_temperature();
                app->pressure = alt_get_current_pressure();
                app->altitude = get_altitude_from_pressure(&app->pressure);

                // print_readings(&app->temperature,
                //                &app->pressure,
                //                &app->altitude);

                reset_altimeter_interrupt();
            }
        }

        k_msleep(300);
    }
}

static double get_altitude_from_pressure(double* pressure) {

#define SEA_LEVEL_PRESSURE_INHG 29.9213  // Standard atmospheric pressure at sea level in inHg
#define INHG_TO_PA 3386.39               // Conversion factor from inHg to Pascals
#define BAROMETRIC_CONST 44330.77        // Constant used in the barometric formula
#define BAROMETRIC_EXPONENT 5.25588      // Exponent used in the barometric formula

    // https://whatismyelevation.com/
    double pressure_pa = *pressure * INHG_TO_PA;
    return (BAROMETRIC_CONST * (1 - pow(pressure_pa / (SEA_LEVEL_PRESSURE_INHG * INHG_TO_PA), 1 / BAROMETRIC_EXPONENT)));
}

void print_readings(double* temperature, double* pressure, double* altitude) {
    int temp_int = (int)*temperature;
    int temp_frac = (int)((*temperature - temp_int) * 1000);  // 3 decimal places
    int pres_int = (int)*pressure;
    int pres_frac = (int)((*pressure - pres_int) * 1000);  // 3 decimal places
    int alt_int = (int)*altitude;
    int alt_frac = (int)((*altitude - alt_int) * 1000);  // 3 decimal places

    LOG_INF("Temp: %d.%03d C, Pres: %d.%03d inHg, Alti: %d.%03d meters",
            temp_int, temp_frac,
            pres_int, pres_frac,
            alt_int, alt_frac);
}
