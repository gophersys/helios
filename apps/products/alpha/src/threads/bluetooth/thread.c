#include "thread.h"

// Standard includes
#include <stdbool.h>
#include <string.h>

// Zephyr includes
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/conn.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/bluetooth/uuid.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/logging/log_ctrl.h>
#include <zephyr/sys/reboot.h>
#include <zephyr/sys/sys_heap.h>

// Thread includes
#include "types.h"

LOG_MODULE_REGISTER(bluetooth_t, LOG_LEVEL_INF);

/*----------------------------------------------------------------------------------------
 *                                                                           Configuration
 *--------------------------------------------------------------------------------------*/

// Sensor service UUID
#define BT_UUID_SENSOR_SERVICE_VAL BT_UUID_128_ENCODE(0x12345678, 0x1234, 0x5678, 0x1234, 0x56789abcdef0)
static struct bt_uuid_128 sensor_service_uuid = BT_UUID_INIT_128(BT_UUID_SENSOR_SERVICE_VAL);

// PPG 1Hz vitals data UUID
#define BT_UUID_PPG_1HZ_VITALS_DATA_VAL BT_UUID_128_ENCODE(0x12345678, 0x1234, 0x5678, 0x1234, 0x56789abcdef1)
static struct bt_uuid_128 ppg_1hz_vitals_data_uuid = BT_UUID_INIT_128(BT_UUID_PPG_1HZ_VITALS_DATA_VAL);

// PPG 25Hz intensity data UUID
#define BT_UUID_PPG_25HZ_INTENSITY_DATA_VAL BT_UUID_128_ENCODE(0x12345678, 0x1234, 0x5678, 0x1234, 0x56789abcdef2)
static struct bt_uuid_128 ppg_25hz_intensity_data_uuid = BT_UUID_INIT_128(BT_UUID_PPG_25HZ_INTENSITY_DATA_VAL);

// PPG 32Hz intensity data UUID
#define BT_UUID_PPG_32HZ_INTENSITY_DATA_VAL BT_UUID_128_ENCODE(0x12345678, 0x1234, 0x5678, 0x1234, 0x56789abcdef3)
static struct bt_uuid_128 ppg_32hz_intensity_data_uuid = BT_UUID_INIT_128(BT_UUID_PPG_32HZ_INTENSITY_DATA_VAL);

// Accelerometer 25Hz data UUID
#define BT_UUID_ACCEL_25HZ_DATA_VAL BT_UUID_128_ENCODE(0x12345678, 0x1234, 0x5678, 0x1234, 0x56789abcdef4)
static struct bt_uuid_128 accel_25hz_data_uuid = BT_UUID_INIT_128(BT_UUID_ACCEL_25HZ_DATA_VAL);

// Accelerometer 32Hz data UUID
#define BT_UUID_ACCEL_32HZ_DATA_VAL BT_UUID_128_ENCODE(0x12345678, 0x1234, 0x5678, 0x1234, 0x56789abcdef5)
static struct bt_uuid_128 accel_32hz_data_uuid = BT_UUID_INIT_128(BT_UUID_ACCEL_32HZ_DATA_VAL);

// PSP Input PPG 32Hz intensity data UUID
#define BT_UUID_PSP_32HZ_INTENSITY_DATA_VAL BT_UUID_128_ENCODE(0x12345678, 0x1234, 0x5678, 0x1234, 0x56789abcdef6)
static struct bt_uuid_128 psp_32hz_ppg_intensity_data_uuid = BT_UUID_INIT_128(BT_UUID_PSP_32HZ_INTENSITY_DATA_VAL);

// PSP Input Accelerometer 32Hz data UUID
#define BT_UUID_PSP_32HZ_ACCEL_DATA_VAL BT_UUID_128_ENCODE(0x12345678, 0x1234, 0x5678, 0x1234, 0x56789abcdef7)
static struct bt_uuid_128 psp_32hz_accel_data_uuid = BT_UUID_INIT_128(BT_UUID_PSP_32HZ_ACCEL_DATA_VAL);

// PSP Input PPG 32Hz read intensity data UUID
#define BT_UUID_PSP_32HZ_READ_INTENSITY_DATA_VAL BT_UUID_128_ENCODE(0x12345678, 0x1234, 0x5678, 0x1234, 0x56789abcdef8)
static struct bt_uuid_128 psp_32hz_read_ppg_intensity_data_uuid = BT_UUID_INIT_128(BT_UUID_PSP_32HZ_READ_INTENSITY_DATA_VAL);

// PSP Input Accelerometer 32Hz read data UUID
#define BT_UUID_PSP_32HZ_READ_ACCEL_DATA_VAL BT_UUID_128_ENCODE(0x12345678, 0x1234, 0x5678, 0x1234, 0x56789abcdef9)
static struct bt_uuid_128 psp_32hz_read_accel_data_uuid = BT_UUID_INIT_128(BT_UUID_PSP_32HZ_READ_ACCEL_DATA_VAL);

/*----------------------------------------------------------------------------------------
 *                                                                       Private Functions
 *--------------------------------------------------------------------------------------*/
// There's a single intance of the thread
static bluetooth_thread_t *_p_thread = NULL;
static void bluetooth_thread_entry(void *p_arg0, void *p_arg1, void *p_arg2);

/*----------------------------------------------------------------------------------------
 *                                                                      Service Definition
 *--------------------------------------------------------------------------------------*/

// CCC change callback
static void ppg_1hz_vitals_data_ccc_cfg_changed(const struct bt_gatt_attr *attr, uint16_t value) {
    _p_thread->notify_1hz_vitals_enabled = (value == BT_GATT_CCC_NOTIFY);
}

static void ppg_25hz_intensity_data_ccc_cfg_changed(const struct bt_gatt_attr *attr, uint16_t value) {
    _p_thread->notify_25hz_ppg_intensity_enabled = (value == BT_GATT_CCC_NOTIFY);
}

static void ppg_32hz_intensity_data_ccc_cfg_changed(const struct bt_gatt_attr *attr, uint16_t value) {
    _p_thread->notify_32hz_ppg_intensity_enabled = (value == BT_GATT_CCC_NOTIFY);
}

static void accel_25hz_data_ccc_cfg_changed(const struct bt_gatt_attr *attr, uint16_t value) {
    _p_thread->notify_25hz_accel_enabled = (value == BT_GATT_CCC_NOTIFY);
}

static void accel_32hz_data_ccc_cfg_changed(const struct bt_gatt_attr *attr, uint16_t value) {
    _p_thread->notify_32hz_accel_enabled = (value == BT_GATT_CCC_NOTIFY);
}

