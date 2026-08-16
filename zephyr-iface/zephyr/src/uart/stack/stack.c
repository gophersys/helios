#include "stack.h"

// Standard includes
#include <stddef.h>
#include <stdio.h>

// Zephyr includes
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/net_ip.h>
#include <zephyr/sys/crc.h>
#include <zephyr/sys/ring_buffer.h>

#include "utils/assembler.h"
#include "utils/assert.h"
#include "utils/protocol.h"

LOG_MODULE_REGISTER(uart_stack, CONFIG_CK_IFACE_LIB_STACK_DEBUG_LEVEL);

/**
 * @def UART_CB_RECV_TIMEOUT_MS
 * @brief Timeout period to wait for a consecutive data to be received on the callback.
 */
#define UART_CB_RECV_TIMEOUT_MS 1

/**
 * @def DEFAULT_TIMEOUT_MS
 * @brief Default timeout for send/recv operations
 */
#define DEFAULT_TIMEOUT_MS 60000

/*-----------------------------------------------------------------------------------------------------
 *                                                                                         Data & Types
 *---------------------------------------------------------------------------------------------------*/
/**
 * @struct uart_device_event_t
 * @brief Holds all objects required for a user function call to add an event to the event loop.
 */
typedef struct
{
    uintptr_t __k_reserved;
    const struct device *p_dev;
    struct k_sem event_complete_sem;
    bool succesful;
} uart_device_event_t;

/**
 * @struct uart_cb_buffer_t
 * @brief Used by the UART async API to store received data. Shared across all sockets.
 */
typedef struct
{
    bool in_use;
    uint8_t buffer[CONFIG_CK_IFACE_RECV_CB_BUFFER_SIZE];
} uart_cb_buffer_t;

/**
 * @struct uart_send_buffer_t
 * @brief Used by the UART async API to send user data. Shared across all sockets.
 */
typedef struct
{
    bool in_use;
    uint8_t buffer[CONFIG_CK_IFACE_PROTOCOL_MAX_PAYLOAD_SIZE];
} uart_send_buffer_t;

/**
 * @brief Receive buffers for the UART callback. Shared by all device instance callbacks.
 *
 * @note Because Zephyr's UART async API uses DMA for certain hardware, these buffers have to
 * be defined as __no_cache, which is enabled by option CONFIG_NOCACHE_MEMORY
 *
 * @note At least 2 buffers are needed per device
 */
#ifdef CONFIG_NOCACHE_MEMORY
__nocache static uart_cb_buffer_t _cb_recv_buffers[CONFIG_CK_IFACE_NUM_UART_SOCKETS * 2] = {0};
#else
static uart_cb_buffer_t _cb_recv_buffers[CONFIG_CK_IFACE_NUM_UART_SOCKETS * 2] = {0};
#endif

/**
 * @brief Send buffers for the UART peripheral. Shared by all device instance callbacks.
 *
 * @note Because Zephyr's UART async API uses DMA for certain hardware, these buffers have to
 * be defined as __no_cache, which is enabled by option CONFIG_NOCACHE_MEMORY
 *
 * @note At least buffers are needed per device
 */
#ifdef CONFIG_NOCACHE_MEMORY
__nocache static uart_send_buffer_t _send_buffers[CONFIG_CK_IFACE_SEND_BUFFER_COUNT];
#else
static uart_send_buffer_t _send_buffers[CONFIG_CK_IFACE_SEND_BUFFER_COUNT];
#endif

/*-----------------------------------------------------------------------------------------------------
 *                                                                                          Private API
 *---------------------------------------------------------------------------------------------------*/
// Event handlers
bool _uart_event_register_device(uart_stack_t *p_stack, const struct device *p_dev);
bool _uart_event_unregister_device(uart_stack_t *p_stack, const struct device *p_dev);

// Buffers
static void _init_buffer_management(void);
static uart_send_buffer_t *_fp_get_send_buffer(void);
static void _free_send_buffer(uint8_t *buffer);
static uart_cb_buffer_t *_fp_get_cb_recv_buffer(void);
static void _free_cb_recv_buffer(uint8_t *buffer);

