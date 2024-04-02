
// #include <zephyr/device.h>
// #include <zephyr/logging/log.h>
// #include "ina219_events.h"

// LOG_MODULE_REGISTER(ina219_events);

// static const struct device *ina219_dev;
// /*-----------------------------------------------------------------------------------------------------
//  *                                                                                    ina209 Functions
//  *---------------------------------------------------------------------------------------------------*/
// const struct device *app_get_ina219_info()
// {
//     return ina219_dev;
// }

// bool app_set_ina219_power(app_info_t *app, double pow) {
//     event_opt_ina219_set_power_t opt = {
//         .desired_power = pow,
//     };

//     if (!process_event(app, EVENT_BMP_GET_ALTITUDE, &opt, sizeof(opt))) {
//         // TOODO: handle fatal error
//         return false;
//     }

//     return true;
// }

// void init_ina290() {
//     // get the ina29 device here
//     ina219_dev = DEVICE_DT_GET_ONE(ti_ina219);
//     if (device_is_ready(ina219_dev)) {
//         LOG_INF("INA290 Dev Ready To use");
//     }
// }

// void app_ina219_print_voltage(app_info_t *app) {
//     double value = (double)app->ina219_dev.bus_voltage.val1 + (double)app->ina219_dev.bus_voltage.val2 / 1000000;
//     int int_part = (int)value;
//     int frac_part = (int)((value - int_part) * 1000);
//     LOG_INF("Voltage [V]: %d.%03d", int_part, frac_part);
// }

// void app_ina219_print_current(app_info_t *app) {
//     double value = (double)app->ina219_dev.current.val1 + (double)app->ina219_dev.current.val2 / 1000000;
//     int int_part = (int)value;
//     int frac_part = (int)((value - int_part) * 1000);
//     LOG_INF("Current [A]: %d.%03d", int_part, frac_part);
// }

// void app_ina219_print_power(app_info_t *app) {
//     double value = (double)app->ina219_dev.power.val1 + (double)app->ina219_dev.power.val2 / 1000000;
//     int int_part = (int)value;
//     int frac_part = (int)((value - int_part) * 1000);
//     LOG_INF("Power [W]: %d.%03d", int_part, frac_part);
// }

// void app_print_ina219_data(app_info_t *app) {
//     app_ina219_print_power(app);
//     app_ina219_print_voltage(app);
//     app_ina219_print_current(app);
// }