static void psp_32hz_ppg_intensity_data_ccc_cfg_changed(const struct bt_gatt_attr *attr, uint16_t value) {
    _p_thread->notify_32hz_psp_ppg_intensity_enabled = (value == BT_GATT_CCC_NOTIFY);
}

static void psp_32hz_accel_data_ccc_cfg_changed(const struct bt_gatt_attr *attr, uint16_t value) {
    _p_thread->notify_32hz_psp_accel_enabled = (value == BT_GATT_CCC_NOTIFY);
}

static void psp_32hz_read_ppg_intensity_data_ccc_cfg_changed(const struct bt_gatt_attr *attr, uint16_t value) {
    _p_thread->notify_32hz_psp_read_ppg_intensity_enabled = (value == BT_GATT_CCC_NOTIFY);
}

static void psp_32hz_read_accel_data_ccc_cfg_changed(const struct bt_gatt_attr *attr, uint16_t value) {
    _p_thread->notify_32hz_psp_read_accel_enabled = (value == BT_GATT_CCC_NOTIFY);
}

// Attribute enumeration (multiply by 3 and add 1 for actual characteristic value handle)
typedef enum {
    BLUETOOTH_ATTRIBUTE_VITALS_1HZ = 2,
    BLUETOOTH_ATTRIBUTE_PPG_INTENSITY_25HZ = 5,  // Value handle
    BLUETOOTH_ATTRIBUTE_PPG_INTENSITY_32HZ = 8,
    BLUETOOTH_ATTRIBUTE_ACCEL_25HZ = 11,
    BLUETOOTH_ATTRIBUTE_ACCEL_32HZ = 14,
    BLUETOOTH_ATTRIBUTE_PSP_PPG_INTENSITY_32HZ = 17,
    BLUETOOTH_ATTRIBUTE_PSP_ACCEL_32HZ = 20,
    BLUETOOTH_ATTRIBUTE_PSP_READ_PPG_INTENSITY_32HZ = 23,
    BLUETOOTH_ATTRIBUTE_PSP_READ_ACCEL_32HZ = 26,
} bluetooth_thread_attribute_t;

// Service Definition
BT_GATT_SERVICE_DEFINE(sensor_svc,
                       BT_GATT_PRIMARY_SERVICE(&sensor_service_uuid),

                       // PPG 1Hz vitals data characteristic
                       BT_GATT_CHARACTERISTIC(&ppg_1hz_vitals_data_uuid.uuid,
                                              BT_GATT_CHRC_NOTIFY | BT_GATT_CHRC_READ,
                                              BT_GATT_PERM_READ,
                                              NULL, NULL, NULL),
                       BT_GATT_CCC(ppg_1hz_vitals_data_ccc_cfg_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),

                       // PPG 25Hz intensity data characteristic
                       BT_GATT_CHARACTERISTIC(&ppg_25hz_intensity_data_uuid.uuid,
                                              BT_GATT_CHRC_NOTIFY | BT_GATT_CHRC_READ,
                                              BT_GATT_PERM_READ,
                                              NULL, NULL, NULL),
                       BT_GATT_CCC(ppg_25hz_intensity_data_ccc_cfg_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),

                       // PPG 32Hz intensity data characteristic
                       BT_GATT_CHARACTERISTIC(&ppg_32hz_intensity_data_uuid.uuid,
                                              BT_GATT_CHRC_NOTIFY | BT_GATT_CHRC_READ,
                                              BT_GATT_PERM_READ,
                                              NULL, NULL, NULL),
                       BT_GATT_CCC(ppg_32hz_intensity_data_ccc_cfg_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),

                       // Accelerometer 25Hz data characteristic
                       BT_GATT_CHARACTERISTIC(&accel_25hz_data_uuid.uuid,
                                              BT_GATT_CHRC_NOTIFY | BT_GATT_CHRC_READ,
                                              BT_GATT_PERM_READ,
                                              NULL, NULL, NULL),
                       BT_GATT_CCC(accel_25hz_data_ccc_cfg_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),

                       // Accelerometer 32Hz data characteristic
                       BT_GATT_CHARACTERISTIC(&accel_32hz_data_uuid.uuid,
                                              BT_GATT_CHRC_NOTIFY | BT_GATT_CHRC_READ,
                                              BT_GATT_PERM_READ,
                                              NULL, NULL, NULL),
                       BT_GATT_CCC(accel_32hz_data_ccc_cfg_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),

                       // PSP Input PPG 32Hz intensity data characteristic
                       BT_GATT_CHARACTERISTIC(&psp_32hz_ppg_intensity_data_uuid.uuid,
                                              BT_GATT_CHRC_NOTIFY | BT_GATT_CHRC_READ,
                                              BT_GATT_PERM_READ,
                                              NULL, NULL, NULL),
                       BT_GATT_CCC(psp_32hz_ppg_intensity_data_ccc_cfg_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),

                       // PSP Input Accelerometer 32Hz data characteristic
                       BT_GATT_CHARACTERISTIC(&psp_32hz_accel_data_uuid.uuid,
                                              BT_GATT_CHRC_NOTIFY | BT_GATT_CHRC_READ,
                                              BT_GATT_PERM_READ,
                                              NULL, NULL, NULL),
                       BT_GATT_CCC(psp_32hz_accel_data_ccc_cfg_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),

                       // PSP Input PPG 32Hz read intensity data characteristic
                       BT_GATT_CHARACTERISTIC(&psp_32hz_read_ppg_intensity_data_uuid.uuid,
                                              BT_GATT_CHRC_NOTIFY | BT_GATT_CHRC_READ,
                                              BT_GATT_PERM_READ,
                                              NULL, NULL, NULL),
                       BT_GATT_CCC(psp_32hz_read_ppg_intensity_data_ccc_cfg_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),

                       // PSP Input Accelerometer 32Hz read data characteristic
                       BT_GATT_CHARACTERISTIC(&psp_32hz_read_accel_data_uuid.uuid,
                                              BT_GATT_CHRC_NOTIFY | BT_GATT_CHRC_READ,
                                              BT_GATT_PERM_READ,
                                              NULL, NULL, NULL),
                       BT_GATT_CCC(psp_32hz_read_accel_data_ccc_cfg_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE));

/*----------------------------------------------------------------------------------------
 *                                                                               Callbacks
 *--------------------------------------------------------------------------------------*/
static void connected(struct bt_conn *conn, uint8_t err) {
    if (err) {
        LOG_ERR("Connection failed (err %u)", err);
        return;
    }

    // Store the connection handle
    _p_thread->current_conn = bt_conn_ref(conn);

    // Wake up the thread
    k_sem_give(&_p_thread->connected_sem);
}

static void disconnected(struct bt_conn *conn, uint8_t reason) {
    _p_thread->current_conn = NULL;

    // Wake up the thread
    k_sem_give(&_p_thread->disconnected_sem);
}

