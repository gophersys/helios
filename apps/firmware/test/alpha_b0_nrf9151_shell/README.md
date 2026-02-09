# Alpha B0 nRF9151 Shell Test Firmware

MTIB UART shell test firmware for the nRF9151 communications processor on the Alpha B0 host board (REV 1.2 pinout).

## Purpose

Provides a minimal Zephyr shell over UART0 for MTIB test bench validation. Replaces the older theta_b0 test hexes which had the REV 1.1 (swapped) UART pin configuration.

**UART0 pins (Alpha B0 / REV 1.2):** TX=P0.21, RX=P0.22, 115200 baud

## Build

```bash
cd apps/firmware/test/alpha_b0_nrf9151_shell

west build -b alpha_b0/nrf9151_ns -- \
  -DBOARD_ROOT=/workspaces/concord/libs/zephyr/ck_boards/current \
  -DDTS_ROOT=/workspaces/concord/libs/zephyr/ck_boards/current
```

Or, since BOARD_ROOT and DTS_ROOT are set in CMakeLists.txt:

```bash
west build
```

## Flash via MTIB

Upload the built hex (`build/zephyr/zephyr.hex`) to the MTIB server and flash to the nRF9151 target.

## Shell Commands

| Command | Description |
|---------|-------------|
| `test ping` | Responds with `pong` (UART connectivity check) |
| `test info` | Prints board revision, UART pins, build date |
| `test led <red\|green\|blue> <on\|off>` | Control onboard LEDs |
| `test modem` | Read modem IMEI and ICCID via AT commands |

## Test

1. Open UART stream to the nRF9151 at 115200 baud
2. Type `test ping` and press Enter
3. Expect response: `pong`

## Notes

- The blue LED blinks every 2 seconds as a heartbeat indicator
- Green LED flashes briefly on successful boot
- Modem commands require a SIM card to be inserted
- Modem initialization failure is non-fatal; the shell remains functional
- Board uses TF-M (Trusted Firmware-M) for the secure partition