// Context helpers
static uart_dev_context_t *_fp_get_uart_dev_context(uart_stack_t *stack, const struct device *p_dev);
static uart_dev_context_t *_fp_get_uart_dev_context_from_semaphore(uart_stack_t *stack, struct k_sem *sem);

// Main transport thread
static void _uart_thread(void *arg0, void *arg1, void *arg2);

// Shared callback for all devices
static void _uart_callback(const struct device *p_dev, struct uart_event *event, void *user_data);

/*-----------------------------------------------------------------------------------------------------
 *                                                                            Public API Implementation
 *---------------------------------------------------------------------------------------------------*/
bool uart_net_init(uart_stack_t *p_stack, uart_stack_config_t cfg) {
    ASSERT_NOT_NULL(p_stack);

    if (cfg.transport_type != UART_TRANSPORT_TYPE_UDP) {
        LOG_ERR("%s", "Only UDP-like transport is implemented by UART transport layer");
        return false;
    }

    if (!p_stack->initialized) {
        // 1. Initialize the main transport thread
        p_stack->t_id = k_thread_create(&p_stack->t_data,
                                        p_stack->t_stack,
                                        K_THREAD_STACK_SIZEOF(p_stack->t_stack),
                                        _uart_thread,
                                        (void *)p_stack, NULL, NULL,
                                        CONFIG_CK_IFACE_UART_STACK_THREAD_PRIORITY,
                                        0,
                                        K_NO_WAIT);
        k_thread_name_set(p_stack->t_id, "uart_net_stack");

        // 2. Zero out the necessary fields in the stack
        p_stack->dev_count = 0;

        // 3. Initialize device specific fields
        for (size_t i = 0; i < ARRAY_SIZE(p_stack->dev_ctx); i++) {
            k_sem_init(&p_stack->dev_ctx[p_stack->dev_count].process_data_sem, 0, 1);
            k_sem_init(&p_stack->dev_ctx[p_stack->dev_count].data_sent_sem, 0, 1);
        }

        // 4. Initialize buffers
        _init_buffer_management();

        // 5. Initialize event queues
        k_fifo_init(&p_stack->register_device_queue);
        k_fifo_init(&p_stack->unregister_device_queue);

        p_stack->initialized = true;
    }

    return true;
}

bool uart_net_register_dev(uart_stack_t *p_stack, const struct device *p_dev) {
    ASSERT_NOT_NULL(p_stack);
    ASSERT_INITIALIZED(p_stack->initialized);
    ASSERT_NOT_NULL(p_dev);

    // Check that the user isn't re-registering this device
    for (size_t i = 0; i < ARRAY_SIZE(p_stack->dev_ctx); i++) {
        if (p_stack->dev_ctx[i].p_dev == p_dev) {
            LOG_WRN("Device %s already registered with stack, are you calling %s twice?", p_dev->name, __func__);
            return false;
        }
    }

    // Check that the user isn't trying to register more devices than configured at build time
    if (p_stack->dev_count >= CONFIG_CK_IFACE_NUM_UART_SOCKETS) {
        LOG_ERR(
            "More devices are trying to be registered than those configured at build time. "
            "Increase Kconfig option CONFIG_CK_IFACE_NUM_UART_SOCKETS, current value: %d",
            CONFIG_CK_IFACE_NUM_UART_SOCKETS);

        return false;
    }

    // Check that the device is ready
    if (!device_is_ready(p_dev)) {
        LOG_ERR("Device %s is not ready for use", p_dev->name);
        return false;
    }

    // Tell the main thread that a register device event is ready
    uart_device_event_t register_event =
        {
            .p_dev = p_dev,
            .succesful = false};

    k_sem_init(&register_event.event_complete_sem, 0, 1);
    k_fifo_put(&p_stack->register_device_queue, &register_event);

    // Await for the main thread to process this event
    k_sem_take(&register_event.event_complete_sem, K_FOREVER);

    if (!register_event.succesful) {
        LOG_ERR("Unable to register device %s with transport stack", p_dev->name);
        return false;
    }

    return true;
}

