#!/bin/bash
set -eo pipefail

# Alpha Build Recipe
# Builds nRF52840 (app) + nRF9151 (comms) firmware
# Uses CONCORD_FW_TYPE to handle app vs mfg firmware

source /app/sdk/concord-build.sh
concord_init

REPO="$CONCORD_REPO_DIR"
BOARD="$CONCORD_BOARD"
COMMS_SOC="${CONCORD_COMMS_SOC:-nrf9151}"
COMMS_DIR="$REPO/comm_coproc_mfg"
REPO_NAME=$(basename "$REPO")

# ── Config files ─────────────────────────────────────────

APP_CONF="$REPO/version.conf"
COMMS_CONF="$REPO/version.conf"

# Verbose builds get UART logging
if [ "$CONCORD_CONFIG_LOG" = "y" ] && [ -f "$REPO/logging.conf" ]; then
    APP_CONF="$APP_CONF;$REPO/logging.conf"
fi

# Comms gets default personalization
if [ -f "$REPO/default_personalization.conf" ]; then
    COMMS_CONF="$COMMS_CONF;$REPO/default_personalization.conf"
fi

# MFG builds enable the manufacturing shell
COMMS_OVERLAY=""
if [ "$CONCORD_FW_TYPE" = "mfg" ]; then
    COMMS_OVERLAY="dev.conf"
fi

# DTS overlays (only if they exist)
APP_OVERLAY="$REPO/boards/${BOARD}_nrf52840.overlay"
[ ! -f "$APP_OVERLAY" ] && APP_OVERLAY=""

COMMS_DTS_OVERLAY="$REPO/boards/${BOARD}_${COMMS_SOC}_ns.overlay"
[ ! -f "$COMMS_DTS_OVERLAY" ] && COMMS_DTS_OVERLAY=""

# ── Build App (nRF52840) ─────────────────────────────────

echo "Building app (nRF52840)..."

west build --pristine \
    -d "$REPO/build/app" \
    -b "$BOARD/nrf52840" \
    --sysbuild "$REPO" \
    -- -DBOARD_ROOT="$REPO/ck_boards/current/" \
       -DEXTRA_CONF_FILE="$APP_CONF" \
       ${APP_OVERLAY:+-DDTC_OVERLAY_FILE="$APP_OVERLAY"}

# Merge PSP hex (vitals processing library) if present
PSP_HEX="$REPO/vsm_drv/src/corekinect/module/vsm/threads/vitals/lib/bin/psp.hex"
if [ -f "$PSP_HEX" ]; then
    mergehex -m "$REPO/build/app/merged.hex" "$PSP_HEX" -o "$REPO/build/app/merged.hex"
fi

# ── Build Comms (nRF9151) ────────────────────────────────

echo "Building comms ($COMMS_SOC)..."

# Fix encryption key path to match deployed location
sed -i "s|/workspaces/[a-z_]*/comms_encryption_key.pem|$REPO/comms_encryption_key.pem|g" \
    "$COMMS_DIR/sysbuild.conf" 2>/dev/null || true

# Clear FIPS hash placeholder for first build
echo "# FIPS placeholder" > "$COMMS_DIR/fips.conf"

west build --pristine \
    -d "$COMMS_DIR/build" \
    -b "$BOARD/$COMMS_SOC/ns" \
    --sysbuild "$COMMS_DIR" \
    -- -DBOARD_ROOT="$REPO/ck_boards/current/" \
       ${COMMS_OVERLAY:+-DOVERLAY_CONFIG="$COMMS_OVERLAY"} \
       -DEXTRA_CONF_FILE="$COMMS_CONF" \
       ${COMMS_DTS_OVERLAY:+-DDTC_OVERLAY_FILE="$COMMS_DTS_OVERLAY"}

# ── FIPS hash + rebuild ──────────────────────────────────

echo "Calculating FIPS hash..."

python3 "$COMMS_DIR/wolfssl/scripts/gen_fips_hash.py" \
    "$COMMS_DIR/build/merged.hex" \
    "$COMMS_DIR/build/comm_coproc_mfg/zephyr/zephyr.map" > "$COMMS_DIR/fips.conf"

if grep -q "Errno" "$COMMS_DIR/fips.conf" 2>/dev/null; then
    echo "ERROR: FIPS hash generation failed"
    cat "$COMMS_DIR/fips.conf"
    exit 1
fi

FIPS_OVERLAY="fips.conf"
[ -n "$COMMS_OVERLAY" ] && FIPS_OVERLAY="$COMMS_OVERLAY;fips.conf"

west build \
    -d "$COMMS_DIR/build" \
    -b "$BOARD/$COMMS_SOC/ns" \
    --sysbuild "$COMMS_DIR" \
    -- -DBOARD_ROOT="$REPO/ck_boards/current/" \
       -DOVERLAY_CONFIG="$FIPS_OVERLAY" \
       -DEXTRA_CONF_FILE="$COMMS_CONF" \
       ${COMMS_DTS_OVERLAY:+-DDTC_OVERLAY_FILE="$COMMS_DTS_OVERLAY"}

# ── Collect artifacts ────────────────────────────────────

echo "Collecting artifacts..."

concord_collect_hex app   "$REPO/build/app/merged.hex"
concord_collect_hex comms "$COMMS_DIR/build/merged.hex"
concord_collect_cfw app   "$REPO/build/app/$REPO_NAME/zephyr/zephyr.signed.encrypted.bin"
concord_collect_cfw comms "$COMMS_DIR/build/comm_coproc_mfg/zephyr/zephyr.signed.encrypted.bin"

concord_finalize
