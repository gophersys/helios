#ifndef CIPHER_H
#define CIPHER_H

#include <stdbool.h>

#include <zephyr/kernel.h>

// CoreKinect includes
#include "tal.h"
#include "config.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Packet Layer
 *---------------------------------------------------------------------------------------------------*/

// Connection manager thread for the given interface
typedef struct
{
    k_tid_t id;
    struct k_thread data;
    K_THREAD_STACK_MEMBER(stack, CONNECTION_THREAD_STACK_SIZE);
} cipher_connection_thread_info_t;

// Send and Recv threads are identical
typedef struct
{
    k_tid_t id;
    struct k_thread data;
    K_THREAD_STACK_MEMBER(stack, TRANSPORT_THREAD_STACK_SIZE);
} cipher_transport_thread_info_t;

// Transport abstraction layer
typedef struct
{
    cipher_connection_thread_info_t connection_t;
    cipher_transport_thread_info_t send_t;
    cipher_transport_thread_info_t recv_t;
} cipher_interface_thread_group_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Deamon
 *---------------------------------------------------------------------------------------------------*/
typedef struct
{
    // user Config
    tal_config_t uplink_interface_cfg[CONFIG_UP_LINK_INTERFACE_COUNT];
    tal_config_t downlink_interface_cfg[CONFIG_DOWN_LINK_INTERFACE_COUNT];

    // Device Unique Id
    uint16_t device_id;

    // Controller thread info
    k_tid_t ctrl_t_id;
    struct k_thread ctrl_t_data;
    K_THREAD_STACK_MEMBER(ctrl_t_stack, 1024);

    // Service discovery thread info
    k_tid_t sd_t_id;
    struct k_thread sd_t_data;
    K_THREAD_STACK_MEMBER(sd_t_stack, 1024);

    // Router thread info
    k_tid_t router_t_id;
    struct k_thread router_t_data;
    K_THREAD_STACK_MEMBER(router_t_stack, 1024);

    // RPC thread info
    k_tid_t rpc_t_id;
    struct k_thread rpc_t_data;
    K_THREAD_STACK_MEMBER(rpc_t_stack, 1024);

    // Event thread info
    k_tid_t event_t_id;
    struct k_thread event_t_data;
    K_THREAD_STACK_MEMBER(event_t_stack, 1024);

    // Uplink thread groups
    cipher_interface_thread_group_t uplink_t_g[CONFIG_UP_LINK_INTERFACE_COUNT];

    // Downlink thread groups
    cipher_interface_thread_group_t downlink_t_g[CONFIG_DOWN_LINK_INTERFACE_COUNT];

    // Queues
    struct k_fifo controller_event_queue;
    struct k_fifo service_discovery_queue;
    struct k_fifo unrouted_packets_queue;
    struct k_fifo rpc_queue;
    struct k_fifo event_queue;

    // Heaps
    struct k_heap recv_buffers_heap;
    uint8_t __aligned(8) recv_buffers_heap_mem[CONFIG_CIPHER_RECV_BUFFER_SIZE * CONFIG_CIPHER_RECV_BUFFERS];
    struct k_heap unrouted_packets_heap;
    uint8_t __aligned(8) unrouted_packets_heap_mem[CONFIG_CIPHER_UNROUTED_PACKETS_HEAP];
    struct k_heap local_packets_heap;
    uint8_t __aligned(8) local_packets_heap_mem[CONFIG_CIPHER_LOCAL_PACKETS_HEAP];

} cipher_daemon_t;

bool cipher_init_daemon(cipher_daemon_t *d);

/**
 * @brief Ensure that node at end point matches protocol version, and exchange configs
 *
 * @param cfg The transport interface configuration
 * @return true If node was handshook correctly
 * @return false If node protocol version mismatch or connection issue occurs
 */
bool cipher_handshake(const tal_config_t *cfg);

void cipher_controller_thread(void *arg0, void *arg1, void *arg2);
void cipher_sd_thread(void *arg0, void *arg1, void *arg2);
void cipher_router_thread(void *arg0, void *arg1, void *arg2);
void cipher_rpc_thread(void *arg0, void *arg1, void *arg2);
void cipher_event_thread(void *arg0, void *arg1, void *arg2);

void cipher_interface_conn_thread(void *arg0, void *arg1, void *arg2);
void cipher_interface_send_thread(void *arg0, void *arg1, void *arg2);
void cipher_interface_recv_thread(void *arg0, void *arg1, void *arg2);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Controller
 *---------------------------------------------------------------------------------------------------*/

typedef enum
{
    CONTROLLER_EVENT_TYPE_SPAWN_THREAD,
    CONTROLLER_EVENT_TYPE_EXIT,

    CONTROLLER_EVENT_TYPE_MAX,
} controller_event_type_t;

typedef struct
{
    controller_event_type_t type;
} controller_event_t;

bool cipher_controller_exit(cipher_daemon_t *daemon);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Protocol
 *---------------------------------------------------------------------------------------------------*/

typedef enum
{
    CIPHER_PACKET_TYPE_SD,
    CIPHER_PACKET_TYPE_RPC,
    CIPHER_PACKET_TYPE_EVENT,

    CIPHER_PACKET_TYPE_MAX
} cipher_packet_type_t;

typedef struct
{
    cipher_packet_type_t header;
    void *payload;
} cipher_packet_t;

// Cipher Header (12 bytes)
typedef struct __attribute__((packed))
{
    uint16_t source_id;         // Up to 65536 devices on a single network
    uint16_t destination_id;    // Up to 65536 devices on a single network
    uint32_t service_id : 14;   // Up to 16384 services
    uint32_t operation_id : 8;  // Up to 256 operations per service
    uint32_t payload_len : 10;  // Header + Payload will never exceed 1024 bytes
    uint16_t sequence_num : 13; // Up to ~8MB streams (8192 sequences * 1005 bytes payload)
    uint16_t type : 3;          // Up to 8 types (RPC, event, pub/sub, admin, etc)
    uint8_t flags;              // Protocol/admin level communication (unimplemented methods, etc)
    uint8_t hop_count;          // TODO: Serdes for me
} cipher_header_t;

void cipher_print_header(const cipher_header_t *header);
bool cipher_packet_parse_header(const uint8_t *recv_buffer, uint16_t recv_buffer_size, cipher_header_t *header_buffer);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Serdes
 *---------------------------------------------------------------------------------------------------*/

typedef enum
{
    CIPHER_ERROR_OK,
    CIPHER_ERROR_INVALID_HEADER,
    CIPHER_ERROR_MAX
} cipher_error_t;

typedef struct
{
    cipher_header_t *header;
    uint8_t *raw_payload;
    size_t raw_payload_size;
    void *decoded_payload;
} cipher_decode_args_t;

typedef struct
{
    cipher_header_t *header;
    void *raw_payload;
    size_t raw_payload_size;
    uint8_t *encoded_payload;
} cipher_encode_args_t;

cipher_error_t cipher_encode_packet(cipher_encode_args_t args);
cipher_error_t cipher_decode_packet(cipher_decode_args_t args);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    Service Discovery
 *---------------------------------------------------------------------------------------------------*/
typedef struct
{
    uint16_t service_id;
    uint8_t max_hops;
} cipher_payload_sd_t;

#endif // RAL_H