// MTU updated callback
static void mtu_updated(struct bt_conn *conn, uint16_t tx, uint16_t rx) {
    LOG_INF("Updated MTU: TX: %d RX: %d bytes", tx, rx);
}

// Register both connection and GATT callbacks
BT_CONN_CB_DEFINE(conn_callbacks) = {
    .connected = connected,
    .disconnected = disconnected,
};

static struct bt_gatt_cb gatt_callbacks = {
    .att_mtu_updated = mtu_updated,
};

/*----------------------------------------------------------------------------------------
 *                                                                        Advertising Data
 *--------------------------------------------------------------------------------------*/
static const struct bt_data ad[] = {
    BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
    BT_DATA_BYTES(BT_DATA_UUID128_ALL, BT_UUID_SENSOR_SERVICE_VAL),
};

static const struct bt_data sd[] = {
    BT_DATA(BT_DATA_NAME_COMPLETE, CONFIG_BT_DEVICE_NAME, sizeof(CONFIG_BT_DEVICE_NAME) - 1),
};

/*----------------------------------------------------------------------------------------
 *                                                                          Initialization
 *--------------------------------------------------------------------------------------*/
static void timer_1hz_handler(struct k_timer *timer) {
    k_sem_give(&_p_thread->timer_sem_1hz);
}

static void timer_25hz_handler(struct k_timer *timer) {
    k_sem_give(&_p_thread->timer_sem_25hz);
}

static void timer_32hz_handler(struct k_timer *timer) {
    k_sem_give(&_p_thread->timer_sem_32hz);
}

/*----------------------------------------------------------------------------------------
 *                                                                          Initialization
 *--------------------------------------------------------------------------------------*/
bool bluetooth_thread_init(const bluetooth_thread_config_t *p_config, bluetooth_thread_t *p_thread) {
    int err;

    // Initialize Bluetooth
    err = bt_enable(NULL);
    if (err) {
        LOG_ERR("Bluetooth init failed (err %d)", err);
        return false;
    }

    // Register GATT callbacks
    bt_gatt_cb_register(&gatt_callbacks);

    // Start advertising
    err = bt_le_adv_start(BT_LE_ADV_CONN, ad, ARRAY_SIZE(ad), sd, ARRAY_SIZE(sd));
    if (err) {
        LOG_ERR("Advertising failed to start (err %d)", err);
        return false;
    }

    // Initialize thread objects
    k_sem_init(&p_thread->connected_sem, 0, 1);
    k_sem_init(&p_thread->disconnected_sem, 0, 1);
    k_sem_init(&p_thread->timer_sem_1hz, 0, 1);
    k_sem_init(&p_thread->timer_sem_25hz, 0, 1);
    k_sem_init(&p_thread->timer_sem_32hz, 0, 1);
    k_fifo_init(&p_thread->data_fifo_1hz);
    k_fifo_init(&p_thread->data_fifo_25hz);
    k_fifo_init(&p_thread->data_fifo_32hz);
    k_fifo_init(&p_thread->data_fifo_psp_32hz);
    k_fifo_init(&p_thread->data_fifo_psp_read_32hz);
    k_timer_init(&p_thread->timer_1hz, &timer_1hz_handler, NULL);
    k_timer_init(&p_thread->timer_25hz, &timer_25hz_handler, NULL);
    k_timer_init(&p_thread->timer_32hz, &timer_32hz_handler, NULL);
    k_heap_init(&p_thread->data_heap, &p_thread->data_heap_mem, sizeof(p_thread->data_heap_mem));

    // Assign configuration
    p_thread->config = p_config;
    _p_thread = p_thread;

    // Initialize thread
    p_thread->tid = k_thread_create(&p_thread->thread,
                                    p_thread->stack,
                                    CONFIG_BLUETOOTH_THREAD_STACK_SIZE,
                                    (k_thread_entry_t)bluetooth_thread_entry,
                                    p_thread,
                                    NULL,
                                    NULL,
                                    CONFIG_BLUETOOTH_THREAD_PRIORITY,
                                    0,
                                    K_NO_WAIT);

    k_thread_name_set(&p_thread->thread, "bluetooth");

    LOG_INF("Bluetooth initialized and advertising");

    return true;
}

bool bluetooth_send_sensor_data(bluetooth_thread_data_type_t type, uint8_t *p_data, size_t length) {
    // Check if the thread is initialized
    if (_p_thread == NULL) {
        return true;
    }

    // Check if the data type is enabled
    switch (type) {
        case BLUETOOTH_THREAD_DATA_TYPE_VITALS_1HZ:
            if (!_p_thread->config->vitals_1hz_enabled) {
                return true;
            }
            break;
        case BLUETOOTH_THREAD_DATA_TYPE_SENSOR_DATA_25HZ:
            if (!_p_thread->config->sensor_data_25hz_enabled) {
                return true;
            }
            break;
        case BLUETOOTH_THREAD_DATA_TYPE_SENSOR_DATA_32HZ:
            if (!_p_thread->config->sensor_data_32hz_enabled) {
                return true;
            }
            break;
        case BLUETOOTH_THREAD_DATA_TYPE_PSP_INPUT_DATA_32HZ:
            if (!_p_thread->config->psp_input_data_32hz_enabled) {
                return true;
            }
            break;
        case BLUETOOTH_THREAD_DATA_TYPE_PSP_READ_INPUT_DATA_32HZ:
            if (!_p_thread->config->psp_read_input_data_32hz_enabled) {
                return true;
            }
            break;
        default:
            LOG_ERR("Unknown or unsupported data type %d", type);
            return false;
    }

    // Check if we are connected to a device
    if (_p_thread->current_conn == NULL) {
        return true;
    }

    // Allocate memory to copy the data into our heap
    bluetooth_thread_data_t *p_data_item = k_heap_alloc(&_p_thread->data_heap, sizeof(bluetooth_thread_data_t), K_MSEC(20));
    if (!p_data_item) {
        LOG_ERR("Failed to allocate memory for data copy");
        return false;
    }

    // Allocate memory for the data
    p_data_item->data = k_heap_alloc(&_p_thread->data_heap, length, K_MSEC(20));
    if (!p_data_item->data) {
        k_heap_free(&_p_thread->data_heap, p_data_item);
        LOG_ERR("Failed to allocate memory for data");
        return false;
    }

    // Assign the data type and length
    p_data_item->type = type;

    // Copy the data into our heap
    memcpy(p_data_item->data, p_data, length);

    // Put the data in the FIFO and increment counter
    switch (type) {
        case BLUETOOTH_THREAD_DATA_TYPE_VITALS_1HZ:
            k_fifo_put(&_p_thread->data_fifo_1hz, p_data_item);
            break;
        case BLUETOOTH_THREAD_DATA_TYPE_SENSOR_DATA_25HZ:
            k_fifo_put(&_p_thread->data_fifo_25hz, p_data_item);
            break;
        case BLUETOOTH_THREAD_DATA_TYPE_SENSOR_DATA_32HZ:
            k_fifo_put(&_p_thread->data_fifo_32hz, p_data_item);
            break;
        case BLUETOOTH_THREAD_DATA_TYPE_PSP_INPUT_DATA_32HZ:
            k_fifo_put(&_p_thread->data_fifo_psp_32hz, p_data_item);
            break;
        case BLUETOOTH_THREAD_DATA_TYPE_PSP_READ_INPUT_DATA_32HZ:
            k_fifo_put(&_p_thread->data_fifo_psp_read_32hz, p_data_item);
            break;
        default:
            LOG_ERR("Unknown or unsupported data type %d", type);
            return false;
    }

    return true;
}

