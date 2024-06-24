#include "uart.h"

// Standard includes
#include <stddef.h>
#include <stdio.h>

// Zephyr includes
#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/ring_buffer.h>

// Corekinect includes
#include <corekinect/cipher/cipher.h>

// Protocol includes
#include "protos/mtib_runner_zephyr/mtib_runner_zephyr.cipher.h"

LOG_MODULE_DECLARE(app);

// Thread info
k_tid_t t_id;
struct k_thread t_data;
K_THREAD_STACK_MEMBER(t_stack, 4096);

// Devices
const struct device *uart_ports[] =
{
    DEVICE_DT_GET(DT_ALIAS(nrf9160_uart)),
    DEVICE_DT_GET(DT_ALIAS(nrf52840_uart)),
};

#define RING_BUFER_SIZE 10000

// Events
typedef struct
{
    struct k_sem data_sent_sem;
    size_t bytes_sent;
    struct k_sem recv_ready_sem;
    struct ring_buf ring_buffer;
    uint8_t ring_buffer_storage[RING_BUFER_SIZE];
} device_event_objects_t;

struct k_poll_event _events[NUM_PORTS] = {0};
static device_event_objects_t _device_event_objs[NUM_PORTS] = {0};

// Thread
static void _uart_thread(void *arg0, void *arg1, void *arg2);

// Callback
static void _uart_callback(const struct device *p_dev, struct uart_event *event, void *user_data);

// Buffers
static uart_cb_buffer_t _cb_recv_buffers[NUM_PORTS * 2] = {0};
static uart_send_buffer_t _send_buffers[NUM_PORTS];
static void _init_buffer_management(void);
static uart_send_buffer_t *_fp_get_send_buffer(void);
static void _free_send_buffer(uint8_t *buffer);
static uart_cb_buffer_t *_fp_get_cb_recv_buffer(void);
static void _free_cb_recv_buffer(uint8_t *buffer);

