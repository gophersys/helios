/*
 * IWSCK A1 — Permanent BLE + NFC beacon
 *
 * Boots headless, immediately starts:
 *   - BLE connectable advertising (GATT server with status notify)
 *   - NFC T2T tag emulation (NDEF text record)
 *
 * Runs indefinitely while power is applied. No shell, no UART.
 */

#include <zephyr/kernel.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/bluetooth/conn.h>
#include <nfc_t2t_lib.h>
#include <nfc/ndef/msg.h>
#include <nfc/ndef/text_rec.h>
#include <string.h>

/* ---------------- BLE ---------------- */

#define SVC_UUID  BT_UUID_128_ENCODE(0x12345678,0x1234,0x5678,0x1234,0x56789abcdef0)
#define CHAR_UUID BT_UUID_128_ENCODE(0x12345678,0x1234,0x5678,0x1234,0x56789abcdef1)

static struct bt_uuid_128 svc_uuid  = BT_UUID_INIT_128(SVC_UUID);
static struct bt_uuid_128 char_uuid = BT_UUID_INIT_128(CHAR_UUID);

static bool notifying;
static struct bt_conn *conn_ref;

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
};

static const struct device *const temp_dev = DEVICE_DT_GET(DT_NODELABEL(temp));

static void ccc_changed(const struct bt_gatt_attr *attr, uint16_t value)
{
	notifying = (value == BT_GATT_CCC_NOTIFY);
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
	if (!notifying || !conn_ref) {
		return;
	}

	struct status_pkt pkt = {0};
	if (device_is_ready(temp_dev)) {
		struct sensor_value v;
		sensor_sample_fetch(temp_dev);
		sensor_channel_get(temp_dev, SENSOR_CHAN_DIE_TEMP, &v);
		pkt.die_temp_c10 = (int16_t)(v.val1 * 10 + v.val2 / 100000);
	}
	pkt.uptime_s = (uint32_t)(k_uptime_get() / 1000);

	bt_gatt_notify(conn_ref, &iwsck_svc.attrs[1], &pkt, sizeof(pkt));
	k_work_reschedule(&notify_work, K_SECONDS(2));
}

static void on_connected(struct bt_conn *conn, uint8_t err)
{
	if (err) {
		return;
	}
	conn_ref = bt_conn_ref(conn);
}

static void on_disconnected(struct bt_conn *conn, uint8_t reason)
{
	ARG_UNUSED(reason);
	notifying = false;
	if (conn_ref) {
		bt_conn_unref(conn_ref);
		conn_ref = NULL;
	}
	/* Re-advertise after disconnect */
	bt_le_adv_start(BT_LE_ADV_CONN_FAST_1, ad, ARRAY_SIZE(ad),
			sd, ARRAY_SIZE(sd));
}

BT_CONN_CB_DEFINE(conn_cbs) = {
	.connected    = on_connected,
	.disconnected = on_disconnected,
};

static int ble_init(void)
{
	int err = bt_enable(NULL);
	if (err) {
		return err;
	}

	err = bt_le_adv_start(BT_LE_ADV_CONN_FAST_1, ad, ARRAY_SIZE(ad),
			      sd, ARRAY_SIZE(sd));
	return err;
}

/* ---------------- NFC ---------------- */

static uint8_t ndef_msg_buf[256];

static void nfc_callback(void *context, nfc_t2t_event_t event,
			 const uint8_t *data, size_t data_length)
{
	ARG_UNUSED(context);
	ARG_UNUSED(data);
	ARG_UNUSED(data_length);
	/* Nothing to do — tag just stays active */
}

static int nfc_init(void)
{
	int err = nfc_t2t_setup(nfc_callback, NULL);
	if (err) {
		return err;
	}

	static const char text[] = "IWSCK-A1";
	uint8_t lang_code[] = "en";
	uint32_t len = sizeof(ndef_msg_buf);

	NFC_NDEF_MSG_DEF(nfc_msg, 1);
	NFC_NDEF_TEXT_RECORD_DESC_DEF(text_rec, UTF_8, lang_code,
				      sizeof(lang_code) - 1,
				      (const uint8_t *)text, sizeof(text) - 1);

	err = nfc_ndef_msg_record_add(&NFC_NDEF_MSG(nfc_msg),
				      &NFC_NDEF_TEXT_RECORD_DESC(text_rec));
	if (err) {
		return err;
	}

	err = nfc_ndef_msg_encode(&NFC_NDEF_MSG(nfc_msg), ndef_msg_buf, &len);
	if (err) {
		return err;
	}

	err = nfc_t2t_payload_set(ndef_msg_buf, len);
	if (err) {
		return err;
	}

	return nfc_t2t_emulation_start();
}

/* ---------------- Main ---------------- */

int main(void)
{
	/* Start BLE advertising */
	ble_init();

	/* Start NFC tag emulation */
	nfc_init();

	/* Both peripherals run from ISR/radio context.
	 * Main thread sleeps forever — kernel idle handles low-power. */
	k_sleep(K_FOREVER);
	return 0;
}
