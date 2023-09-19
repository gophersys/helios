#ifndef TAL_H
#define TAL_H

// Standard includes
#include <stdbool.h>
#include <stdint.h>

// Zephyr includes
#include <zephyr/logging/log.h>

// Cipher includes
#include "config.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                Types
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Interfaces supported
 */
typedef enum
{
    TAL_INTERFACE_TYPE_SOCKET,
    TAL_INTERFACE_TYPE_UART,

    TAL_INTERFACE_TYPE_MAX
} tal_interface_type_t;

/**
 * @brief The kind of connection to the remote end
 */
typedef enum
{
    TAL_LINK_TYPE_UPLINK,   // Interface is the client
    TAL_LINK_TYPE_DOWNLINK, // Interface is the server

    TAL_LINK_TYPE_MAX,
} tal_link_type_t;

/**
 * @brief Available options on interface
 */
typedef enum
{
    TAL_OPTION_SEND_TIMEOUT, // uint16_t in millis
    TAL_OPTION_RECV_TIMEOUT, // uint16_t in millis

    TAL_OPTION_MAX
} tal_option_type_t;

/**
 * @brief Used to hold all interface metadata. All fields are not mandatory
 */
typedef struct
{
    tal_interface_type_t type;
    tal_link_type_t link;

    // socket
    uint16_t port;
    char *host;
    uint16_t socket;

    uint16_t _id;
} tal_interface_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  API
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Creates a new interface of the desired type.
 *
 * Use common sense, if it's a socket then it needs a port and a host, etc. Function will assert
 * erroneous configurations passed.
 *
 * @param iface The desired interface
 * @return true If the interface was created succesfully
 * @return false If an error occurs. Implementation specific, printed to LOG_WRN
 */
bool tal_create(tal_interface_t *iface);

/**
 * @brief Set interface options. Works similar to POSIX sockets
 *
 * @param iface The desired interface
 * @param type The desired option
 * @param option A pointer to the option struct or type
 * @param option_size Size of the option struct or type
 * @return true If the option was set correctly
 * @return false If an error occurs. Implementation specific, printed to LOG_WRN
 */
bool tal_set_opt(tal_interface_t *iface, tal_option_type_t type, void *option, size_t option_size);

/**
 * @brief Connects to a remote interface end point. Timeout can be set with SEND_TIMEOUT option
 *
 * @param iface The desired interface
 * @param timeout Indicate the caller if a timeout occured
 * @return true If a succesful connection
 * @return false If an error occurs. Implementation specific, printed to LOG_WRN
 */
bool tal_connect(tal_interface_t *iface, bool *timeout);

/**
 * @brief Accepts a connection from a remote client. Timeout can be set with RECV_TIMEOUT option
 *
 * @param iface The desired interface
 * @param timeout Indicate the caller if a timeout occured
 * @return true If a connection is received before timeout
 * @return false If an error occurs. Implementation specific, printed to LOG_WRN
 */
bool tal_accept(tal_interface_t *iface, bool *timeout);

/**
 * @brief Send data on interface
 *
 * @param iface The desired interface
 * @param buffer Send buffer
 * @param buffer_size Size of send buffer
 * @param send_count Number of bytes sent
 * @param conn_closed Remote connection status
 * @return true If the data was sent succesfully
 * @return false If an error occurs. Implementation specific, printed to LOG_WRN
 */
bool tal_send(const tal_interface_t *iface, const void *buffer, const size_t buffer_size,
              uint16_t *send_count, bool *conn_closed);

/**
 * @brief Receive data on interface
 *
 * @param iface The desired interface
 * @param buffer Recv buffer
 * @param buffer_size Size of recv buffer
 * @param recv_count Number of bytes received
 * @param conn_closed Remote connection status
 * @return true If the data was received succesfully
 * @return false If an error occurs. Implementation specific, printed to LOG_WRN
 */
bool tal_recv(const tal_interface_t *iface, void *buffer, const size_t buffer_size,
              uint16_t *recv_count, bool *conn_closed);

/**
 * @brief Closes and cleans up resources for interface
 *
 * @param iface
 * @return true
 * @return false
 */
bool tal_close(const tal_interface_t *iface);

#endif // TAL_H