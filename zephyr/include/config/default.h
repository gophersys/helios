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
#define CTRL_THREAD_STACK_SIZE 2048

#define SD_THREAD_PRIORITY 100
#define SD_THREAD_STACK_SIZE 2048

#define ROUTER_THREAD_PRIORITY 100
#define ROUTER_THREAD_STACK_SIZE 2048

#define RPC_THREAD_PRIORITY 100
#define RPC_WORKER_THREAD_STACK_SIZE 1024
#define RPC_THREAD_STACK_SIZE 2048

#define EVENT_THREAD_PRIORITY 100
#define EVENT_THREAD_STACK_SIZE 2048

#define STREAM_THREAD_PRIORITY 100
#define STREAM_THREAD_STACK_SIZE 2048

#define TRANSPORT_THREAD_BASE_PRIORITY 100
#define TRANSPORT_THREAD_STACK_SIZE 2048

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

// Network Heap. The packet-pipeline depths below dominate the daemon's static
// RAM (count * MAX_PAYLOAD each). They default to a deep pipeline for wired
// throughput, but are #ifndef-guarded so a memory-constrained target (e.g. an
// ESP32, where WiFi already claims ~50 KB) can override them at build time via
// zephyr_compile_definitions(CONFIG_LOCAL_PACKETS_COUNT=8 ...).
#ifndef CONFIG_NET_PACKETS_COUNT
#define CONFIG_NET_PACKETS_COUNT 16   // deeper pipeline for streaming throughput (also feeds the recv framer accumulator)
#endif
#define CONFIG_NET_PACKET_HEAP_SIZE (CONFIG_NET_PACKETS_COUNT * CONFIG_MAX_PAYLOAD_SIZE)

#define CONFIG_NET_PART_PACKET_HEAP_SIZE (CONFIG_NET_PACKET_HEAP_SIZE / 2)

// Unrecv packet heaps
#ifndef CONFIG_UNROUTED_PACKETS_COUNT
#define CONFIG_UNROUTED_PACKETS_COUNT 2
#endif
#define CONFIG_UNROUTED_PACKETS_HEAP_SIZE (CONFIG_UNROUTED_PACKETS_COUNT * CONFIG_MAX_PAYLOAD_SIZE)

// Local packet heaps
#ifndef CONFIG_LOCAL_PACKETS_COUNT
#define CONFIG_LOCAL_PACKETS_COUNT 32  // in-flight stream packets (send pipeline depth)
#endif
#define CONFIG_LOCAL_PACKETS_HEAP_SIZE (CONFIG_LOCAL_PACKETS_COUNT * CONFIG_MAX_PAYLOAD_SIZE)

#endif  // DEFAULT_H