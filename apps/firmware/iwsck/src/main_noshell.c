/* Absolute minimum power test — no shell, no UART, no BLE.
 * Just init and sleep forever. */

#include <zephyr/kernel.h>

int main(void)
{
	k_sleep(K_FOREVER);
	return 0;
}
