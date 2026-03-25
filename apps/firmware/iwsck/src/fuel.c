/* BQ35100 fuel gauge — I2C commands + interrupt + enable
 * A0: bit-bang I2C (i2c_bb), INT P0.00, EN P0.01
 * A1: hardware TWIM21 (i2c21), INT P0.02, EN P0.03
 */

#include <zephyr/kernel.h>
#include <zephyr/shell/shell.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>

/* I2C bus: hardware TWIM21 on A1, bit-bang on A0 */
#if DT_NODE_HAS_STATUS_OKAY(DT_NODELABEL(i2c21))
static const struct device *const i2c = DEVICE_DT_GET(DT_NODELABEL(i2c21));
#else
static const struct device *const i2c = DEVICE_DT_GET(DT_NODELABEL(i2c_bb));
#endif

/* Fuel gauge interrupt — P0.02, active-low */
static const struct gpio_dt_spec fuel_int =
	GPIO_DT_SPEC_GET(DT_NODELABEL(fuel_gauge_int), gpios);

/* Fuel gauge enable — P0.03, active-high */
static const struct gpio_dt_spec fuel_en =
	GPIO_DT_SPEC_GET(DT_NODELABEL(fuel_en), gpios);

static bool ge_enabled;

static int fuel_ge_init(void)
{
	if (!gpio_is_ready_dt(&fuel_en)) return -ENODEV;
	gpio_pin_configure_dt(&fuel_en, GPIO_OUTPUT_INACTIVE);
	return 0;
}
SYS_INIT(fuel_ge_init, APPLICATION, 89);

static void fuel_ge_on(void)
{
	if (!ge_enabled) {
		if (!gpio_is_ready_dt(&fuel_en)) {
			printk("[fuel] GE: gpio not ready!\n");
			return;
		}
		gpio_pin_set_dt(&fuel_en, 1);
		ge_enabled = true;
		k_msleep(1000); /* BQ35100 needs ~1s after GE rising edge for valid readings */
		printk("[fuel] GE enabled (P%d.%02d HIGH)\n",
		       fuel_en.port == DEVICE_DT_GET(DT_NODELABEL(gpio0)) ? 0 :
		       fuel_en.port == DEVICE_DT_GET(DT_NODELABEL(gpio1)) ? 1 : 2,
		       fuel_en.pin);
	}
}

#define ADDR 0x55

/* Registers */
#define REG_CONTROL 0x00
#define REG_ACAP    0x02
#define REG_TEMP    0x06
#define REG_VOLT    0x08
#define REG_BSTAT   0x0A
#define REG_BALERT  0x0B
#define REG_CURR    0x0C
#define REG_MEAS_Z  0x22
#define REG_SOH     0x2E
#define REG_DCAP    0x3C

/* Control subcommands */
#define CNTL_DEVICE_TYPE  0x0001
#define CNTL_FW_VERSION   0x0002
#define CNTL_HW_VERSION   0x0003
#define CNTL_CHEM_ID      0x0006
#define CNTL_GAUGE_START  0x0011
#define CNTL_GAUGE_STOP   0x0012

static int rd16(uint8_t reg, uint16_t *val)
{
	uint8_t buf[2];
	int err = i2c_burst_read(i2c, ADDR, reg, buf, 2);
	if (err) return err;
	*val = buf[0] | (buf[1] << 8);
	return 0;
}

static int rd8(uint8_t reg, uint8_t *val)
{
	return i2c_burst_read(i2c, ADDR, reg, val, 1);
}

static int ctl(uint16_t subcmd)
{
	uint8_t buf[3] = {REG_CONTROL, subcmd & 0xFF, subcmd >> 8};
	return i2c_write(i2c, buf, 3, ADDR);
}

static int ctl_read(uint16_t subcmd, uint16_t *val)
{
	int err = ctl(subcmd);
	if (err) return err;
	k_msleep(10);
	return rd16(REG_CONTROL, val);
}

/* --- Interrupt on P0.02 --- */

static struct gpio_callback fuel_int_cb;
static volatile uint32_t fuel_int_count;
static volatile uint32_t fuel_int_last_ms;

static void fuel_int_handler(const struct device *port, struct gpio_callback *cb,
			     gpio_port_pins_t pins)
{
	ARG_UNUSED(port); ARG_UNUSED(cb); ARG_UNUSED(pins);
	fuel_int_count++;
	fuel_int_last_ms = k_uptime_get_32();
	printk("[fuel] INT! (#%u)\n", fuel_int_count);
}

static int fuel_int_init(void)
{
	if (!gpio_is_ready_dt(&fuel_int)) return 0;
	gpio_pin_configure_dt(&fuel_int, GPIO_INPUT);
	gpio_pin_interrupt_configure_dt(&fuel_int, GPIO_INT_EDGE_TO_ACTIVE);
	gpio_init_callback(&fuel_int_cb, fuel_int_handler, BIT(fuel_int.pin));
	gpio_add_callback(fuel_int.port, &fuel_int_cb);
	return 0;
}
SYS_INIT(fuel_int_init, APPLICATION, 92);

