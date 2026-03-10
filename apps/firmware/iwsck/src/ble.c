/* BLE GATT server — connectable, notify die temp + fuel voltage every 2s */

#include <zephyr/kernel.h>
#include <zephyr/shell/shell.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/bluetooth/conn.h>
#include <string.h>

static const struct device *const temp_dev = DEVICE_DT_GET(DT_NODELABEL(temp));
static const struct device *const i2c_dev = DEVICE_DT_GET(DT_NODELABEL(i2c21));

static bool advertising;
static bool ready;
static bool notifying;
static struct bt_conn *conn_ref;

/* Custom service */
#define SVC_UUID  BT_UUID_128_ENCODE(0x12345678,0x1234,0x5678,0x1234,0x56789abcdef0)
#define CHAR_UUID BT_UUID_128_ENCODE(0x12345678,0x1234,0x5678,0x1234,0x56789abcdef1)

static struct bt_uuid_128 svc_uuid = BT_UUID_INIT_128(SVC_UUID);
static struct bt_uuid_128 char_uuid = BT_UUID_INIT_128(CHAR_UUID);

static const struct bt_data ad[] = {
	BT_DATA_BYTES(BT_DATA_FLAGS, BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR),
};
static const struct bt_data sd[] = {
	BT_DATA(BT_DATA_NAME_COMPLETE, CONFIG_BT_DEVICE_NAME,
		sizeof(CONFIG_BT_DEVICE_NAME) - 1),
};

struct __packed status_pkt {
	int16_t  die_temp_c10;
	uint32_t uptime_s;
	uint16_t voltage_mv;
};

static void ccc_changed(const struct bt_gatt_attr *attr, uint16_t value)
{
	notifying = (value == BT_GATT_CCC_NOTIFY);
	printk("BLE notify %s\n", notifying ? "on" : "off");
}

BT_GATT_SERVICE_DEFINE(iwsck_svc,
	BT_GATT_PRIMARY_SERVICE(&svc_uuid),
	BT_GATT_CHARACTERISTIC(&char_uuid.uuid, BT_GATT_CHRC_NOTIFY,
			       BT_GATT_PERM_NONE, NULL, NULL, NULL),
	BT_GATT_CCC(ccc_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),
);

static void notify_work_fn(struct k_work *w);
K_WORK_DELAYABLE_DEFINE(notify_work, notify_work_fn);

static void notify_work_fn(struct k_work *w)
{
	if (!notifying || !conn_ref) return;

	struct status_pkt pkt = {0};
	if (device_is_ready(temp_dev)) {
		struct sensor_value v;
		sensor_sample_fetch(temp_dev);
		sensor_channel_get(temp_dev, SENSOR_CHAN_DIE_TEMP, &v);
		pkt.die_temp_c10 = (int16_t)(v.val1 * 10 + v.val2 / 100000);
	}
	pkt.uptime_s = (uint32_t)(k_uptime_get() / 1000);

	uint16_t volt;
	if (i2c_burst_read(i2c_dev, 0x55, 0x08, (uint8_t *)&volt, 2) == 0)
		pkt.voltage_mv = volt;

	bt_gatt_notify(conn_ref, &iwsck_svc.attrs[1], &pkt, sizeof(pkt));
	k_work_reschedule(&notify_work, K_SECONDS(2));
}

static void on_connected(struct bt_conn *conn, uint8_t err)
{
	if (err) { printk("BLE connect err: %d\n", err); return; }
	conn_ref = bt_conn_ref(conn);
	printk("BLE connected\n");
}

static void on_disconnected(struct bt_conn *conn, uint8_t reason)
{
	printk("BLE disconnected (%u)\n", reason);
	notifying = false;
	if (conn_ref) { bt_conn_unref(conn_ref); conn_ref = NULL; }
	if (advertising)
		bt_le_adv_start(BT_LE_ADV_CONN_FAST_1, ad, ARRAY_SIZE(ad),
				sd, ARRAY_SIZE(sd));
}

BT_CONN_CB_DEFINE(conn_cbs) = {
	.connected = on_connected,
	.disconnected = on_disconnected,
};

static int cmd_start(const struct shell *sh, size_t argc, char **argv)
{
	if (!ready) {
		shell_print(sh, "Initializing BLE...");
		int err = bt_enable(NULL);
		if (err) { shell_error(sh, "bt_enable: %d", err); return err; }
		ready = true;
		shell_print(sh, "BLE ready");
	}
	if (advertising) { shell_warn(sh, "Already advertising"); return 0; }

	if (argc >= 2) bt_set_name(argv[1]);

	int err = bt_le_adv_start(BT_LE_ADV_CONN_FAST_1, ad, ARRAY_SIZE(ad),
				  sd, ARRAY_SIZE(sd));
	if (err) { shell_error(sh, "Adv start: %d", err); return err; }

	advertising = true;
	shell_print(sh, "BLE server started (%s)", bt_get_name());
	return 0;
}

static int cmd_stop(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);
	if (!advertising) { shell_warn(sh, "Not advertising"); return 0; }

	notifying = false;
	k_work_cancel_delayable(&notify_work);
	if (conn_ref) bt_conn_disconnect(conn_ref, BT_HCI_ERR_REMOTE_USER_TERM_CONN);

	int err = bt_le_adv_stop();
	if (err) { shell_error(sh, "Stop: %d", err); return err; }

	advertising = false;
	shell_print(sh, "BLE stopped");
	return 0;
}

SHELL_STATIC_SUBCMD_SET_CREATE(sub_ble,
	SHELL_CMD(start, NULL, "Start GATT server [name]", cmd_start),
	SHELL_CMD(stop, NULL, "Stop server", cmd_stop),
	SHELL_SUBCMD_SET_END
);
SHELL_CMD_REGISTER(ble, &sub_ble, "BLE GATT server", NULL);
