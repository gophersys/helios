#include "app.h"

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

LOG_MODULE_DECLARE(mtib);
K_THREAD_STACK_DEFINE(t_stack, APP_THREAD_STACK_SIZE);

// declare thread variables here

// declare k_fifo
K_FIFO_DEFINE(event_fifo);

// define static functions here functions here
static void app_event_handler_thread(void *arg0, void *arg1, void *arg2);

void app_process_event(Event_t *event) {

    switch (event->device->type) {

        case DEVICE_TYPE_BMP390:
            if (event->command == EVENT_CMD_READ) {
                // call read function
            } else if (event->command == EVENT_CMD_WRITE) {
                // call write function
            }
            break;
        case DEVICE_TYPE_LIS2DE12:
            if (event->command == EVENT_CMD_READ) {
                // call read function
            } else if (event->command == EVENT_CMD_WRITE) {
                // call write function
            }
            break;
        case DEVICE_TYPE_INA219:
            if (event->command == EVENT_CMD_READ) {
                // call read function
            } else if (event->command == EVENT_CMD_WRITE) {
                // call write function
            }
            break;
        case DEVICE_TYPE_MC24C08:
            if (event->command == EVENT_CMD_READ) {
                // call read function
            } else if (event->command == EVENT_CMD_WRITE) {
                // call write function
            }
            break;
        case DEVICE_TYPE_MCP4017:
            if (event->command == EVENT_CMD_READ) {
                // call read function
            } else if (event->command == EVENT_CMD_WRITE) {
                // call write function
            }
            break;
    }
}

void app_init_threads(app_info_t *app) {

    app->t_id = k_thread_create(&app->t_data, t_stack,
                                K_THREAD_STACK_SIZEOF(t_stack), app_event_handler_thread,
                                (void *)app, NULL, NULL,
                                APP_THREAD_PRIORITY, 0, K_NO_WAIT);
}

void app_sim_start(app_info_t *app) {

    app_heap_init(app);
    app_init_devices();
    app_init_threads(app);
}

static void app_event_handler_thread(void *arg0, void *arg1, void *arg2) {
    app_info_t *app = (app_info_t *)arg0;
    while (1) {
        Event_t *event = k_fifo_get(&app->command_event_queue, K_FOREVER);
        app_process_event(event);
        k_heap_free(&app->app_events_heap, event);
    }
}

void app_add_event_to_fifo(app_info_t *app, device_t *device, command_t command) {
    // Specify the alignment requirement, for example, 8 bytes
    const size_t alignment = 8;

    Event_t *event = k_heap_aligned_alloc(&app->app_events_heap, alignment, sizeof(Event_t), K_NO_WAIT);
    if (event != NULL) {
        event->device = device;
        event->command = command;
        k_fifo_put(&app->command_event_queue, event);
    }
}

void app_heap_init(app_info_t *app) {
    k_heap_init(&app->app_events_heap, app->app_events_heap_mem, EVENTS_HEAP_SIZE);
}

void app_init_devices() {
    // add the init funcitons here for all the devices that will be used
}