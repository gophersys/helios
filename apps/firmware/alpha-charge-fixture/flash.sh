#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
ZEPHYR_DIR="$BUILD_DIR/zephyr"
ESPTOOL="/ncs/modules/hal/espressif/tools/esptool_py/esptool.py"
OBJCOPY="/usr/local/zephyr-sdk-0.17.4/xtensa-espressif_esp32_zephyr-elf/bin/xtensa-espressif_esp32_zephyr-elf-objcopy"
PORT="${1:-/dev/ttyUSB0}"

echo "=== Extracting DROM and IROM segments ==="
$OBJCOPY -O binary \
    --only-section=.flash.rodata \
    --only-section=initlevel \
    --only-section=device_area \
    "$ZEPHYR_DIR/zephyr.elf" "$ZEPHYR_DIR/drom.bin"

$OBJCOPY -O binary \
    --only-section=.flash.text \
    "$ZEPHYR_DIR/zephyr.elf" "$ZEPHYR_DIR/irom.bin"

echo "=== Flashing to $PORT ==="
python3 "$ESPTOOL" \
    --chip auto \
    --port "$PORT" \
    --baud 921600 \
    --before default_reset \
    --after hard_reset \
    write_flash -u \
    --flash_mode dio \
    --flash_freq 40m \
    --flash_size detect \
    0x1000 "$ZEPHYR_DIR/zephyr.bin" \
    0x20000 "$ZEPHYR_DIR/drom.bin" \
    0x30000 "$ZEPHYR_DIR/irom.bin"

echo "=== Flash complete ==="
