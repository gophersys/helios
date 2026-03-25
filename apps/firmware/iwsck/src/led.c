/* RGB LED control — active-low on GPIO port 2 */

#include <zephyr/kernel.h>
#include <zephyr/shell/shell.h>
#include <zephyr/drivers/gpio.h>
#include <string.h>

static const struct gpio_dt_spec leds[] = {
	GPIO_DT_SPEC_GET(DT_NODELABEL(led_red), gpios),
	GPIO_DT_SPEC_GET(DT_NODELABEL(led_green), gpios),
	GPIO_DT_SPEC_GET(DT_NODELABEL(led_blue), gpios),
};
static const char *led_names[] = {"red", "green", "blue"};

static int led_init_fn(void)
{
	for (int i = 0; i < 3; i++)
		gpio_pin_configure_dt(&leds[i], GPIO_OUTPUT_INACTIVE);
	return 0;
}
SYS_INIT(led_init_fn, APPLICATION, 90);

static int cmd_led(const struct shell *sh, size_t argc, char **argv)
{
	if (argc < 3) {
		shell_error(sh, "Usage: led <red|green|blue> <on|off|toggle>");
		return -EINVAL;
	}

	int idx = -1;
	for (int i = 0; i < 3; i++) {
		if (strcmp(argv[1], led_names[i]) == 0) { idx = i; break; }
	}
	if (idx < 0) {
		shell_error(sh, "Unknown LED: %s", argv[1]);
		return -EINVAL;
	}

	if (strcmp(argv[2], "on") == 0)          gpio_pin_set_dt(&leds[idx], 1);
	else if (strcmp(argv[2], "off") == 0)     gpio_pin_set_dt(&leds[idx], 0);
	else if (strcmp(argv[2], "toggle") == 0)  gpio_pin_toggle_dt(&leds[idx]);
	else {
		shell_error(sh, "Unknown action: %s", argv[2]);
		return -EINVAL;
	}

	shell_print(sh, "LED %s: %s", argv[1], argv[2]);
	return 0;
}

SHELL_CMD_REGISTER(led, NULL, "led <red|green|blue> <on|off|toggle>", cmd_led);
