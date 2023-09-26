#ifndef DEFAULT_H
#define DEFAULT_H

// Number of interfaces
#define CONFIG_UP_LINK_IFACE_COUNT 1
#define CONFIG_DOWN_LINK_IFACE_COUNT 1

/*-----------------------------------------------------------------------------------------------------
 *                                                                                            Debugging
 *---------------------------------------------------------------------------------------------------*/
#define REGISTRY_LOG_LEVEL LOG_LEVEL_INF
#define ROUTER_LOG_LEVEL LOG_LEVEL_WRN
#define SD_LOG_LEVEL LOG_LEVEL_WRN
#define EVENT_LOG_LEVEL LOG_LEVEL_WRN
#define RPC_LOG_LEVEL LOG_LEVEL_WRN
#define DAEMON_LOG_LEVEL LOG_LEVEL_INF
#define IFACE_LOG_LEVEL LOG_LEVEL_INF
#define TAL_LOG_LEVEL LOG_LEVEL_WRN

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Services
 *---------------------------------------------------------------------------------------------------*/
#define CONFIG_MAX_NUM_SERVICES 10
#define CONFIG_CIPHER_NAME_LEN 16

/*-----------------------------------------------------------------------------------------------------
 *                                                                                           Interfaces
 *---------------------------------------------------------------------------------------------------*/

// Count of semaphore used to indicate a connection. 1 for send thread and 1 for recv thread
#define CONFIG_IFACE_CONN_SEM_COUNT 2

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Threads
 *---------------------------------------------------------------------------------------------------*/
#define CONTROLLER_THREAD_PRIORITY 90
#define CONTROLLER_THREAD_STACK_SIZE 1024

#define SD_THREAD_PRIORITY 100
#define SD_THREAD_STACK_SIZE 1024

#define ROUTER_THREAD_PRIORITY 100
#define ROUTER_THREAD_STACK_SIZE 1024

#define RPC_THREAD_PRIORITY 100
#define RPC_THREAD_STACK_SIZE 1024

#define EVENT_THREAD_PRIORITY 100
#define EVENT_THREAD_STACK_SIZE 1024

#define TRANSPORT_THREAD_BASE_PRIORITY 100
#define TRANSPORT_THREAD_STACK_SIZE 2048

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Deamon
 *---------------------------------------------------------------------------------------------------*/

// The version of the cipher header used
#define CIPHER_CONFIG_PROTOCOL_VERSION (uint16_t)1

// Maximum allowed packet size (header + payload)
#define CONFIG_MAX_PAYLOAD_SIZE 1024

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

#define CONFIG_CTRL_EVENTS_HEAP_SIZE 128

#endif  // DEFAULT_H