/*----------------------------------------------------------------------------------------
 *                                                                                  Events
 *--------------------------------------------------------------------------------------*/
static void bluetooth_thread_init_events(bluetooth_thread_t *p_thread) {
    // Connection events
    k_poll_event_init(&p_thread->events[BLUETOOTH_THREAD_EVENT_CONNECTED],
                      K_POLL_TYPE_SEM_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &p_thread->connected_sem);

    k_poll_event_init(&p_thread->events[BLUETOOTH_THREAD_EVENT_DISCONNECTED],
                      K_POLL_TYPE_SEM_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &p_thread->disconnected_sem);

    // Timer events
    k_poll_event_init(&p_thread->events[BLUETOOTH_THREAD_EVENT_TIMER_1HZ],
                      K_POLL_TYPE_SEM_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &p_thread->timer_sem_1hz);

    k_poll_event_init(&p_thread->events[BLUETOOTH_THREAD_EVENT_TIMER_25HZ],
                      K_POLL_TYPE_SEM_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &p_thread->timer_sem_25hz);

    k_poll_event_init(&p_thread->events[BLUETOOTH_THREAD_EVENT_TIMER_32HZ],
                      K_POLL_TYPE_SEM_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &p_thread->timer_sem_32hz);
}

static bool process_event_connected(bluetooth_thread_t *p_thread) {
    k_sem_take(&p_thread->connected_sem, K_NO_WAIT);

    char addr[BT_ADDR_LE_STR_LEN];
    bt_addr_le_to_str(bt_conn_get_dst(p_thread->current_conn), addr, sizeof(addr));
    LOG_INF("Connected to %s", addr);

    // Get connection parameters
    struct bt_conn_info info;
    if (bt_conn_get_info(p_thread->current_conn, &info) == 0) {
        LOG_INF("Connection parameters: interval %.2fms latency %d timeout %dms",
                (double)info.le.interval * 1.25,
                info.le.latency,
                info.le.timeout * 10);
    }

    // Start timers with correct periods
    k_timer_start(&_p_thread->timer_1hz, K_MSEC(1000), K_MSEC(1000));  // 1Hz = 1000ms period
    k_timer_start(&_p_thread->timer_25hz, K_MSEC(40), K_MSEC(40));     // 25Hz = 40ms period
    k_timer_start(&_p_thread->timer_32hz, K_MSEC(31), K_MSEC(31));     // 32Hz = ~31.25ms period

    return true;
}

static bool process_event_disconnected(bluetooth_thread_t *p_thread) {
    // For now just sytem reset
    LOG_WRN("Disconnected from device, rebooting in 2 seconds");
    k_sleep(K_SECONDS(2));
    LOG_INF("ok byeee :(\n\n\n");
    LOG_PANIC();
    sys_reboot(0);

    k_sem_take(&p_thread->disconnected_sem, K_NO_WAIT);

    // Only try to get address if connection is still valid
    if (p_thread->current_conn) {
        char addr[BT_ADDR_LE_STR_LEN];
        bt_addr_le_to_str(bt_conn_get_dst(p_thread->current_conn), addr, sizeof(addr));
        LOG_INF("Disconnected from %s", addr);

        bt_conn_unref(p_thread->current_conn);
        p_thread->current_conn = NULL;
    } else {
        LOG_INF("Disconnected from device");
    }

    // Disable notifications
    p_thread->notify_1hz_vitals_enabled = false;
    p_thread->notify_25hz_ppg_intensity_enabled = false;
    p_thread->notify_32hz_ppg_intensity_enabled = false;
    p_thread->notify_25hz_accel_enabled = false;
    p_thread->notify_32hz_accel_enabled = false;
    p_thread->notify_32hz_psp_ppg_intensity_enabled = false;
    p_thread->notify_32hz_psp_accel_enabled = false;
    p_thread->notify_32hz_psp_read_ppg_intensity_enabled = false;  // Add missing notification flags
    p_thread->notify_32hz_psp_read_accel_enabled = false;

    // Stop timers
    k_timer_stop(&p_thread->timer_32hz);
    k_timer_stop(&p_thread->timer_25hz);
    k_timer_stop(&p_thread->timer_1hz);

    // Reset FIFOs - properly free any remaining data
    bluetooth_thread_data_t *p_item;
    while ((p_item = k_fifo_get(&p_thread->data_fifo_1hz, K_NO_WAIT))) {
        k_heap_free(&p_thread->data_heap, p_item->data);
        k_heap_free(&p_thread->data_heap, p_item);
    }
    while ((p_item = k_fifo_get(&p_thread->data_fifo_25hz, K_NO_WAIT))) {
        k_heap_free(&p_thread->data_heap, p_item->data);
        k_heap_free(&p_thread->data_heap, p_item);
    }
    while ((p_item = k_fifo_get(&p_thread->data_fifo_32hz, K_NO_WAIT))) {
        k_heap_free(&p_thread->data_heap, p_item->data);
        k_heap_free(&p_thread->data_heap, p_item);
    }
    while ((p_item = k_fifo_get(&p_thread->data_fifo_psp_32hz, K_NO_WAIT))) {
        k_heap_free(&p_thread->data_heap, p_item->data);
        k_heap_free(&p_thread->data_heap, p_item);
    }
    while ((p_item = k_fifo_get(&p_thread->data_fifo_psp_read_32hz, K_NO_WAIT))) {
        k_heap_free(&p_thread->data_heap, p_item->data);
        k_heap_free(&p_thread->data_heap, p_item);
    }

    // Reset Heap
    k_heap_init(&p_thread->data_heap, &p_thread->data_heap_mem, sizeof(p_thread->data_heap_mem));

    // Add a small delay before starting advertising
    k_sleep(K_MSEC(100));

    // Stop any existing advertising first
    bt_le_adv_stop();

    // Start advertising again with error retry
    int retry_count = 0;
    int err;
    do {
        err = bt_le_adv_start(BT_LE_ADV_CONN, ad, ARRAY_SIZE(ad), sd, ARRAY_SIZE(sd));
        if (err) {
            LOG_WRN("Advertising failed to start (err %d), retry %d", err, retry_count + 1);
            k_sleep(K_MSEC(100));  // Wait before retrying
        }
        retry_count++;
    } while (err && retry_count < 3);  // Try up to 3 times

    if (err) {
        LOG_ERR("Advertising failed to start after %d retries (err %d)", retry_count, err);
        return false;
    }

    LOG_INF("Advertising started after disconnection");
    return true;
}

