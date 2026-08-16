#ifndef UART_STACK_H
#define UART_STACK_H

// Standard includes
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// Zephyr includes
#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/ring_buffer.h>

// Private includes
#include "utils/assembler.h"
#include "utils/protocol.h"

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        Configuration
 *---------------------------------------------------------------------------------------------------*/
/**
 * @def UART_STACK_THREAD_STACK_SIZE
 * @brief
 */
#define UART_STACK_NUM_EVENTS 2 + CONFIG_CK_IFACE_NUM_UART_SOCKETS
#define UART_STACK_EVENT_REGISTER 0
#define UART_STACK_EVENT_UNREGISTER 1

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Data & Types
 *---------------------------------------------------------------------------------------------------*/
/**
 * @enum uart_transport_type_t
 * @brief Enumerates transport type for the UART stack instance.
 */
typedef enum
{
    UART_TRANSPORT_TYPE_UDP,
    UART_TRANSPORT_TYPE_TCP,

    URAT_TRANSPORT_MAX,
} uart_transport_type_t;

/**
 * @struct uart_stack_config_t
 * @brief Structure holding the configuration fields for a stack instance.
 */
typedef struct
{
    uart_transport_type_t transport_type;
} uart_stack_config_t;

typedef enum
{
    UART_DEV_CTX_OPT_SEND_TIMEOUT, /**< Equivalent to socket send timeout, in millis */
    UART_DEV_CTX_OPT_RECV_TIMEOUT, /**< Equivalent to socket recv timeout, in millis */

    UART_STACK_DEV_CTX_OPTION_MAX
} uart_dev_ctx_opt_t;

/**
 * @struct uart_dev_context_t
 * @brief Structure holding all objects needed to handle a device instance in the stack.
 */
typedef struct
{
    const struct device *p_dev;    /**< Used to keep track of context. */
    struct k_sem process_data_sem; /**< Used to signal main thread when there's enough data in assembler to process. */
    struct k_sem data_sent_sem;
    uint16_t bytes_sent;

    assembler_t assembler;         /**< Object that puts together full packets from chunk streams. */

    uint16_t send_timeout_ms;
    uint16_t recv_timeout_ms;
} uart_dev_context_t;

/**
 * @struct uart_stack_t
 * @brief Structure holding all objects needed for a UART transport stack to work.
 */
typedef struct
{
    bool initialized; /**< Used to check if the stack has been succesfully initialized. */
    size_t dev_count; /**< Used to keep count of how many devices have been registered. */

    k_tid_t t_id;
    struct k_thread t_data;
    K_THREAD_STACK_MEMBER(t_stack, CONFIG_CK_IFACE_UART_STACK_THREAD_STACK_SIZE);

    uart_dev_context_t dev_ctx[CONFIG_CK_IFACE_NUM_UART_SOCKETS]; /**< Devices registered with this stack */

    struct k_poll_event events[UART_STACK_NUM_EVENTS]; /**< Poll events for the transport thread. */
    struct k_fifo register_device_queue;
    struct k_fifo unregister_device_queue;
} uart_stack_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                                  API
 *---------------------------------------------------------------------------------------------------*/
/**
 * @brief Initialize a new instance of a UART transport stack.
 *
 * This creates a thread to handle all devices registered with this instance, and initializes
 * all the objects used by it.
 *
 * @param[in] p_stack The stack object.
 * @param[in] cfg     The desired configuration for this stack.
 * @return true If all objects were initialized succesfully.
 * @return false If a null stack object was passed, or and invalid configuration.
 */
bool uart_net_init(uart_stack_t *p_stack, uart_stack_config_t cfg);

/**
 * @brief Registers a new UART device with the transport stack.
 *
 * Initializes all objects needed for the device, and creates a new internal device
 * context for further API calls with this device.
 *
 * @param p_stack The stack object.
 * @param p_dev   The device to be registered.
 * @return true If the device was registered succesfully.
 * @return false If there's an error. Logged to console as ERR
 */
bool uart_net_register_dev(uart_stack_t *p_stack, const struct device *p_dev);

