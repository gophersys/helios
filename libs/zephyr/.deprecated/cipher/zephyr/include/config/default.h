#ifndef DEFAULT_H
#define DEFAULT_H

// Number of interfaces
// #define CONFIG_CIPHER_CLIENT_IFACE_COUNT 2
// #define CONFIG_CK_CIPHER_SERVER_IFACE_COUNT 2

/*-----------------------------------------------------------------------------------------------------
 *                                                                                            Debugging
 *---------------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Services
 *---------------------------------------------------------------------------------------------------*/
#define CONFIG_MAX_NUM_CONCURRENT_RPCS 3

#define CONFIG_CIPHER_LOCAL_ADDR 0x0000
#define CONFIG_CIPHER_ANY_ADDR 0xFFFF

#define CONFIG_MAX_NUM_OPS_PER_SERVICE 15

#define CONFIG_MAX_NUM_DEVICES_PER_IFACE 5

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Interfaces
 *---------------------------------------------------------------------------------------------------*/

// Count of semaphore used to indicate a connection. 1 for send thread and 1 for recv thread
#define CONFIG_IFACE_CONN_SEM_COUNT 2

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Threads
 *---------------------------------------------------------------------------------------------------*/
#define CTRL_THREAD_PRIORITY 90
#define CTRL_THREAD_STACK_SIZE 1024

#define SD_THREAD_PRIORITY 100
#define SD_THREAD_STACK_SIZE 1024

#define ROUTER_THREAD_PRIORITY 100
#define ROUTER_THREAD_STACK_SIZE 1024

#define RPC_THREAD_PRIORITY 100
#define RPC_WORKER_THREAD_STACK_SIZE 512
#define RPC_THREAD_STACK_SIZE 1024

#define EVENT_THREAD_PRIORITY 100
#define EVENT_THREAD_STACK_SIZE 1024

#define STREAM_THREAD_PRIORITY 100
#define STREAM_THREAD_STACK_SIZE 1024

#define TRANSPORT_THREAD_BASE_PRIORITY 100
#define TRANSPORT_THREAD_STACK_SIZE 1024

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Deamon
 *---------------------------------------------------------------------------------------------------*/

// The version of the cipher header used
#define CIPHER_CONFIG_PROTOCOL_VERSION (uint16_t)1

// Maximum allowed packet size (header + payload)
#define CONFIG_MAX_PAYLOAD_SIZE 1024

// Ctrl events heap
#define CONFIG_CTRL_EVENTS_HEAP_SIZE 256

// RPC events heap
#define CONFIG_RPC_EVENTS_HEAP_SIZE 1024

// Network Heap
#define CONFIG_NET_PACKETS_COUNT 4
#define CONFIG_NET_PACKET_HEAP_SIZE (CONFIG_NET_PACKETS_COUNT * CONFIG_MAX_PAYLOAD_SIZE)

#define CONFIG_NET_PART_PACKET_HEAP_SIZE (CONFIG_NET_PACKET_HEAP_SIZE / 2)

// Unrecv packet heaps
#define CONFIG_UNROUTED_PACKETS_COUNT 2
#define CONFIG_UNROUTED_PACKETS_HEAP_SIZE (CONFIG_UNROUTED_PACKETS_COUNT * CONFIG_MAX_PAYLOAD_SIZE)

// Local packet heaps
#define CONFIG_LOCAL_PACKETS_COUNT 2
#define CONFIG_LOCAL_PACKETS_HEAP_SIZE (CONFIG_LOCAL_PACKETS_COUNT * CONFIG_MAX_PAYLOAD_SIZE)

#endif  // DEFAULT_H