static bool process_event_timer_1hz(bluetooth_thread_t *p_thread) {
    static int64_t last_time_ticks = 0;
    static uint32_t samples_this_second = 0;
    static uint32_t last_second = 0;
    int64_t current_time_ticks = k_uptime_ticks();

    k_sem_take(&p_thread->timer_sem_1hz, K_NO_WAIT);

    // Get data from FIFO, return true if no data (not an error)
    bluetooth_thread_data_t *p_item = k_fifo_get(&p_thread->data_fifo_1hz, K_NO_WAIT);

    if (!p_item) {
        return true;
    }

    // Only process if we have a connection
    if (!p_thread->current_conn) {
        k_heap_free(&p_thread->data_heap, p_item->data);
        k_heap_free(&p_thread->data_heap, p_item);
        return true;
    }

    int err = 0;
    vitals_data_t *vitals_data = (vitals_data_t *)p_item->data;

    // Process based on data type
    if (p_item->type == BLUETOOTH_THREAD_DATA_TYPE_VITALS_1HZ) {
        static uint32_t index = 0;
        index++;

        // Send vitals data if enabled
        if (p_thread->notify_1hz_vitals_enabled) {
            // Create a packed structure without k_reserved
            struct __attribute__((packed)) {
                int16_t heart_rate;
                int8_t heart_rate_quality;
                int16_t heart_rate_index;
                int16_t spo2;
                int8_t spo2_quality;
                int16_t spo2_index;
                float temperature_f;
            } packed_data = {
                .heart_rate = vitals_data->heart_rate,
                .heart_rate_quality = vitals_data->heart_rate_quality,
                .heart_rate_index = vitals_data->heart_rate_index,
                .spo2 = vitals_data->spo2,
                .spo2_quality = vitals_data->spo2_quality,
                .spo2_index = vitals_data->spo2_index,
                .temperature_f = vitals_data->temperature_f};

            err = bt_gatt_notify(p_thread->current_conn,
                                 &sensor_svc.attrs[BLUETOOTH_ATTRIBUTE_VITALS_1HZ],
                                 &packed_data,
                                 sizeof(packed_data));  // Should be 12 bytes

            if (err) {
                LOG_ERR("Failed to send vitals data: %d", err);
                goto cleanup;
            }
        }
    }
cleanup:
    // Free allocated memory
    k_heap_free(&p_thread->data_heap, p_item->data);
    k_heap_free(&p_thread->data_heap, p_item);

    // Calculate interval since last event
    int64_t interval_us = 0;
    if (last_time_ticks != 0) {
        interval_us = k_ticks_to_us_floor32(current_time_ticks - last_time_ticks);
    } else {
        // Skip the warning on first event since there's no previous timestamp
        last_time_ticks = current_time_ticks;
        return (err == 0);
    }

    // Track samples per second
    uint32_t current_second = k_uptime_get_32() / 1000;
    static bool first_sample = true;
    if (current_second != last_second && !first_sample) {
        if (samples_this_second < 1) {  // Changed from 24 to 1 since we expect 1Hz
            LOG_ERR("Vitals 1Hz samples in last second: %d (expected: 1)", samples_this_second);
        } else if (samples_this_second > 1) {
            LOG_WRN("Vitals 1Hz samples in last second: %d (expected: 1)", samples_this_second);
        } else {
            // Only log as debug when we get exactly 1 sample as expected
            LOG_DBG("Vitals 1Hz samples in last second: %d (expected: 1)", samples_this_second);
        }
        samples_this_second = 0;
        last_second = current_second;
    }

    last_time_ticks = current_time_ticks;
    return (err == 0);
}

static bool process_event_timer_25hz(bluetooth_thread_t *p_thread) {
    static int64_t last_time_ticks = 0;
    static bool first_sample = true;

    k_sem_take(&p_thread->timer_sem_25hz, K_NO_WAIT);

    // Get data from FIFO, return true if no data (not an error)
    bluetooth_thread_data_t *p_item = k_fifo_get(&p_thread->data_fifo_25hz, K_NO_WAIT);

    // Take current time for all cases
    int64_t current_time_ticks = k_uptime_ticks();

    if (!p_item) {
        // Still update last_time_ticks to maintain proper interval tracking
        if (last_time_ticks != 0) {
            int64_t interval_us = k_ticks_to_us_floor32(current_time_ticks - last_time_ticks);
            LOG_DBG("No raw sensor data available, interval since last check: %.3fms",
                    (double)interval_us / 1000.0);
        }
        last_time_ticks = current_time_ticks;
        return true;
    }

    // Only process if we have a connection
    if (!p_thread->current_conn) {
        k_heap_free(&p_thread->data_heap, p_item->data);
        k_heap_free(&p_thread->data_heap, p_item);
        return true;
    }

    int64_t start_process_ticks = k_uptime_ticks();

    int err = 0;
    sensor_data_t *sensor_data = (sensor_data_t *)p_item->data;

    // Process based on data type
    if (p_item->type == BLUETOOTH_THREAD_DATA_TYPE_SENSOR_DATA_25HZ) {
        static uint32_t index = 0;
        index++;

        // Send accelerometer data if enabled
        if (p_thread->notify_25hz_accel_enabled) {
            err = bt_gatt_notify(p_thread->current_conn,
                                 &sensor_svc.attrs[BLUETOOTH_ATTRIBUTE_ACCEL_25HZ],
                                 &sensor_data->accelerometer,
                                 sizeof(accelerometer_data_t));

            if (err) {
                LOG_ERR("Failed to send accelerometer data: %d", err);
                goto cleanup;
            }
        }

        // Send PPG intensity data if enabled
        if (p_thread->notify_25hz_ppg_intensity_enabled) {
            err = bt_gatt_notify(p_thread->current_conn,
                                 &sensor_svc.attrs[BLUETOOTH_ATTRIBUTE_PPG_INTENSITY_25HZ],
                                 &sensor_data->ppg_intensity,
                                 sizeof(ppg_intensity_data_t));

            if (err) {
                LOG_ERR("Failed to send PPG intensity data: %d", err);
                goto cleanup;
            }
        }
    }
cleanup:
    // Free allocated memory
    k_heap_free(&p_thread->data_heap, p_item->data);
    k_heap_free(&p_thread->data_heap, p_item);

    // Calculate processing time (fixed to use start_process_ticks)
    int64_t duration_us = k_ticks_to_us_floor32(k_uptime_ticks() - start_process_ticks);

    static uint32_t index = 0;
    index++;

    // Calculate interval since last successful data processing
    int64_t interval_us = 0;
    if (last_time_ticks != 0) {
        interval_us = k_ticks_to_us_floor32(current_time_ticks - last_time_ticks);

        // Only warn if interval is significantly off from expected 40ms
        // and we're not in the startup phase
        if (!first_sample && (interval_us > (40000 + 5000))) {
            LOG_WRN("Raw sensor 25Hz event %d: gap=%.3fms (should be 5ms, off by %.3fms) process=%.3fms",
                    index,
                    (double)interval_us / 1000.0,
                    (double)(interval_us - 40000) / 1000.0,
                    (double)duration_us / 1000.0);
        }
    }

    // Update timing tracking
    last_time_ticks = current_time_ticks;
    if (first_sample) {
        first_sample = false;
    }

    return (err == 0);
}

