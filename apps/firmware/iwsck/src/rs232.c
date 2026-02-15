/* RS232/LEMO via uart20 — IRQ-driven RX, poll TX */

#include <zephyr/kernel.h>
#include <zephyr/shell/shell.h>
#include <zephyr/drivers/uart.h>
#include <string.h>

static const struct device *const dev = DEVICE_DT_GET(DT_NODELABEL(uart20));

static volatile uint8_t rx_buf[256];
static volatile uint16_t rx_head;
static volatile uint16_t rx_tail;

static void irq_handler(const struct device *uart, void *user_data)
{
	ARG_UNUSED(user_data);
	while (uart_irq_update(uart) && uart_irq_is_pending(uart)) {
		if (uart_irq_rx_ready(uart)) {
			uint8_t buf[32];
			int len = uart_fifo_read(uart, buf, sizeof(buf));
			for (int i = 0; i < len; i++) {
				uint16_t next = (rx_head + 1) % sizeof(rx_buf);
				if (next != rx_tail) {
					rx_buf[rx_head] = buf[i];
					rx_head = next;
				}
			}
		}
	}
}

static int rx_get(uint8_t *c)
{
	if (rx_head == rx_tail) return -1;
	*c = rx_buf[rx_tail];
	rx_tail = (rx_tail + 1) % sizeof(rx_buf);
	return 0;
}

static void tx_str(const char *s)
{
	while (*s) uart_poll_out(dev, *s++);
}

static int rs232_init(void)
{
	if (!device_is_ready(dev)) return 0;
	uart_irq_callback_set(dev, irq_handler);
	uart_irq_rx_enable(dev);
	return 0;
}
SYS_INIT(rs232_init, APPLICATION, 91);

static int cmd_send(const struct shell *sh, size_t argc, char **argv)
{
	if (argc < 2) {
		shell_error(sh, "Usage: rs232 send <text>");
		return -EINVAL;
	}
	for (size_t i = 1; i < argc; i++) {
		tx_str(argv[i]);
		if (i < argc - 1) uart_poll_out(dev, ' ');
	}
	tx_str("\r\n");
	shell_print(sh, "TX: %d arg(s)", (int)(argc - 1));
	return 0;
}

static int cmd_recv(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);
	uint8_t ch;
	int n = 0;
	while (rx_get(&ch) == 0) {
		shell_fprintf(sh, SHELL_NORMAL, (ch >= 0x20 && ch < 0x7F) ? "%c" : "\\x%02X", ch);
		n++;
	}
	shell_print(sh, n ? "\n[%d bytes]" : "(empty)", n);
	return 0;
}

static int cmd_loopback(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);
	uint8_t dummy;
	while (rx_get(&dummy) == 0) {}

	const char *test = "IWSCK-LOOPBACK-TEST";
	int len = strlen(test);
	tx_str(test);
	k_msleep(200);

	int ok = 0, idx = 0;
	uint8_t ch;
	while (rx_get(&ch) == 0 && idx < len) {
		if (ch == (uint8_t)test[idx]) ok++;
		else shell_warn(sh, "MISMATCH @%d: 0x%02X!=0x%02X", idx, test[idx], ch);
		idx++;
	}

	if (ok == len)
		shell_print(sh, "LOOPBACK PASS — %d/%d bytes", ok, len);
	else if (idx == 0)
		shell_error(sh, "NO RX DATA — check cable (LEMO pin 3->4)");
	else
		shell_error(sh, "LOOPBACK FAIL — %d/%d OK", ok, len);
	return 0;
}

SHELL_STATIC_SUBCMD_SET_CREATE(sub_rs232,
	SHELL_CMD(send, NULL, "TX text out RS232/LEMO", cmd_send),
	SHELL_CMD(recv, NULL, "Dump RX buffer", cmd_recv),
	SHELL_CMD(loopback, NULL, "Loopback test (LEMO 3->4)", cmd_loopback),
	SHELL_SUBCMD_SET_END
);
SHELL_CMD_REGISTER(rs232, &sub_rs232, "RS232/LEMO via uart20", NULL);
