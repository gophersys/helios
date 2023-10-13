#ifndef APP_TEST_H
#define APP_TEST_H

#include <zephyr/kernel.h>

#define LOCAL_TEST_ENABLED

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
} test_app_info_t;

void test_app_start(void);
test_app_info_t* get_app_info(void);
void print_readings(double* temperature, double* pressure, double* altitude);

#ifdef LOCAL_TEST_ENABLED
void run_manual_test(void);
#endif

#endif