bool app_uart_forwarder_init(void)
{
    // Initialize a thread to handle send/recv events
    t_id = k_thread_create(&t_data,
                           t_stack,
                           K_THREAD_STACK_SIZEOF(t_stack),
                           _uart_thread,
                           NULL, NULL, NULL,
                           120,
                           0,
                           K_NO_WAIT);
    k_thread_name_set(t_id, "uart_forwarder");

    _init_buffer_management();

    // Initialize all the devices
    for (size_t i = 0; i < ARRAY_SIZE(uart_ports); i++)
    {
        // Ensure the devices are initialized
        if (!device_is_ready(uart_ports[i]))
        {
            LOG_ERR("Device %s is not ready", uart_ports[i]->name);
            return false;
        }

        // Initialize device objects
        k_sem_init(&_device_event_objs[i].recv_ready_sem, 0, 1);
        k_sem_init(&_device_event_objs[i].data_sent_sem, 0, 1);
        ring_buf_init(&_device_event_objs[i].ring_buffer, sizeof(_device_event_objs[i].ring_buffer_storage), _device_event_objs[i].ring_buffer_storage);

        // We user ASYNC uart so setup a callback
        int err = uart_callback_set(uart_ports[i], _uart_callback, &_device_event_objs[i]);
        if (err != 0)
        {
            if (err == -ENOSYS)
            {
                LOG_ERR("Callback is not supported for device %s", uart_ports[i]->name);
            }
            else if (err == -ENOTSUP)
            {
                LOG_ERR("%s", "UART async API is not enabled");
            }
            else
            {
                LOG_ERR("Error setting up UART callback for device %s, errno: %s", uart_ports[i]->name, strerror(errno));
            }

            return false;
        }
    }

    return true;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                       Enable/Disable
 *---------------------------------------------------------------------------------------------------*/

static bool uart_port_states[ARRAY_SIZE(uart_ports)] = {0};

bool app_uart_forwarder_enable(UartDeviceType device)
{
    int i = -1;

    switch (device)
    {
        case UartDeviceType_NRF9160:
            i = 0;
            break;
        case UartDeviceType_NRF82840:
            i = 1;
            break;
        default:
            LOG_ERR("Unknown device type %d", device);
            return false;
    }

    if (uart_port_states[i])
    {
        // Device is already enabled
        return true;
    }

    // Setup an initial receive buffer for this device
    uart_cb_buffer_t *rx_buffer = _fp_get_cb_recv_buffer();
    if (rx_buffer == NULL)
    {
        LOG_ERR("Error acquiring a callback receive buffer for device %s", uart_ports[i]->name);
        return false;
    }

    // Enable receive - we are ready to process events
    int err = uart_rx_enable(uart_ports[i], rx_buffer->buffer, RECV_CB_BUFFER_SIZE, 100);
    if (err != 0)
    {
        if (err == -ENOTSUP)
        {
            LOG_ERR("%s", "UART async API is not enabled");
        }
        else if (err == -EBUSY)
        {
            LOG_ERR("Receive is already in progress for device %s", uart_ports[i]->name);
        }
        else
        {
            LOG_ERR("Error enabling receive for device %s, err: %d, errno: %s", uart_ports[i]->name, err, strerror(errno));
        }

        return false;
    }

    // Set the state to enabled
    uart_port_states[i] = true;

    return true;
}

bool app_uart_forwarder_disable(UartDeviceType device)
{
    int i = -1;

    switch (device)
    {
        case UartDeviceType_NRF9160:
            i = 0;
            break;
        case UartDeviceType_NRF82840:
            i = 1;
            break;
        default:
            LOG_ERR("Unknown device type %d", device);
            return false;
    }

    if (!uart_port_states[i])
    {
        // Device is already disabled
        return true;
    }

    // Disable receive
    int err = uart_rx_disable(uart_ports[i]);
    if (err != 0)
    {
        if (err == -ENOTSUP)
        {
            LOG_ERR("%s", "UART async API is not enabled");
        }
        else if (err == -EFAULT)
        {
            LOG_ERR("No active reception for device %d", device);
        }
        else
        {
            LOG_ERR("Error disabling receive for device %d, errno: %s", device, strerror(errno));
        }

        return false;
    }

    // Set the state to disabled
    uart_port_states[i] = false;

    ring_buf_reset(&_device_event_objs[i].ring_buffer);

    return true;
}

bool app_uart_forwarder_send_data(UartDeviceType device, uint8_t *data, size_t data_size)
{
    if (data_size >= SEND_BUFFER_SIZE)
    {
        LOG_ERR("Trying to send payload with size %d when buffer is only %d bytes", data_size, SEND_BUFFER_SIZE);
        return false;
    }

    int i = -1;

    switch (device)
    {
        case UartDeviceType_NRF9160:
            i = 0;
            break;
        case UartDeviceType_NRF82840:
            i = 1;
            break;
        default:
            LOG_ERR("Unknown device type %d", device);
            return false;
    }

    // 2. Get a free send buffer
    uart_send_buffer_t *p_send_buffer = _fp_get_send_buffer();
    if (p_send_buffer == NULL)
    {
        LOG_ERR("Error acquiring send buffer for device %s", uart_ports[i]->name);
        return false;
    }

    // 3. Copy the data into said buffer
    memcpy(p_send_buffer->buffer, data, data_size);

    // 4. Call the UART async API to send
    //
    // We can pass SYS_FOREVER_US as timeout because flow control is disabled ---|
    int err = uart_tx(uart_ports[i], p_send_buffer->buffer, data_size, SYS_FOREVER_US); // <--|
    if (err != 0)
    {
        if (err == -EBUSY)
        {
            LOG_ERR("%s", "You're attempting to send data faster than this host can send on this device");
        }
        else
        {
            LOG_ERR("Unknown send error: %s", strerror(errno));
        }

        return false;
    }

    // 5. Await for the UART callback to notify, or timeout
    int res = k_sem_take(&_device_event_objs[i].data_sent_sem, K_MSEC(1000));
    if (res != 0)
    {
        if (res == -EAGAIN)
        {
            return false;
        }
        else
        {
            // Why is the send timeout = 0?
            LOG_ERR("%s", "Send semaphore returned without waiting. This is a software bug.");
            return false;
        }
    }

    _free_send_buffer(p_send_buffer->buffer);

    if (_device_event_objs[i].bytes_sent != data_size)
    {
        LOG_ERR("Unknown error occurred while sending on device %d. Sent %d, expected %d", i, _device_event_objs[i].bytes_sent, data_size);
        return false;
    }

    return true;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                     Transport Thread
 *---------------------------------------------------------------------------------------------------*/

static void _uart_thread(void *arg0, void *arg1, void *arg2)
{
    // Initialize device events
    for (size_t i = 0; i < ARRAY_SIZE(uart_ports); i++)
    {
        k_poll_event_init(&_events[i],
                          K_POLL_TYPE_SEM_AVAILABLE,
                          K_POLL_MODE_NOTIFY_ONLY,
                          &_device_event_objs[i].recv_ready_sem);
    }

    // Main loop
    while (1)
    {
        // Wait for any of the recv buffers to unblock
        int rc = k_poll(_events, ARRAY_SIZE(_events), K_FOREVER);
        if (rc != 0)
        {
            LOG_ERR("Unknown timeout in uart forwarder");
        }
        else
        {
            // Continue processing as long as there's data in any queue
            bool any_data_left = true;

            while (any_data_left)
            {
                any_data_left = false;

                // Process each queue in a round-robin fashion
                for (size_t i = 0; i < ARRAY_SIZE(_events); i++)
                {
                    if (k_sem_take(&_device_event_objs[i].recv_ready_sem, K_NO_WAIT) == 0)
                    {
                        bool queue_has_data = true;

                        while (queue_has_data)
                        {
                            queue_has_data = false;

                            // Initialize variables for the loop
                            cipher_unary_rpc_user_info_t info =
                            {
                                .destination_id = CIPHER_DESTINATION_ID_ANY,
                                .timeout_ms = 1000,
                            };

                            // Process the ring buffer once for this queue
                            UartMessageRequest request = {0};
                            request.data.size = ring_buf_get(&_device_event_objs[i].ring_buffer, request.data.bytes, sizeof(request.data.bytes));

                            // Check if there was data in the ring buffer
                            if (request.data.size > 0)
                            {
                                queue_has_data = true;
                                any_data_left = true;
                                request.device = i == 0 ? UartDeviceType_NRF9160 : UartDeviceType_NRF82840;

                                // Perform RPC with the data from the ring buffer
                                UartMessageResponse response = MtibRunnerZephyr_SigmaToPiMessageRpc(&info, request);
                                if (info.error != CIPHER_RPC_ERR_OK)
                                {
                                    LOG_ERR("Could not send uart data to orange pi, cipher err: %d", info.error);
                                }

                                if (!response.success)
                                {
                                    LOG_ERR("RPC MtibRunnerZephyr_SigmaToPiMessageRpc executed with an error: %s", response.error);
                                }

                                // Ensure fairness by checking the next queue before continuing
                                for (size_t j = (i + 1) % ARRAY_SIZE(_events); j != i; j = (j + 1) % ARRAY_SIZE(_events))
                                {
                                    if (k_sem_take(&_device_event_objs[j].recv_ready_sem, K_NO_WAIT) == 0)
                                    {
                                        k_sem_give(&_device_event_objs[j].recv_ready_sem);
                                        queue_has_data = false; // Allow switching to the next queue
                                        break;
                                    }
                                }
                            }
                        }

                        // Reset the event state after processing the queue
                        _events[i].state = K_POLL_STATE_NOT_READY;
                    }
                }
            }
        }
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                        UART Callback
 *---------------------------------------------------------------------------------------------------*/
static void _uart_callback(const struct device *p_dev, struct uart_event *event, void *user_data)
{
    device_event_objects_t *objs = (device_event_objects_t *)user_data;
    switch (event->type)
    {
        /*----------------------------------------------------
         *                                                Send
         *--------------------------------------------------*/
        case UART_TX_DONE:
            // Flow control is disabled, so we always assume that this is called when done
            objs->bytes_sent = event->data.tx.len;
            k_sem_give(&objs->data_sent_sem);

            break;
        case UART_TX_ABORTED:
            LOG_ERR("UART transmission aborted. This is a software bug. Flow control should NOT be enabled on device %s", p_dev->name);
            k_fatal_halt(0);
            break;

        /*----------------------------------------------------
         *                                                Recv
         *--------------------------------------------------*/
        case UART_RX_RDY:
            // Add received data to the ring buffer
            size_t bytes_added = ring_buf_put(&objs->ring_buffer,
                                              event->data.rx.buf + event->data.rx.offset,
                                              event->data.rx.len);

            // Only notify thread if the size is the expected on
            k_sem_give(&objs->recv_ready_sem);

            // Catch an overflow
            if (bytes_added < event->data.rx.len)
            {
                // CONFIG_CK_IFACE_RECV_RING_BUFER_SIZE
                LOG_ERR("Ring buffer overflow, %d bytes lost", event->data.rx.len - bytes_added);
                k_fatal_halt(0);
            }

            break;

        case UART_RX_BUF_REQUEST:
        {
            uart_cb_buffer_t *rx_buffer = _fp_get_cb_recv_buffer();
            if (rx_buffer == NULL)
            {
                LOG_ERR("%s", "No available receive buffers");
                k_fatal_halt(0);
            }
            else
            {
                int err = uart_rx_buf_rsp(p_dev, rx_buffer->buffer, RECV_CB_BUFFER_SIZE);
                if (err != 0)
                {
                    LOG_ERR("Could not set new UART RX buffer, err: %d", err);
                    k_fatal_halt(0);
                }
            }
        }
        break;

        case UART_RX_BUF_RELEASED:
        {
            _free_cb_recv_buffer(event->data.rx_buf.buf);
        }
        break;

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
 *                                                                                              Buffers
 *---------------------------------------------------------------------------------------------------*/
static void _init_buffer_management(void)
{
    // Send buffers
    for (size_t i = 0; i < ARRAY_SIZE(_send_buffers); ++i)
    {
        _send_buffers[i].in_use = false;
    }

    // Recv buffers
    for (size_t i = 0; i < ARRAY_SIZE(_cb_recv_buffers); i++)
    {
        _cb_recv_buffers[i].in_use = false;
    }
}

static uart_send_buffer_t *_fp_get_send_buffer(void)
{
    for (size_t i = 0; i < ARRAY_SIZE(_send_buffers); ++i)
    {
        uart_send_buffer_t *p_item = &_send_buffers[i];
        if (p_item->in_use)
        {
            continue;
        }

        p_item->in_use = true;
        return p_item;
    }

    LOG_ERR("Not enough send buffers available. Increase CONFIG_CK_IFACE_SEND_BUFFER_COUNT from %d",
            CONFIG_CK_IFACE_SEND_BUFFER_COUNT);

    return NULL;
}

static void _free_send_buffer(uint8_t *buffer)
{
    for (size_t i = 0; i < ARRAY_SIZE(_send_buffers); ++i)
    {
        uart_send_buffer_t *p_item = &_send_buffers[i];
        if (p_item->buffer != buffer)
        {
            continue;
        }

        p_item->in_use = false;
        return;
    }
}

static uart_cb_buffer_t *_fp_get_cb_recv_buffer(void)
{
    for (size_t i = 0; i < ARRAY_SIZE(_cb_recv_buffers); i++)
    {
        uart_cb_buffer_t *item = &_cb_recv_buffers[i];
        if (item->in_use)
        {
            continue;
        }

        item->in_use = true;
        return item;
    }

    /**
     * @brief The reason this is a bug is because the UART async API only needs 2 buffers per peripheral
     * instance. Something has gone terribly wrong if you get to this point. Sorry. You're on your own
     * if I'm not around. - Mateo */
    LOG_ERR("%s", "Not enough callback receive buffers available. This is a logic error in the module, report as bug");
    return NULL;
}

static void _free_cb_recv_buffer(uint8_t *buffer)
{
    for (size_t i = 0; i < ARRAY_SIZE(_cb_recv_buffers); i++)
    {
        uart_cb_buffer_t *item = &_cb_recv_buffers[i];
        if (item->buffer != buffer)
        {
            continue;
        }

        item->in_use = false;
        return;
    }
}