static bool _send_raw_sensor_data_32hz(bluetooth_thread_t *p_thread) {
    static int64_t last_time_ticks = 0;
    static bool first_sample = true;

    // Get data from FIFO first
    bluetooth_thread_data_t *p_item = k_fifo_get(&p_thread->data_fifo_32hz, K_NO_WAIT);

    // Take current time for all cases
    int64_t current_time_ticks = k_uptime_ticks();

    // If no data, just update the timestamp and return
    if (!p_item) {
        // Still update last_time_ticks to maintain proper interval tracking
        if (last_time_ticks != 0) {
            int64_t interval_us = k_ticks_to_us_floor32(current_time_ticks - last_time_ticks);
            LOG_DBG("No raw sensor data available, interval since last check: %.3fms",
                    (double)interval_us / 1000.0);
        }
        last_time_ticks = current_time_ticks;
        return true;
    }

    int64_t start_process_ticks = k_uptime_ticks();

    int err = 0;
    sensor_data_t *sensor_data = (sensor_data_t *)p_item->data;

    // Process based on data type
    if (p_item->type == BLUETOOTH_THREAD_DATA_TYPE_SENSOR_DATA_32HZ) {
        static uint32_t index = 0;
        index++;

        // Send accelerometer data if enabled
        if (p_thread->notify_32hz_accel_enabled) {
            err = bt_gatt_notify(p_thread->current_conn,
                                 &sensor_svc.attrs[BLUETOOTH_ATTRIBUTE_ACCEL_32HZ],
                                 &sensor_data->accelerometer,
                                 sizeof(accelerometer_data_t));

            if (err) {
                LOG_ERR("Failed to send accelerometer data: %d", err);
                goto cleanup;
            }
        }

        // Send PPG intensity data if enabled
        if (p_thread->notify_32hz_ppg_intensity_enabled) {
            err = bt_gatt_notify(p_thread->current_conn,
                                 &sensor_svc.attrs[BLUETOOTH_ATTRIBUTE_PPG_INTENSITY_32HZ],
                                 &sensor_data->ppg_intensity,
                                 sizeof(ppg_intensity_data_t));

            if (err) {
                LOG_ERR("Failed to send PPG intensity data: %d", err);
                goto cleanup;
            }
        }
    }
cleanup:
    // Free allocated memory
    k_heap_free(&p_thread->data_heap, p_item->data);
    k_heap_free(&p_thread->data_heap, p_item);

    // Calculate processing time
    int64_t duration_us = k_ticks_to_us_floor32(k_uptime_ticks() - start_process_ticks);

    static uint32_t index = 0;
    index++;

    // Calculate interval since last successful data processing
    int64_t interval_us = 0;
    if (last_time_ticks != 0) {
        interval_us = k_ticks_to_us_floor32(current_time_ticks - last_time_ticks);

        // Only warn if interval is significantly off from expected 31.25ms
        // and we're not in the startup phase
        if (!first_sample && (interval_us > (31250 + 5000))) {
            LOG_WRN("Raw sensor 32Hz event %d: gap=%.3fms (should be 31.25ms, off by %.3fms) process=%.3fms",
                    index,
                    (double)interval_us / 1000.0,
                    (double)(interval_us - 31250) / 1000.0,
                    (double)duration_us / 1000.0);
        }
    }

    // Update timing tracking
    last_time_ticks = current_time_ticks;
    if (first_sample) {
        first_sample = false;
    }

    return (err == 0);
}

static bool _send_psp_data_32hz(bluetooth_thread_t *p_thread) {
    static int64_t last_time_ticks = 0;
    static uint32_t samples_this_second = 0;
    static uint32_t last_second = 0;
    int64_t current_time_ticks = k_uptime_ticks();
    int64_t start_process_ticks = k_uptime_ticks();

    // Get data from FIFO, return true if no data (not an error)
    bluetooth_thread_data_t *p_item = k_fifo_get(&p_thread->data_fifo_psp_32hz, K_NO_WAIT);

    if (!p_item) {
        return true;
    }

    // Only process if we have a connection
    if (!p_thread->current_conn) {
        k_heap_free(&p_thread->data_heap, p_item->data);
        k_heap_free(&p_thread->data_heap, p_item);
        return true;
    }

    int err = 0;
    psp_input_data_t *psp_data = (psp_input_data_t *)p_item->data;

    LOG_INF("PSP data size: %zu", sizeof(psp_input_data_t));

    // Process based on data type
    if (p_item->type == BLUETOOTH_THREAD_DATA_TYPE_PSP_INPUT_DATA_32HZ) {
        static uint32_t index = 0;
        index++;

        // Send accelerometer data if enabled
        if (p_thread->notify_32hz_psp_accel_enabled) {
            err = bt_gatt_notify(p_thread->current_conn,
                                 &sensor_svc.attrs[BLUETOOTH_ATTRIBUTE_PSP_ACCEL_32HZ],
                                 &psp_data->accelerometer,
                                 sizeof(psp_input_accelerometer_data_t));

            if (err) {
                LOG_ERR("Failed to send PSP accelerometer data: %d", err);
                goto cleanup;
            }
        }

        // Send PPG intensity data if enabled
        if (p_thread->notify_32hz_psp_ppg_intensity_enabled) {
            err = bt_gatt_notify(p_thread->current_conn,
                                 &sensor_svc.attrs[BLUETOOTH_ATTRIBUTE_PSP_PPG_INTENSITY_32HZ],
                                 &psp_data->ppg_intensity,
                                 sizeof(psp_input_ppg_intensity_data_t));

            if (err) {
                LOG_ERR("Failed to send PSP PPG intensity data: %d", err);
                goto cleanup;
            }
        }
    }
cleanup:
    // Free allocated memory
    k_heap_free(&p_thread->data_heap, p_item->data);
    k_heap_free(&p_thread->data_heap, p_item);

    // Calculate processing time
    int64_t duration_us = k_ticks_to_us_floor32(k_uptime_ticks() - start_process_ticks);

    // Calculate interval since last event
    int64_t interval_us = 0;
    if (last_time_ticks != 0) {
        interval_us = k_ticks_to_us_floor32(current_time_ticks - last_time_ticks);
    }

    // Track samples per second
    uint32_t current_second = k_uptime_get_32() / 1000;
    static bool first_sample = true;
    if (current_second != last_second && !first_sample) {
        if (samples_this_second < 31) {
            LOG_ERR("PSP 32Hz samples in last second: %d (expected: 32)", samples_this_second);
        } else {
            LOG_DBG("PSP 32Hz samples in last second: %d (expected: 32)", samples_this_second);
        }
        samples_this_second = 0;
        last_second = current_second;
    }
    if (first_sample) {
        first_sample = false;
        last_second = current_second;
    }
    samples_this_second++;

    static uint32_t index = 0;
    index++;

    if (interval_us > (40000 + 10000)) {  // Log any big gaps (over 40ms + 10ms)
        LOG_WRN("PSP 32Hz event %d: gap=%.3fms (should be 31.25ms) process=%.3fms",
                index,
                (double)interval_us / 1000.0,
                (double)duration_us / 1000.0);
    }

    last_time_ticks = current_time_ticks;
    return (err == 0);
}

