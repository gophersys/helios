# Alpha B0 nRF52840 Shell Test Firmware

MTIB UART shell test firmware for the Alpha B0 host board nRF52840 processor.

## Purpose

Provides a simple Zephyr shell over UART0 for manufacturing test bench (MTIB) validation.
The Alpha B0 board uses the REV 1.2 UART pinout (TX=P0.23, RX=P0.25), which differs from
the Theta B0 (REV 1.1) pins. This firmware targets the correct Alpha B0 pin configuration.

## UART Configuration

| Signal | Pin   | Baud Rate |
|--------|-------|-----------|
| TX     | P0.23 | 115200    |
| RX     | P0.25 | 115200    |

Console and shell are both mapped to UART0.

## Shell Commands

| Command                              | Description                            |
|--------------------------------------|----------------------------------------|
| `test ping`                          | Responds with `pong` (UART check)      |
| `test info`                          | Board revision, UART pins, build date  |
| `test led <red\|green\|blue> <on\|off>` | Control onboard LEDs                |
| `test gpio <port.pin> <in\|out> [high\|low]` | Raw GPIO read/write            |

## LED Pinout

| LED   | Pin   | Active |
|-------|-------|--------|
| Red   | P0.17 | Low    |
| Green | P0.13 | Low    |
| Blue  | P0.15 | Low    |

A heartbeat thread blinks the green LED every 2 seconds to indicate the firmware is running.

## Build

```bash
west build -b alpha_b0/nrf52840 apps/firmware/test/alpha_b0_nrf52840_shell \
  -- -DBOARD_ROOT=/workspaces/concord/libs/zephyr/ck_boards/current \
     -DDTS_ROOT=/workspaces/concord/libs/zephyr/ck_boards/current
```

Or from the app directory (using the paths already set in CMakeLists.txt):

```bash
cd apps/firmware/test/alpha_b0_nrf52840_shell
west build -b alpha_b0/nrf52840 .
```

## Flash via MTIB

1. Build the firmware to produce `build/zephyr/zephyr.hex`
2. Upload the hex file to the MTIB test bench
3. Flash to the nRF52840 target via the MTIB J-Link interface

## Test

1. Open a UART stream to the nRF52840 at 115200 baud
2. Type `test ping` and press Enter
3. Expect response: `pong`
4. Type `test info` for full board/pin diagnostics
