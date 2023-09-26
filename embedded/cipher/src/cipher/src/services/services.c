// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "protocol/protocol.h"
#include "protocol/serdes.h"
#include "transport/transport.h"
#include "utils/err.h"

// Private include
#include "interface.h"
#include "packet.h"
#include "services.h"
#include "threads.h"

LOG_MODULE_REGISTER(sd, SD_LOG_LEVEL);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                      Developer Notes
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief The service discovery thread will do the following actions:
 *
 * [ ] Register a new service when a service discovery status packet is received
 * [ ] Unregister a service when a service discovery status packet is received
 * [ ] Unregister all services on an interface when its disconnected
 * [ ] Broadcast a service status to all affected interfaces when the service registry changes
 */

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/
#define EVENT_NUM 3
#define SD_PACKET_EVENT 0
#define IFACE_CONN_EVENT 1
#define IFACE_DISCONN_EVENT 2

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Private Functions
 *---------------------------------------------------------------------------------------------------*/
static void setup_thread_events(cipher_daemon_t *d, struct k_poll_event *events) {
    k_poll_event_init(&events[SD_PACKET_EVENT],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &d->sd_packet_queue);

    k_poll_event_init(&events[IFACE_CONN_EVENT],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &d->sd_iface_conn_queue);

    k_poll_event_init(&events[IFACE_DISCONN_EVENT],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &d->sd_iface_disconn_queue);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Thread
 *---------------------------------------------------------------------------------------------------*/
void cipher_sd_thread(void *arg0, void *arg1, void *arg2) {
    cipher_daemon_t *d = (cipher_daemon_t *)arg0;
    __ASSERT(d != NULL, "null daemon passed to thread");

    struct k_poll_event sd_events[EVENT_NUM];
    setup_thread_events(d, sd_events);

    while (true) {
        int event = k_poll(sd_events, EVENT_NUM, K_FOREVER);

        if (event != 0) {
            ERROR("Unexpected timeout on k_poll: %d, daemon %d", event, d->id);
        } else {
            if (sd_events[SD_PACKET_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE) {
                handle_packet_event(d);
            } else if (sd_events[IFACE_CONN_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE) {
                handle_iface_conn_event(d);
            } else if (sd_events[IFACE_DISCONN_EVENT].state == K_POLL_STATE_FIFO_DATA_AVAILABLE) {
                handle_iface_disconn_event(d);
            } else {
                ERROR("Unknown poll condition: %d, daemon %d", event, d->id);
            }

            // reset events
            for (uint8_t i = 0; i < EVENT_NUM; i++) {
                sd_events[i].state = K_POLL_STATE_NOT_READY;
            }
        }
    }
}