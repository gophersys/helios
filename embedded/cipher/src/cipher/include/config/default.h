#ifndef DEFAULT_H
#define DEFAULT_H

// Number of interfaces
#define CONFIG_UP_LINK_INTERFACE_COUNT 1
#define CONFIG_DOWN_LINK_INTERFACE_COUNT 1

/*-----------------------------------------------------------------------------------------------------
 *                                                                                            Debugging
 *---------------------------------------------------------------------------------------------------*/
#define TAL_LOG_LEVEL LOG_LEVEL_INF

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Threads
 *---------------------------------------------------------------------------------------------------*/
#define CONTROLLER_THREAD_PRIORITY 100
#define CONTROLLER_THREAD_STACK_SIZE 1024

#define SD_THREAD_PRIORITY 100
#define SD_THREAD_STACK_SIZE 1024

#define ROUTER_THREAD_PRIORITY 100
#define ROUTER_THREAD_STACK_SIZE 1024

#define RPC_THREAD_PRIORITY 100
#define RPC_THREAD_STACK_SIZE 1024

#define EVENT_THREAD_PRIORITY 100
#define EVENT_THREAD_STACK_SIZE 1024

#define CONNECTION_THREAD_PRIORITY 100
#define CONNECTION_THREAD_STACK_SIZE 1024

#define TRANSPORT_THREAD_PRIORITY 100
#define TRANSPORT_THREAD_STACK_SIZE 1024

/*-----------------------------------------------------------------------------------------------------
 *                                                                                               Deamon
 *---------------------------------------------------------------------------------------------------*/

// The version of the cipher header used
#define CIPHER_CONFIG_PROTOCOL_VERSION (uint16_t)1

// Maximum allowed packet size (header + payload)
#define CIPHER_CONFIG_MAX_PAYLOAD_SIZE 1024

// Recv Buffer Pool. Used to store raw network packets on recv()
#define CONFIG_CIPHER_RECV_BUFFER_SIZE CIPHER_CONFIG_MAX_PAYLOAD_SIZE
#define CONFIG_CIPHER_RECV_BUFFERS 5

// Send Buffer Pool
#define CONFIG_CIPHER_SEND_BUFFER_SIZE CIPHER_CONFIG_MAX_PAYLOAD_SIZE
#define CONFIG_CIPHER_SEND_BUFFERS 5

// Unrecv packet heaps
#define CONFIG_CIPHER_UNROUTED_PACKETS_HEAP 2048

// Local packet heaps
#define CONFIG_CIPHER_LOCAL_PACKETS_HEAP 2048

#endif // DEFAULT_H