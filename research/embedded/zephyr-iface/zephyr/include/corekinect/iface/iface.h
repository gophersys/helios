#ifndef COREKINECT_IFACE_H
#define COREKINECT_IFACE_H

// Standard includes
#include <stdbool.h>
#include <stdint.h>

// Zephyr includes
#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#ifdef CONFIG_CK_IFACE_LIB_SOCKETS
    #include <zephyr/net/socket.h>
#else
    // #if !defined(CONFIG_CK_IFACE_LIB_SOCKETS) && !defined(CONFIG_NET_SOCKETS_POSIX_NAMES)
    // Checks if the system is little-endian
    #define IS_LITTLE_ENDIAN ((*(uint16_t *)"01") == 0x3130)

    // Converts a 16-bit short from host byte order to network byte order
    #ifndef htons
        #define htons(hostshort) (IS_LITTLE_ENDIAN ? ((hostshort) >> 8) | ((hostshort) << 8) : (hostshort))
    #endif

    // Converts a 16-bit short from network byte order to host byte order
    #ifndef ntohs
        #define ntohs(netshort) htons(netshort)
    #endif

    // Converts a 32-bit long from host byte order to network byte order
    #ifndef htonl
        #define htonl(hostlong) (IS_LITTLE_ENDIAN ? ((hostlong) >> 24) | (((hostlong) & 0x00FF0000) >> 8) | (((hostlong) & 0x0000FF00) << 8) | ((hostlong) << 24) : (hostlong))
    #endif

    // Converts a 32-bit long from network byte order to host byte order
    #ifndef ntohl
        #define ntohl(netlong) htonl(netlong)
    #endif

#endif

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                Types
 *---------------------------------------------------------------------------------------------------*/

/**
 * @struct iface_type_t
 * @brief Physical interfaces supported by abstraction layer
 */
typedef enum
{
    IFACE_TYPE_SOCKET, /**< Single socket connection */
    IFACE_TYPE_UART,   /**< UART bus connection */

    IFACE_TYPE_MAX
} iface_type_t;

/**
 * @struct iface_link_type_t
 * @brief Connection type of the interface
 */
typedef enum
{
    IFACE_LINK_TYPE_SERVER, /**< Interface behaves as a server */
    IFACE_LINK_TYPE_CLIENT, /**< Interface behaves as a client */

    IFACE_LINK_TYPE_MAX,
} iface_link_type_t;

/**
 * @struct iface_opt_t
 * @brief Available options on interface
 */
typedef enum
{
    IFACE_OPT_SEND_TIMEOUT, /**< Equivalent to socket send timeout, in millis */
    IFACE_OPT_RECV_TIMEOUT, /**< Equivalent to socket recv timeout, in millis */

    IFACE_OPT_MAX
} iface_opt_t;

/**
 * @struct iface_t
 * @brief Transport interface configuration. Fields used vary based on type
 */
typedef struct
{
    iface_type_t type;      /**< The type of interface this config belongs to */
    iface_link_type_t link; /**< The type of link of the interface */

    // Sockets
    char *p_host;         /**< If type is CLIENT, the remote host it will connect to */
    uint16_t port;        /**< If type is CLIENT, the port to which the client will connect to.
                               If type is SERVER, the port to which the listening socket will bind to */
    int listening_socket; /**< Socket used for listening (server only) */
    int client_socket;    /**< Socket used for client connections */
    bool socket_bound;    /**< Internal: server listener already bound. Managed by the
                               socket backend; leave zero-initialized. Distinguishes
                               "never bound" from a listener that landed on fd 0. */

    // Uart
    const struct device *const p_uart_dev;
} iface_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  API
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Creates a new interface of the desired type.
 *
 * Use common sense, if it's a socket then it needs a port and a host, etc. Function will assert
 * erroneous configurations passed.
 *
 * @param[in, out] p_iface The desired interface
 * @return true If the interface was created succesfully
 * @return false If there's an error. Logged to console as ERR.
 */
bool iface_create(iface_t *p_iface);

/**
 * @brief Set interface options. Works similar to POSIX sockets
 *
 * @param[in, out] p_iface The desired interface
 * @param[in] type The desired option
 * @param[in] p_option A pointer to the option struct or type
 * @param[in] option_size Size of the option struct or type
 * @return true If the option was set correctly
 * @return false If there's an error. Logged to console as ERR.
 */
bool iface_set_opt(iface_t *p_iface, iface_opt_t type, void *p_option, size_t option_size);

/**
 * @brief Connects to a remote interface end point.
 *
 * Returns immediately if a connection timeout occurred.
 *
 * @param[in, out] p_iface The desired interface
 * @param[out] timeout Indicate the caller if a timeout occured
 * @return true If a succesful connection
 * @return false If there's an error or timeout. Logged to console as ERR.
 */
bool iface_connect(iface_t *p_iface, bool *timeout);

/**
 * @brief Accepts a connection from a remote client. Timeout can be set with RECV_TIMEOUT option.
 *
 * @note Default value for UART sockets is about 60 seconds
 *
 * @param[in, out] p_iface The desired interface
 * @param[out] timeout Indicate the caller if a timeout occured
 * @return true If a connection is received before timeout
 * @return false If there's an error or timeout. Logged to console as ERR.
 */
bool iface_accept(iface_t *p_iface, bool *timeout);

/**
 * @brief Send data on interface
 *
 * @param[in, out] p_iface The desired interface
 * @param[in] p_buffer Send buffer
 * @param[in] buffer_size Size of send buffer
 * @param[out] p_send_count Number of bytes sent
 * @param[out] p_conn_closed Remote connection status
 * @param[out] p_timeout Timeout buffer
 * @return true If the data was sent succesfully
 * @return false If there's an error or timeout. Logged to console as ERR.
 */
bool iface_send(const iface_t *p_iface, const void *p_buffer, const size_t buffer_size,
                uint16_t *p_send_count, bool *p_conn_closed, bool *p_timeout);

/**
 * @brief Receive data on interface
 *
 * @param[in, out] p_iface The desired interface
 * @param[in] p_buffer Recvbuffer
 * @param[in] buffer_size Size of recv buffer
 * @param[out] p_recv_count Number of bytes received
 * @param[out] p_conn_closed Remote connection status
 * @param[out] p_timeout Timeout buffer
 * @return true If the data was received succesfully
 * @return false If there's an error or timeout. Logged to console as ERR.
 */
bool iface_recv(const iface_t *p_iface, void *p_buffer, const size_t buffer_size,
                uint16_t *p_recv_count, bool *p_conn_closed, bool *p_timeout);

/**
 * @brief Closes and cleans up resources for interface
 *
 * @param[in, out] p_iface The desired interface
 * @return true If the interface was closed correctly and all resources reclaimed
 * @return false If there's an error. Logged to consolor as ERR
 */
bool iface_close(const iface_t *p_iface);

#endif  // COREKINECT_IFACE_H