/* --- Shell commands --- */

static int cmd_read(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);
	uint16_t volt, temp, soh, acap, imp, dcap;
	int16_t curr;

	fuel_ge_on();
	if (rd16(REG_VOLT, &volt)) {
		shell_error(sh, "Read failed — device present?");
		return -EIO;
	}
	rd16(REG_TEMP, &temp);
	rd16(REG_CURR, (uint16_t *)&curr);
	rd16(REG_SOH, &soh);
	rd16(REG_ACAP, &acap);
	rd16(REG_MEAS_Z, &imp);
	rd16(REG_DCAP, &dcap);

	shell_print(sh, "Voltage:    %u mV", volt);
	shell_print(sh, "Temp:       %d C", ((int)temp - 2731) / 10);
	shell_print(sh, "Current:    %d mA", curr);
	shell_print(sh, "SOH:        %u %%", soh);
	shell_print(sh, "Capacity:   %u mAh", acap);
	shell_print(sh, "Design Cap: %u mAh", dcap);
	shell_print(sh, "Impedance:  %u mOhm", imp);
	return 0;
}

static int cmd_status(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);
	uint8_t bstat, balert;

	fuel_ge_on();
	if (rd8(REG_BSTAT, &bstat)) {
		shell_error(sh, "Read failed");
		return -EIO;
	}
	rd8(REG_BALERT, &balert);

	shell_print(sh, "Status: 0x%02X  Alert: 0x%02X", bstat, balert);
	shell_print(sh, "  GA=%d DSG=%d BATTPRES=%d EOS=%d SEALED=%d",
		    !!(bstat & 0x01), !!(bstat & 0x02), !!(bstat & 0x08),
		    !!(bstat & 0x40), !!(bstat & 0x80));
	shell_print(sh, "  IRQ count: %u (last: %u ms ago)",
		    fuel_int_count,
		    fuel_int_count ? (k_uptime_get_32() - fuel_int_last_ms) : 0);
	return 0;
}

static int cmd_info(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);
	uint16_t devtype, fwver, hwver, chemid;

	fuel_ge_on();
	if (ctl_read(CNTL_DEVICE_TYPE, &devtype)) {
		shell_error(sh, "Control read failed");
		return -EIO;
	}
	ctl_read(CNTL_FW_VERSION, &fwver);
	ctl_read(CNTL_HW_VERSION, &hwver);
	ctl_read(CNTL_CHEM_ID, &chemid);

	shell_print(sh, "Device: 0x%04X  FW: 0x%04X  HW: 0x%04X  Chem: 0x%04X",
		    devtype, fwver, hwver, chemid);
	return 0;
}

static int cmd_start(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);
	fuel_ge_on();
	if (ctl(CNTL_GAUGE_START)) { shell_error(sh, "Failed"); return -EIO; }
	shell_print(sh, "Gauge ACTIVE");
	return 0;
}

static int cmd_stop(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);
	fuel_ge_on();
	if (ctl(CNTL_GAUGE_STOP)) { shell_error(sh, "Failed"); return -EIO; }
	shell_print(sh, "Gauge SLEEP");
	return 0;
}

static int cmd_scan(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);
	fuel_ge_on();
	int found = 0;
	for (uint8_t a = 0x08; a <= 0x77; a++) {
		struct i2c_msg msg = {.buf = NULL, .len = 0,
				      .flags = I2C_MSG_WRITE | I2C_MSG_STOP};
		if (i2c_transfer(i2c, &msg, 1, a) == 0) {
			shell_print(sh, "  0x%02X%s", a, a == ADDR ? " (BQ35100)" : "");
			found++;
		}
	}
	shell_print(sh, "%d device(s)", found);
	return 0;
}

SHELL_STATIC_SUBCMD_SET_CREATE(sub_fuel,
	SHELL_CMD(read, NULL, "Voltage, temp, current, SOH, capacity", cmd_read),
	SHELL_CMD(status, NULL, "Status flags + IRQ count", cmd_status),
	SHELL_CMD(info, NULL, "Device type, FW, HW, chem ID", cmd_info),
	SHELL_CMD(start, NULL, "GAUGE_START (ACTIVE)", cmd_start),
	SHELL_CMD(stop, NULL, "GAUGE_STOP (SLEEP)", cmd_stop),
	SHELL_CMD(scan, NULL, "I2C bus scan", cmd_scan),
	SHELL_SUBCMD_SET_END
);
SHELL_CMD_REGISTER(fuel, &sub_fuel, "BQ35100 fuel gauge", NULL);