bool uart_net_set_opt(uart_stack_t *p_stack, const struct device *p_dev, uart_dev_ctx_opt_t opt, void *option, size_t option_size) {
    ASSERT_NOT_NULL(p_stack);
    ASSERT_INITIALIZED(p_stack->initialized);
    ASSERT_NOT_NULL(p_dev);

    uart_dev_context_t *dev_ctx = _fp_get_uart_dev_context(p_stack, p_dev);
    ASSERT_NOT_NULL(dev_ctx);

    switch (opt) {
        case UART_DEV_CTX_OPT_SEND_TIMEOUT:
            if (option_size != sizeof(dev_ctx->send_timeout_ms)) {
                LOG_ERR("Expected option size to be %zu, but got %zu", sizeof(dev_ctx->send_timeout_ms), option_size);
                return false;
            }
            memcpy(&dev_ctx->send_timeout_ms, option, sizeof(dev_ctx->send_timeout_ms));
            break;
        case UART_DEV_CTX_OPT_RECV_TIMEOUT:
            if (option_size != sizeof(dev_ctx->recv_timeout_ms)) {
                LOG_ERR("Expected option size to be %zu, but got %zu", sizeof(dev_ctx->recv_timeout_ms), option_size);
                return false;
            }
            memcpy(&dev_ctx->recv_timeout_ms, option, sizeof(dev_ctx->recv_timeout_ms));
            break;
        default:
            LOG_ERR("Unsupported UART option %d", opt);
            return false;
    }

    return true;
}

bool uart_net_get_send_timeout(uart_stack_t *p_stack, const struct device *p_dev, uint16_t *timeout_ms) {
    ASSERT_NOT_NULL(p_stack);
    ASSERT_INITIALIZED(p_stack->initialized);
    ASSERT_NOT_NULL(p_dev);
    ASSERT_NOT_NULL(timeout_ms);

    uart_dev_context_t *dev_ctx = _fp_get_uart_dev_context(p_stack, p_dev);
    ASSERT_NOT_NULL(dev_ctx);

    *timeout_ms = dev_ctx->send_timeout_ms;
    return true;
}

bool uart_net_get_recv_timeout(uart_stack_t *p_stack, const struct device *p_dev, uint16_t *timeout_ms) {
    ASSERT_NOT_NULL(p_stack);
    ASSERT_INITIALIZED(p_stack->initialized);
    ASSERT_NOT_NULL(p_dev);
    ASSERT_NOT_NULL(timeout_ms);

    uart_dev_context_t *dev_ctx = _fp_get_uart_dev_context(p_stack, p_dev);
    ASSERT_NOT_NULL(dev_ctx);

    *timeout_ms = dev_ctx->recv_timeout_ms;
    return true;
}

bool uart_net_unregister_dev(uart_stack_t *p_stack, const struct device *p_dev) {
    ASSERT_NOT_NULL(p_stack);
    ASSERT_INITIALIZED(p_stack->initialized);
    ASSERT_NOT_NULL(p_dev);

    // Tell the main thread that an unregister device event is ready
    uart_device_event_t unregister_event =
        {
            .p_dev = p_dev,
            .succesful = false};

    k_sem_init(&unregister_event.event_complete_sem, 0, 1);
    k_fifo_put(&p_stack->unregister_device_queue, &unregister_event);

    // Await for the main thread to process this event
    k_sem_take(&unregister_event.event_complete_sem, K_FOREVER);

    if (!unregister_event.succesful) {
        LOG_ERR("Unable to unregister device %s with transport stack", p_dev->name);
        return false;
    }

    return true;
}

