# IWSCK A0 Bring-Up Shell

Interactive shell for exercising IWSCK A0 hardware. Boots to `iwsck>` prompt.

## MUST SET CORRECT CK_BOARD DIRECTORY IN CMAKELISTS.TXT!!!!

## Build & Flash

```bash
west build --pristine --no-sysbuild -b iwsck_a0/nrf54l15/cpuapp .
nrfjprog --program build/zephyr/zephyr.hex --chiperase --verify --reset
```

## Commands

### board info
Pinout, die temp, uptime, clock source.
```
iwsck> board info
IWSCK A0 — nRF54L15 Bring-Up Board
  Console:    uart30  P0.02/P0.03  115200
  RS232/LEMO: uart20  P1.03/P1.02  115200
  I2C (bb):   i2c_bb  P2.00/P2.01  100kHz
  LEDs:       P2.08(R) P2.09(G) P2.10(B) active-low
  Die temp:     30.7 C
  Uptime:       8270 ms
```

### led
RGB control. Active-low GPIOs on port 2.
```
iwsck> led red on
LED red: on
iwsck> led blue toggle
LED blue: toggle
```

### rs232
UART20 → SP3232ECA-L → LEMO connector. IRQ-driven RX, 256-byte ring buffer.
```
iwsck> rs232 loopback
LOOPBACK PASS — 19/19 bytes

iwsck> rs232 send hello
TX: 1 arg(s)

iwsck> rs232 recv
hello\x0D\x0A
[7 bytes]
```
Loopback test needs LEMO pin 3 jumpered to pin 4.

### ble
Connectable GATT server. Inits lazily (~60s first time, RC32K calibration).
```
iwsck> ble start
Initializing BLE (~60s)...
BLE ready
BLE server started (IWSCK-A0)

iwsck> ble stop
BLE stopped
```
Subscribe to the notify characteristic for die temp, uptime, and battery voltage every 2s. Optional name arg: `ble start MyName`.

### fuel
BQ35100 fuel gauge on bit-bang I2C (0x55). P0.00 interrupt, P0.01 enable (hog).
```
iwsck> fuel scan
  0x55 (BQ35100)
1 device(s)

iwsck> fuel read
Voltage:    3971 mV
Temp:       -39 C
Current:    0 mA
SOH:        0 %
Capacity:   0 mAh
Design Cap: 2200 mAh
Impedance:  0 mOhm

iwsck> fuel status
Status: 0x05  Alert: 0x41
  GA=1 DSG=0 BATTPRES=0 EOS=0 SEALED=0
  IRQ count: 1 (last: 33510 ms ago)

iwsck> fuel info
Device: 0xFFA5  FW: 0xFFA5  HW: 0x2080  Chem: 0x2080
```
`fuel start` / `fuel stop` toggle ACTIVE/SLEEP gauging mode.

### Built-in (Zephyr)
```
gpio help          # GPIO pin control
i2c scan i2c_bb    # I2C bus scan
sensor get temp    # Die temperature
kernel reboot warm # Reboot
```

## Hardware Notes

See `libs/zephyr/ck_boards/current/boards/corekinect/iwsck_a0/docs/errata-a0.md` for A0 rework items.
- GPIO port 2 has no interrupts (LEDs, I2C on port 2 — polling only)
- No 32 kHz crystal (LFXO), LF clock is internal RC — BLE init is slow on first start
- NFC pins cut and reworked to RS232
