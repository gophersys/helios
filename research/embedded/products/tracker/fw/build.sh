#!/usr/bin/env bash
# The committed build entry point — the G4 build must be reproducible from
# the repository alone, never from an operator's shell history.
# Run inside the devcontainer, from the repo root.
set -euo pipefail
cd "$(dirname "$0")/../../.."
export ZEPHYR_BASE="$PWD/ws/zephyr"
[ -d "$ZEPHYR_BASE" ] || { echo "FAIL: no west workspace — run .devcontainer/west-init.sh" >&2; exit 1; }
west build -p -b esp32c6_devkitc/esp32c6/hpcore products/tracker/fw -d build/tracker "$@"
echo "artifact: build/tracker/zephyr/zephyr.bin"
