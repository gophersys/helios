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
#include "protos/mtib_zephyr/mtib_zephyr.cipher.h"

LOG_MODULE_DECLARE(app);

// Thread info
k_tid_t t_id;
struct k_thread t_data;
K_THREAD_STACK_MEMBER(t_stack, 4096);

// Devices
const struct device *uart_ports[] =
{
    DEVICE_DT_GET(DT_ALIAS(nrf9160_uart)),
    // DEVICE_DT_GET(DT_ALIAS(nrf52840_uart)),
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
device_event_objects_t _device_event_objs[NUM_PORTS] = {0};

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
                           101,
                           0,
                           K_NO_WAIT);
    k_thread_name_set(t_id, "uart_forwarder");

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

        // Setup an initial receive buffer for this device
        uart_cb_buffer_t *rx_buffer = _fp_get_cb_recv_buffer();
        if (rx_buffer == NULL)
        {
            LOG_ERR("Error acquiring a callback receive buffer for device %s", uart_ports[i]->name);
            return false;
        }

        // Enable receive - we are ready to process events
        err = uart_rx_enable(uart_ports[i], rx_buffer->buffer, RECV_CB_BUFFER_SIZE, 1 * 1000);
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
    }

    return true;
}


/*-----------------------------------------------------------------------------------------------------
 *                                                                                     Transport Thread
 *---------------------------------------------------------------------------------------------------*/
static void _uart_thread(void *arg0, void *arg1, void *arg2)
{
    // Initialize device events
    for (size_t i = 0; i < ARRAY_SIZE(uart_ports) ; i++)
    {
        k_poll_event_init(&_events[i],
                          K_POLL_TYPE_SEM_AVAILABLE,
                          K_POLL_MODE_NOTIFY_ONLY,
                          &_device_event_objs->recv_ready_sem);
    }

    k_msleep(1500);

    // Main loop
    while (1)
    {
        // Wait for any of the recv buffers to unblock
        int rc = k_poll(_events, ARRAY_SIZE(_events), K_FOREVER);
        if (rc != 0)
        {
            LOG_ERR("%s", "Unknown timeout in uart forwarder");
        }
        else
        {
            for (size_t i = 0; i < ARRAY_SIZE(_events); i++)
            {
                if (_events[i].state == K_POLL_STATE_SEM_AVAILABLE)
                {
                    k_sem_take(&_device_event_objs[i].recv_ready_sem, K_NO_WAIT);

                    // Initialize variables for the loop
                    bool data_available = true;
                    static int total_sent = 0;
                    cipher_unary_rpc_user_info_t info =
                    {
                        .destination_id = CIPHER_DESTINATION_ID_ANY,
                        .timeout_ms = 100,
                    };

                    // Continue to process the ring buffer until it's empty
                    while (data_available)
                    {
                        UartMessageRequest request = {0};
                        request.data.size = ring_buf_get(&_device_event_objs[i].ring_buffer, request.data.bytes, sizeof(request.data.bytes));

                        // Check if there was data in the ring buffer
                        if (request.data.size > 0)
                        {
                            request.uart_port = 1;
                            total_sent += request.data.size;

                            // Perform RPC with the data from the ring buffer
                            UartMessageResponse response = MtibZephyr_SigmaToPiMessageRpc(&info, request);
                            if (info.error != CIPHER_RPC_ERR_OK)
                            {
                                LOG_ERR("Could not send uart data to orange pi, cipher err: %d", info.error);
                                k_fatal_halt(0);
                            }

                            if (!response.success)
                            {
                                LOG_ERR("RPC executed with an error: %s", response.error);
                                k_fatal_halt(0);
                            }
                        }
                        else
                        {
                            // If no data was read, exit the loop
                            data_available = false;
                        }
                    }
                }
            }
        }

        // Reset events so that they trigger again
        for (size_t i = 0; i < ARRAY_SIZE(_events); i++)
        {
            _events[i].state = K_POLL_STATE_NOT_READY;
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
                int err = uart_rx_buf_rsp(p_dev, rx_buffer->buffer, CONFIG_CK_IFACE_RECV_CB_BUFFER_SIZE);
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