static bool _send_psp_read_data_32hz(bluetooth_thread_t *p_thread) {
    static int64_t last_time_ticks = 0;
    static bool first_sample = true;

    // Get data from FIFO first
    bluetooth_thread_data_t *p_item = k_fifo_get(&p_thread->data_fifo_psp_read_32hz, K_NO_WAIT);

    // Take current time for all cases
    int64_t current_time_ticks = k_uptime_ticks();

    // If no data, just update the timestamp and return
    if (!p_item) {
        // Still update last_time_ticks to maintain proper interval tracking
        if (last_time_ticks != 0) {
            int64_t interval_us = k_ticks_to_us_floor32(current_time_ticks - last_time_ticks);
            LOG_DBG("No PSP Read data available, interval since last check: %.3fms",
                    (double)interval_us / 1000.0);
        }
        last_time_ticks = current_time_ticks;
        return true;
    }

    int64_t start_process_ticks = k_uptime_ticks();

    // Only process if we have a connection
    if (!p_thread->current_conn) {
        k_heap_free(&p_thread->data_heap, p_item->data);
        k_heap_free(&p_thread->data_heap, p_item);
        return true;
    }

    int err = 0;
    psp_input_data_t *psp_data = (psp_input_data_t *)p_item->data;

    // Process based on data type
    if (p_item->type == BLUETOOTH_THREAD_DATA_TYPE_PSP_READ_INPUT_DATA_32HZ) {
        static uint32_t index = 0;
        index++;

        // Send accelerometer data if enabled
        if (p_thread->notify_32hz_psp_read_accel_enabled) {
            err = bt_gatt_notify(p_thread->current_conn,
                                 &sensor_svc.attrs[BLUETOOTH_ATTRIBUTE_PSP_READ_ACCEL_32HZ],
                                 &psp_data->accelerometer,
                                 sizeof(psp_input_accelerometer_data_t));

            if (err) {
                LOG_ERR("Failed to send PSP accelerometer data: %d", err);
                goto cleanup;
            }
        }

        // Send PPG intensity data if enabled
        if (p_thread->notify_32hz_psp_read_ppg_intensity_enabled) {
            err = bt_gatt_notify(p_thread->current_conn,
                                 &sensor_svc.attrs[BLUETOOTH_ATTRIBUTE_PSP_READ_PPG_INTENSITY_32HZ],
                                 &psp_data->ppg_intensity,
                                 sizeof(psp_input_ppg_intensity_data_t));

            if (err) {
                LOG_ERR("Failed to send PSP PPG intensity data: %d", err);
                goto cleanup;
            }
        }
    }

cleanup:
    // Free allocated memory
    k_heap_free(&p_thread->data_heap, p_item->data);
    k_heap_free(&p_thread->data_heap, p_item);

    // Calculate processing time
    int64_t duration_us = k_ticks_to_us_floor32(k_uptime_ticks() - start_process_ticks);

    static uint32_t index = 0;
    index++;

    // Calculate interval since last successful data processing
    int64_t interval_us = 0;
    if (last_time_ticks != 0) {
        interval_us = k_ticks_to_us_floor32(current_time_ticks - last_time_ticks);

        // Only warn if interval is significantly off from expected 31.25ms
        // and we're not in the startup phase
        if (!first_sample && (interval_us > (31250 + 5000))) {
            LOG_WRN("PSP Read 32Hz event %d: gap=%.3fms (should be 31.25ms, off by %.3fms) process=%.3fms",
                    index,
                    (double)interval_us / 1000.0,
                    (double)(interval_us - 31250) / 1000.0,
                    (double)duration_us / 1000.0);
        }
    }

    // Update timing tracking
    last_time_ticks = current_time_ticks;
    if (first_sample) {
        first_sample = false;
    }

    return (err == 0);
}

static bool process_event_timer_32hz(bluetooth_thread_t *p_thread) {
    static int64_t last_timer_ticks = 0;
    int64_t current_ticks = k_uptime_ticks();

    // Log the actual timer interval
    if (last_timer_ticks != 0) {
        int64_t timer_interval_us = k_ticks_to_us_floor32(current_ticks - last_timer_ticks);
        LOG_DBG("32Hz Timer fired: interval=%.3fms", (double)timer_interval_us / 1000.0);
    }
    last_timer_ticks = current_ticks;

    k_sem_take(&p_thread->timer_sem_32hz, K_NO_WAIT);

    int64_t start_time = k_uptime_ticks();

    bool raw_result = _send_raw_sensor_data_32hz(p_thread);
    int64_t after_raw = k_uptime_ticks();

    bool psp_result = _send_psp_data_32hz(p_thread);
    int64_t after_psp = k_uptime_ticks();

    bool psp_read_result = _send_psp_read_data_32hz(p_thread);
    int64_t after_psp_read = k_uptime_ticks();

    // Log detailed timing for each operation
    LOG_DBG("32Hz Processing: raw=%.3fms psp=%.3fms psp_read=%.3fms total=%.3fms",
            (double)k_ticks_to_us_floor32(after_raw - start_time) / 1000.0,
            (double)k_ticks_to_us_floor32(after_psp - after_raw) / 1000.0,
            (double)k_ticks_to_us_floor32(after_psp_read - after_psp) / 1000.0,
            (double)k_ticks_to_us_floor32(after_psp_read - start_time) / 1000.0);

    return (raw_result && psp_result && psp_read_result);
}