bool uart_net_send_packet(uart_stack_t *p_stack, const struct device *p_dev, iface_packet_t *packet, bool *p_timeout) {
    ASSERT_NOT_NULL(p_stack);
    ASSERT_INITIALIZED(p_stack->initialized);
    ASSERT_NOT_NULL(p_dev);
    ASSERT_NOT_NULL(packet);
    ASSERT_NOT_NULL(p_timeout);

    *p_timeout = false;

    // 1. Find the device context in the stack
    uart_dev_context_t *dev_ctx = _fp_get_uart_dev_context(p_stack, p_dev);
    ASSERT_NOT_NULL(dev_ctx);

    // 2. Get a free send buffer
    uart_send_buffer_t *p_send_buffer = _fp_get_send_buffer();
    ASSERT_NOT_NULL(p_send_buffer);
    size_t send_buffer_size = sizeof(p_send_buffer->buffer);

    // 3. Assemble packet
    size_t bytes_packed = 0;
    if (!assembler_create_packet(&dev_ctx->assembler, p_send_buffer->buffer, send_buffer_size, &bytes_packed, packet)) {
        LOG_ERR("Assembler for device %s was unable to pack outgoing network buffer", p_dev->name);
        return false;
    }

    if (bytes_packed == 0) {
        LOG_ERR("Assembler for device %s packed 0 bytes, this is a software bug", p_dev->name);
        k_fatal_halt(0);
    }

    // 4. Call the UART async API to send
    //
    // We can pass SYS_FOREVER_US as timeout because flow control is disabled ---|
    int err = uart_tx(p_dev, p_send_buffer->buffer, bytes_packed, SYS_FOREVER_US);  // <--|
    if (err != 0) {
        if (err == -EBUSY) {
            LOG_ERR("%s", "You're attempting to send data faster than this host can send on this device");
        } else {
            LOG_ERR("Unknown send error: %s", strerror(errno));
        }

        _free_send_buffer(p_send_buffer->buffer);

        return false;
    }

    // 5. Await for the UART callback to notify, or timeout
    int res = k_sem_take(&dev_ctx->data_sent_sem, K_MSEC(dev_ctx->send_timeout_ms));
    if (res != 0) {
        if (res == -EAGAIN) {
            *p_timeout = true;
            return false;
        } else {
            // Why is the send timeout = 0?
            LOG_ERR("%s", "Send semaphore returned without waiting. This is a software bug.");
            k_fatal_halt(0);
        }
    }

    // 6. Free recv buffer
    _free_send_buffer(p_send_buffer->buffer);

    // 7. Check that we sent the entire payload
    if (dev_ctx->bytes_sent != bytes_packed) {
        LOG_ERR("Unknown error occurred while sending on device %s. Sent %d, expected %d", p_dev->name, dev_ctx->bytes_sent, bytes_packed);
        return false;
    }

    return true;
}

bool uart_net_recv_packet(uart_stack_t *p_stack, const struct device *p_dev, iface_packet_t **p_p_packet, bool *p_timeout) {
    ASSERT_NOT_NULL(p_stack);
    ASSERT_INITIALIZED(p_stack->initialized);
    ASSERT_NOT_NULL(p_dev);
    ASSERT_NOT_NULL(p_p_packet);
    ASSERT_NOT_NULL(p_timeout);

    *p_timeout = false;

    // 1. Find the device context in the stack
    uart_dev_context_t *p_dev_ctx = _fp_get_uart_dev_context(p_stack, p_dev);
    ASSERT_NOT_NULL(p_dev_ctx);

    // 2. Pop a message from the device's assembler recv queue
    if (!assembler_get_packet(&p_dev_ctx->assembler, p_p_packet, p_dev_ctx->recv_timeout_ms)) {
        LOG_ERR("An error occurred while trying to get a message from device's %s assembler", p_dev->name);
        return false;
    }

    // 3. Check if a timeout occurred
    if (*p_p_packet == NULL) {
        *p_timeout = true;
        return false;
    }

    return true;
}

