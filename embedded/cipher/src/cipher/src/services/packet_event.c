// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/socket.h>

// Cipher includes
#include "config/default.h"
#include "daemon/daemon.h"
#include "daemon/registry.h"
#include "protocol/protocol.h"
#include "protocol/serdes.h"
#include "transport/transport.h"
#include "utils/err.h"

// Private include
#include "interface.h"
#include "packet.h"
#include "services.h"
#include "threads.h"

LOG_MODULE_DECLARE(sd, SD_LOG_LEVEL);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Packet Event
 *---------------------------------------------------------------------------------------------------*/
static void notify_interfaces(cipher_daemon_t *d);

void handle_packet_event(cipher_daemon_t *d) {

    cipher_iface_packet_info_t *packet_info = k_fifo_get(&d->sd_packet_queue, K_FOREVER);

    if (packet_info == NULL)
        ERROR("Null item on sd_packet_queue, daemon %d", d->id);

    cipher_packet_t *packet = (cipher_packet_t *)packet_info->packet;

    // Check if service is already registered
    cipher_service_entry_t potential_entry = {
        // .device_id = packet->header.source_id,
        // .service_id = packet->header.service_id,
        .iface = packet_info->iface,
    };

    if (!service_exists(d, &potential_entry)) {
        service_register(d, &potential_entry);
        free_iface_packet_info(d, packet_info);

        notify_interfaces(d);
    }
}

void notify_interfaces(cipher_daemon_t *d) {
}