/*----------------------------------------------------------------------------------------
 *                                                                            Thread Entry
 *--------------------------------------------------------------------------------------*/
static void bluetooth_thread_entry(void *p_arg0, void *p_arg1, void *p_arg2) {
    LOG_INF("Bluetooth thread started");

    bluetooth_thread_t *p_thread = (bluetooth_thread_t *)p_arg0;

    // Initialize thread events
    bluetooth_thread_init_events(p_thread);

    while (true) {
        // Wait for any of the events to trigger
        int rc = k_poll(p_thread->events, ARRAY_SIZE(p_thread->events), K_FOREVER);

        if (rc != 0) {
            LOG_ERR("%s", "Unknown timeout in bluetooth thread");
        } else {
            // Connection events
            if (p_thread->events[BLUETOOTH_THREAD_EVENT_CONNECTED].state == K_POLL_STATE_SEM_AVAILABLE) {
                if (!process_event_connected(p_thread)) {
                    LOG_ERR("Failed to process connected event");
                }

                p_thread->events[BLUETOOTH_THREAD_EVENT_CONNECTED].state = K_POLL_STATE_NOT_READY;  // Clear the event
            }

            if (p_thread->events[BLUETOOTH_THREAD_EVENT_DISCONNECTED].state == K_POLL_STATE_SEM_AVAILABLE) {
                if (!process_event_disconnected(p_thread)) {
                    LOG_ERR("Failed to process disconnected event");
                }

                p_thread->events[BLUETOOTH_THREAD_EVENT_DISCONNECTED].state = K_POLL_STATE_NOT_READY;  // Clear the event
            }

            // Timer events
            if (p_thread->events[BLUETOOTH_THREAD_EVENT_TIMER_32HZ].state == K_POLL_STATE_SEM_AVAILABLE) {
                // Get the exact time when we start processing
                int64_t start_time_ticks = k_uptime_ticks();

                // Stop the timer while we process
                k_timer_stop(&p_thread->timer_32hz);

                if (!process_event_timer_32hz(p_thread)) {
                    LOG_ERR("Failed to process timer 32hz event");
                }

                p_thread->events[BLUETOOTH_THREAD_EVENT_TIMER_32HZ].state = K_POLL_STATE_NOT_READY;  // Clear the event

                // Calculate how long we spent processing
                int64_t process_time_us = k_ticks_to_us_floor32(k_uptime_ticks() - start_time_ticks);

                // Calculate next interval: target period (31.25ms) minus processing time
                uint32_t next_interval_ms = 31;  // 1000/32 ≈ 31.25ms target period

                if (process_time_us < 31250) {  // Only adjust if we haven't exceeded the period
                    next_interval_ms = (31250 - process_time_us) / 1000;
                } else {
                    // Log if we're taking too long to process
                    LOG_ERR("Processing time %lld ms exceeded period (32hz)", process_time_us / 1000);
                    next_interval_ms = 1;  // Minimum delay to prevent overwhelming the system
                }

                // Start timer as one-shot with calculated interval
                k_timer_start(&p_thread->timer_32hz, K_MSEC(next_interval_ms), K_NO_WAIT);
            }

            if (p_thread->events[BLUETOOTH_THREAD_EVENT_TIMER_25HZ].state == K_POLL_STATE_SEM_AVAILABLE) {
                // Get the exact time when we start processing
                int64_t start_time_ticks = k_uptime_ticks();

                // Stop the timer while we process
                k_timer_stop(&p_thread->timer_25hz);

                if (!process_event_timer_25hz(p_thread)) {
                    LOG_ERR("Failed to process timer 25hz event");
                }

                p_thread->events[BLUETOOTH_THREAD_EVENT_TIMER_25HZ].state = K_POLL_STATE_NOT_READY;  // Clear the event

                // Calculate how long we spent processing
                int64_t process_time_us = k_ticks_to_us_floor32(k_uptime_ticks() - start_time_ticks);

                // Calculate next interval: target period (40ms) minus processing time
                uint32_t next_interval_ms = 40;  // 1000/25 = 40ms target period

                if (process_time_us < 40000) {  // Only adjust if we haven't exceeded the period
                    next_interval_ms = (40000 - process_time_us) / 1000;
                } else {
                    // Log if we're taking too long to process
                    LOG_ERR("Processing time %lld ms exceeded period (25hz)", process_time_us / 1000);
                    next_interval_ms = 1;  // Minimum delay to prevent overwhelming the system
                }

                // Start timer with adjusted interval to maintain 25Hz average
                k_timer_start(&p_thread->timer_25hz, K_MSEC(next_interval_ms), K_NO_WAIT);
            }

            if (p_thread->events[BLUETOOTH_THREAD_EVENT_TIMER_1HZ].state == K_POLL_STATE_SEM_AVAILABLE) {
                // Get the exact time when we start processing
                int64_t start_time_ticks = k_uptime_ticks();

                // Stop the timer while we process
                k_timer_stop(&p_thread->timer_1hz);

                if (!process_event_timer_1hz(p_thread)) {
                    LOG_ERR("Failed to process timer 1hz event");
                }

                p_thread->events[BLUETOOTH_THREAD_EVENT_TIMER_1HZ].state = K_POLL_STATE_NOT_READY;  // Clear the event

                // Calculate how long we spent processing
                int64_t process_time_us = k_ticks_to_us_floor32(k_uptime_ticks() - start_time_ticks);

                // Calculate next interval: target period (1000000us = 1s) minus processing time
                uint32_t next_interval_ms = 1000;  // 1000ms target period

                if (process_time_us < 1000000) {  // Only adjust if we haven't exceeded the period (1s = 1000000us)
                    next_interval_ms = (1000000 - process_time_us) / 1000;
                } else {
                    // Log if we're taking too long to process
                    LOG_ERR("Processing time %lld ms exceeded period (1hz)", process_time_us / 1000);
                    next_interval_ms = 1;  // Minimum delay to prevent overwhelming the system
                }

                // Start timer as one-shot with calculated interval
                k_timer_start(&p_thread->timer_1hz, K_MSEC(next_interval_ms), K_NO_WAIT);
            }
        }
    }
}