/**
 * @brief Unregisters a UART device with the transport stack.
 *
 * Deinitializes all objects needed for the device, and cleans up all resources
 * being used by it.
 *
 * @param p_stack The stack object.
 * @param p_dev   The device to be unregistered.
 * @return true If the device was unregistered succesfully.
 * @return false If there's an error. Logged to console as ERR
 */
bool uart_net_unregister_dev(uart_stack_t *p_stack, const struct device *p_dev);

/**
 * @brief Sets options for a UART device in the transport stack.
 *
 * Only send and recv timeouts are currently supported
 *
 * @param[in] p_stack      The stack object.
 * @param[in] p_dev        The device to configure.
 * @param[in] opt          The option to set.
 * @param[in] p_option     Pointer to the option value.
 * @param[in] option_size  Size of the option value.
 * @return true If the option was set successfully.
 * @return false If there's an error in setting the option. Logged to console as ERR.
 */
bool uart_net_set_opt(uart_stack_t *p_stack, const struct device *p_dev, uart_dev_ctx_opt_t opt, void *p_option, size_t option_size);

/**
 * @brief Retrieves the current send timeout for a UART device.
 *
 * @param[in]  p_stack       The stack object.
 * @param[in]  p_dev         The device to query.
 * @param[out] p_timeout_ms  Pointer to where the timeout will be stored.
 * @return true If the timeout was retrieved successfully.
 * @return false If there's an error. Logged to console as ERR.
 */
bool uart_net_get_send_timeout(uart_stack_t *p_stack, const struct device *p_dev, uint16_t *p_timeout_ms);

/**
 * @brief Retrieves the current receive timeout for a UART device.
 *
 * @param[in]  p_stack       The stack object.
 * @param[in]  p_dev         The device to query.
 * @param[out] p_timeout_ms  Pointer to where the timeout will be stored.
 * @return true If the timeout was retrieved successfully.
 * @return false If there's an error. Logged to console as ERR.
 */
bool uart_net_get_recv_timeout(uart_stack_t *p_stack, const struct device *p_dev, uint16_t *p_timeout_ms);

/**
 * @brief Sends a packet over UART using the specified device.
 *
 * This function takes a packet and sends it over UART. It will handle
 * any necessary encoding or framing as required by the UART protocol.
 *
 * @param[in]  p_stack     The stack object.
 * @param[in]  p_dev       The device to send the packet through.
 * @param[in]  p_packet    The packet to send.
 * @param[out] p_timeout   Pointer to a boolean that indicates if a timeout occurred.
 * @return true If the packet was sent successfully.
 * @return false If there's an error or timeout. Logged to console as ERR.
 */
bool uart_net_send_packet(uart_stack_t *p_stack, const struct device *p_dev, iface_packet_t *p_packet, bool *p_timeout);

/**
 * @brief Receives a packet over UART using the specified device.
 *
 * This function waits for a packet on the UART interface. It will handle
 * any necessary decoding or unframing as required by the UART protocol.
 *
 * @note Function will return true if there's a timeout
 *
 * @param[in]  p_stack       The stack object.
 * @param[in]  p_dev         The device to receive the packet from.
 * @param[out] p_p_packet    Pointer to where the received packet will be stored.
 * @param[out] p_timeout     Pointer to a boolean that indicates if a timeout occurred.
 * @return true If a packet was received successfully.
 * @return false If there's an error or timeout. Logged to console as ERR.
 */
bool uart_net_recv_packet(uart_stack_t *p_stack, const struct device *p_dev, iface_packet_t **p_p_packet, bool *p_timeout);

/**
 * @brief Frees a received packet.
 *
 * After a packet has been processed using @ref uart_net_recv_packet, this function should be called to free
 * any resources associated with the packet.
 *
 * @param[in] p_stack   The stack object.
 * @param[in] p_dev     The device the packet was received from.
 * @param[in] p_packet  The packet to free.
 * @return true If the packet was freed successfully.
 * @return false If there's an error. Logged to console as ERR.
 */
bool uart_net_free_recv_packet(uart_stack_t *p_stack, const struct device *p_dev, iface_packet_t *p_packet);

#endif  // UART_STACK_H