bool uart_net_free_recv_packet(uart_stack_t *p_stack, const struct device *p_dev, iface_packet_t *p_packet) {
    ASSERT_NOT_NULL(p_stack);
    ASSERT_INITIALIZED(p_stack->initialized);
    ASSERT_NOT_NULL(p_dev);
    ASSERT_NOT_NULL(p_packet);

    // 1. Find the device context in the stack
    uart_dev_context_t *p_dev_ctx = _fp_get_uart_dev_context(p_stack, p_dev);
    ASSERT_NOT_NULL(p_dev_ctx);

    // 2. Let the assembler know we no longer need this buffer
    if (!assembler_free_packet(&p_dev_ctx->assembler, p_packet)) {
        LOG_ERR("An error occurred while trying to free a buffer from device's %s assembler", p_dev->name);
        return false;
    }

    return true;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        UART Callback
 *---------------------------------------------------------------------------------------------------*/
static void _uart_callback(const struct device *p_dev, struct uart_event *event, void *user_data) {
    uart_stack_t *stack = (uart_stack_t *)user_data;

    uart_dev_context_t *dev_ctx = _fp_get_uart_dev_context(stack, p_dev);
    if (dev_ctx == NULL) {
        LOG_ERR("Device %s context not found for UART device", p_dev->name);  // TODO": improve this error
        k_fatal_halt(0);
    }

    switch (event->type) {
        /*----------------------------------------------------
         *                                                Send
         *--------------------------------------------------*/
        case UART_TX_DONE:
            // Flow control is disabled, so we always assume that this is called when done
            dev_ctx->bytes_sent = event->data.tx.len;
            k_sem_give(&dev_ctx->data_sent_sem);

            break;
        case UART_TX_ABORTED:
            LOG_ERR("UART transmission aborted. This is a software bug. Flow control should NOT be enabled on device %s", p_dev->name);
            k_fatal_halt(0);
            break;

        /*----------------------------------------------------
         *                                                Recv
         *--------------------------------------------------*/
        case UART_RX_RDY:
            // LOG_ERR("data recv: %d", event->data.rx.len);
            // Add received data to the ring buffer
            size_t bytes_added = ring_buf_put(&dev_ctx->assembler.ring_buffer,
                                              event->data.rx.buf + event->data.rx.offset,
                                              event->data.rx.len);

            // Only notify thread if the size is the expected on
            if (ring_buf_size_get(&dev_ctx->assembler.ring_buffer) >= assembler_get_recv_length(&dev_ctx->assembler)) {
                k_sem_give(&dev_ctx->process_data_sem);
            }

            // Catch an overflow
            if (bytes_added < event->data.rx.len) {
                // CONFIG_CK_IFACE_RECV_RING_BUFER_SIZE
                LOG_ERR("Ring buffer overflow, %d bytes lost", event->data.rx.len - bytes_added);
                k_fatal_halt(0);
            }

            break;

        case UART_RX_BUF_REQUEST: {
            // LOG_ERR("buf request");
            uart_cb_buffer_t *rx_buffer = _fp_get_cb_recv_buffer();
            if (rx_buffer == NULL) {
                LOG_ERR("%s", "No available receive buffers");
                k_fatal_halt(0);
            } else {
                int err = uart_rx_buf_rsp(p_dev, rx_buffer->buffer, CONFIG_CK_IFACE_RECV_CB_BUFFER_SIZE);
                if (err != 0) {
                    LOG_ERR("Could not set new UART RX buffer, err: %d", err);
                    k_fatal_halt(0);
                }
            }
        } break;

        case UART_RX_BUF_RELEASED: {
            // LOG_ERR("buf released");
            _free_cb_recv_buffer(event->data.rx_buf.buf);
        } break;

        case UART_RX_DISABLED:
            break;
        case UART_RX_STOPPED:
            break;
        default:
            LOG_ERR("Unknown UART event type %d", event->type);
            k_fatal_halt(0);
            break;
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                     Transport Thread
 *---------------------------------------------------------------------------------------------------*/
static void _uart_thread(void *arg0, void *arg1, void *arg2) {
    uart_stack_t *p_stack = (uart_stack_t *)arg0;

    size_t num_events_init = 0;

    // Initialize register/unregister events
    k_poll_event_init(&p_stack->events[UART_STACK_EVENT_REGISTER],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &p_stack->register_device_queue);
    num_events_init++;

    k_poll_event_init(&p_stack->events[UART_STACK_EVENT_UNREGISTER],
                      K_POLL_TYPE_FIFO_DATA_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &p_stack->unregister_device_queue);
    num_events_init++;

    // Initialize device events
    size_t last_device_event_index = ARRAY_SIZE(p_stack->dev_ctx) + num_events_init;
    for (size_t i = num_events_init; i < last_device_event_index; i++) {
        uint8_t array_offset = i - num_events_init;

        k_poll_event_init(&p_stack->events[i],
                          K_POLL_TYPE_SEM_AVAILABLE,
                          K_POLL_MODE_NOTIFY_ONLY,
                          &p_stack->dev_ctx[array_offset].process_data_sem);
    }

    // Main loop
    while (1) {
        // Wait for any of the recv buffers to unblock
        int rc = k_poll(p_stack->events, ARRAY_SIZE(p_stack->events), K_FOREVER);
        if (rc != 0) {
            LOG_ERR("%s", "Unknown timeout in uart stack thread");
        } else {
            if (p_stack->events[UART_STACK_EVENT_REGISTER].state == K_POLL_STATE_FIFO_DATA_AVAILABLE) {
                LOG_DBG("%s", "Event UART_STACK_EVENT_REGISTER");

                uart_device_event_t *register_event = k_fifo_get(&p_stack->register_device_queue, K_NO_WAIT);
                if (register_event == NULL) {
                    LOG_ERR("%s", "Register device queue had no items in it but the event was triggerted");
                    k_fatal_halt(0);
                }

                register_event->succesful = _uart_event_register_device(p_stack, register_event->p_dev);
                k_sem_give(&register_event->event_complete_sem);
            } else if (p_stack->events[UART_STACK_EVENT_UNREGISTER].state == K_POLL_STATE_FIFO_DATA_AVAILABLE) {
                LOG_DBG("%s", "Event UART_STACK_EVENT_UNREGISTER");

                uart_device_event_t *unregister_event = k_fifo_get(&p_stack->unregister_device_queue, K_NO_WAIT);
                if (unregister_event == NULL) {
                    LOG_ERR("%s", "Unregister device queue had no items in it but the event was triggerted");
                    k_fatal_halt(0);
                }

                unregister_event->succesful = _uart_event_unregister_device(p_stack, unregister_event->p_dev);
                k_sem_give(&unregister_event->event_complete_sem);
            } else {
                LOG_DBG("%s", "Event UART_STACK_PROCESS_DATA");
                size_t last_device_event_index = ARRAY_SIZE(p_stack->dev_ctx) + num_events_init;

                for (size_t i = num_events_init; i < last_device_event_index; i++) {
                    if (p_stack->events[i].state == K_POLL_STATE_SEM_AVAILABLE) {
                        // Find the device context for this event
                        uart_dev_context_t *dev_ctx = _fp_get_uart_dev_context_from_semaphore(p_stack, &p_stack->dev_ctx[0].process_data_sem);
                        if (dev_ctx == NULL) {
                            LOG_ERR("%s", "Device context not found for UART device");
                            k_fatal_halt(0);
                        }

                        k_sem_take(&dev_ctx->process_data_sem, K_NO_WAIT);

                        // Let the packet assembler process the event
                        if (!assembler_process_data(&dev_ctx->assembler)) {
                            LOG_ERR("%s", "Assembler unable to process event");
                            k_fatal_halt(0);
                        }
                    }
                }
            }
        }

        // Reset events so that they trigger again
        for (size_t i = 0; i < ARRAY_SIZE(p_stack->events); i++) {
            p_stack->events[i].state = K_POLL_STATE_NOT_READY;
        }
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                Device Register Event
 *---------------------------------------------------------------------------------------------------*/
bool _uart_event_register_device(uart_stack_t *p_stack, const struct device *p_dev) {
    // 1. Assign a context to the device in the stack
    uart_dev_context_t *dev_ctx = &p_stack->dev_ctx[p_stack->dev_count];
    dev_ctx->p_dev = p_dev;

    // 2. Set default send/recv timeouts
    dev_ctx->send_timeout_ms = DEFAULT_TIMEOUT_MS;
    dev_ctx->recv_timeout_ms = DEFAULT_TIMEOUT_MS;

    // 3. Setup the UART callback
    int err = uart_callback_set(p_dev, _uart_callback, p_stack);
    if (err != 0) {
        if (err == -ENOSYS) {
            LOG_ERR("Callback is not supported for device %s", p_dev->name);
        } else if (err == -ENOTSUP) {
            LOG_ERR("%s", "UART async API is not enabled");
        } else {
            LOG_ERR("Error setting up UART callback for device %s, errno: %s", p_dev->name, strerror(errno));
        }

        return false;
    }

    uart_rx_disable(p_dev);  // Disable receive before enabling it (this is a Zephyr bug)

    // 4. Setup an initial receive buffer for this device
    uart_cb_buffer_t *rx_buffer = _fp_get_cb_recv_buffer();
    if (rx_buffer == NULL) {
        LOG_ERR("Error acquiring a callback receive buffer for device %s", p_dev->name);
        return false;
    }

    // 5. Initialize the packet assembler for this device
    if (!assembler_init(&dev_ctx->assembler)) {
        LOG_ERR("Error initializing packet assembler for device %s", p_dev->name);
        return false;
    }

    // 6. Enable receive - we are ready to process events
    err = uart_rx_enable(p_dev, rx_buffer->buffer, CONFIG_CK_IFACE_RECV_CB_BUFFER_SIZE, 1000 * UART_CB_RECV_TIMEOUT_MS);
    if (err != 0) {
        if (err == -ENOTSUP) {
            LOG_ERR("%s", "UART async API is not enabled");
        } else if (err == -EBUSY) {
            LOG_ERR("Receive is already in progress for device %s", p_dev->name);
        } else {
            LOG_ERR("Error enabling receive for device %s, errno: %s", p_dev->name, strerror(errno));
        }

        return false;
    }

    // 7. Increase the device count registered with this stack
    p_stack->dev_count++;
    return true;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                              Device Unregister Event
 *---------------------------------------------------------------------------------------------------*/
bool _uart_event_unregister_device(uart_stack_t *p_stack, const struct device *p_dev) {
    // Check that the device is registered with the stack
    uart_dev_context_t *dev_ctx = NULL;
    for (size_t i = 0; i < ARRAY_SIZE(p_stack->dev_ctx); i++) {
        if (p_stack->dev_ctx[i].p_dev == p_dev) {
            dev_ctx = &p_stack->dev_ctx[i];
            break;
        }
    }

    if (dev_ctx == NULL)  // If the device is not found after checking all devices
    {
        LOG_WRN("Device %s not registered with stack, are you calling %s before registering the device?", p_dev->name, __func__);
        return false;
    }

    // Take semaphore
    k_sem_reset(&dev_ctx->process_data_sem);

    // Disable receive
    int err = uart_rx_disable(p_dev);
    if (err != 0) {
        if (err == -ENOTSUP) {
            LOG_ERR("%s", "UART async API is not enabled");
        } else if (err == -EFAULT) {
            LOG_ERR("No active reception for device %s", p_dev->name);
        } else {
            LOG_ERR("Error disabling receive for device %s, errno: %s", p_dev->name, strerror(errno));
        }

        return false;
    }

    // Callback can't really be unset

    if (!assembler_reset(&dev_ctx->assembler)) {
        LOG_ERR("Error resetting assembler for device %s", p_dev->name);
        return false;
    }

    // Reset cb_recv buffers

    // Unassign a context to the device in the stack
    dev_ctx->p_dev = NULL;

    // Decrease the device count registered with this stack
    p_stack->dev_count--;

    return true;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                              Buffers
 *---------------------------------------------------------------------------------------------------*/
static void _init_buffer_management(void) {
    // Send buffers
    for (size_t i = 0; i < ARRAY_SIZE(_send_buffers); ++i) {
        _send_buffers[i].in_use = false;
    }

    // Recv buffers
    for (size_t i = 0; i < ARRAY_SIZE(_cb_recv_buffers); i++) {
        _cb_recv_buffers[i].in_use = false;
    }
}

static uart_send_buffer_t *_fp_get_send_buffer(void) {
    for (size_t i = 0; i < ARRAY_SIZE(_send_buffers); ++i) {
        uart_send_buffer_t *p_item = &_send_buffers[i];
        if (p_item->in_use) {
            continue;
        }

        p_item->in_use = true;
        return p_item;
    }

    LOG_ERR("Not enough send buffers available. Increase CONFIG_CK_IFACE_SEND_BUFFER_COUNT from %d",
            CONFIG_CK_IFACE_SEND_BUFFER_COUNT);

    return NULL;
}

static void _free_send_buffer(uint8_t *buffer) {
    for (size_t i = 0; i < ARRAY_SIZE(_send_buffers); ++i) {
        uart_send_buffer_t *p_item = &_send_buffers[i];
        if (p_item->buffer != buffer) {
            continue;
        }

        p_item->in_use = false;
        return;
    }
}

static uart_cb_buffer_t *_fp_get_cb_recv_buffer(void) {
    for (size_t i = 0; i < ARRAY_SIZE(_cb_recv_buffers); i++) {
        uart_cb_buffer_t *item = &_cb_recv_buffers[i];
        if (item->in_use) {
            continue;
        }

        item->in_use = true;
        LOG_WRN("get index: %d", i);
        return item;
    }

    /**
     * @brief The reason this is a bug is because the UART async API only needs 2 buffers per peripheral
     * instance. Something has gone terribly wrong if you get to this point. Sorry. You're on your own
     * if I'm not around. - Mateo */
    LOG_ERR("%s", "Not enough callback receive buffers available. This is a logic error in the module, report as bug");
    return NULL;
}

static void _free_cb_recv_buffer(uint8_t *buffer) {
    for (size_t i = 0; i < ARRAY_SIZE(_cb_recv_buffers); i++) {
        uart_cb_buffer_t *item = &_cb_recv_buffers[i];
        if (item->buffer != buffer) {
            continue;
        }

        item->in_use = false;
        LOG_WRN("free index: %d", i);
        return;
    }
}

static uart_dev_context_t *_fp_get_uart_dev_context(uart_stack_t *stack, const struct device *p_dev) {
    for (size_t i = 0; i < ARRAY_SIZE(stack->dev_ctx); i++) {
        if (stack->dev_ctx[i].p_dev == p_dev) {
            return &stack->dev_ctx[i];
        }
    }

    /**
     * @brief The reason this is a bug is because whent he user registers a device, we already do
     * a check to make sure they're not trying to register more devices than were defined at compile
     * time. - Mateo */
    LOG_ERR("%s", "Not enough dev_ctx items. This is a logic error in the module, report as bug");
    return NULL;
}

static uart_dev_context_t *_fp_get_uart_dev_context_from_semaphore(uart_stack_t *stack, struct k_sem *sem) {
    for (size_t i = 0; i < ARRAY_SIZE(stack->dev_ctx); i++) {
        if (&stack->dev_ctx[i].process_data_sem == sem) {
            return &stack->dev_ctx[i];
        }
    }

    /**
     * @brief The reason this is an error is because the only function that should call this method is our
     * UART callback, and by this point a semaphore was obtained when the device was registered from a dev_ctx
     * So who's calling the method? */
    LOG_ERR("%s", "Dev_ctx not found from semaphore. This is a logic error in the module, report as bug");
    return NULL;
}