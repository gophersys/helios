/* tracker iteration 1 — prove the contract: every catalog-cited device
 * node resolves to a ready driver instance. FAIL-NOT-SKIP at runtime:
 * a device that is not ready is reported, never ignored. */
#include <zephyr/kernel.h>
#include <zephyr/device.h>

static const struct device *const imu = DEVICE_DT_GET(DT_NODELABEL(imu));
static const struct device *const charger = DEVICE_DT_GET(DT_NODELABEL(charger));

int main(void)
{
	printk("tracker fw skeleton — Route 2 (esp32c6 + bg95 + bmi270 + bq25180)\n");
	printk("imu (bmi270):      %s\n", device_is_ready(imu) ? "ready" : "NOT READY");
	printk("charger (bq25180): %s\n", device_is_ready(charger) ? "ready" : "NOT READY");
	/* modem node present in dts; software stack lands in iteration 2 */
	return 0;
}
