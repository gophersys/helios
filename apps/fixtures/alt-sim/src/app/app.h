#ifndef SIM_APP_H
#define SIM_APP_H

#include <stdbool.h>
#include <stdint.h>
#include <zephyr/kernel.h>

#define APP_THREAD_PRIORITY 10
#define APP_THREAD_STACK_SIZE 1024

typedef struct {
    // Thread info
    k_tid_t t_id;
    struct k_thread t_data;
    K_THREAD_STACK_MEMBER(t_stack, APP_THREAD_STACK_SIZE);

    // Readings
    double pressure;
    double temperature;
    double altitude;

    // Current altitude
    double fixture_altitude_ft;
} test_app_info_t;

void alt_sim_app_start(void);
test_app_info_t* get_app_info(void);
void print_readings(double* temperature, double* pressure, double* altitude);

bool set_altitude(test_app_info_t* app, double ft, uint8_t sec);

#endif