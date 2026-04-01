#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Alpha Build Recipe — Concord platform
#
# Builds Alpha firmware for both processors:
#   nRF52840 (app) + nRF9151 (comms coprocessor)
#
# Handles both firmware types via CONCORD_FW_TYPE:
#   app → production/validation firmware from alpha_fw repo
#   mfg → manufacturing firmware from alpha_mfg_fw repo
#
# Signing keys are managed by Concord Secrets and deployed by the orchestrator
# to both repos before this recipe runs. The sysbuild.conf references are
# fixed by the SDK's concord_init.
# ─────────────────────────────────────────────────────────────────────────────

source /app/sdk/concord-build.sh
concord_init

REPO="${CONCORD_REPO_DIR}"
BOARD="${CONCORD_BOARD}"
COMMS_SOC="${CONCORD_COMMS_SOC:-nrf9151}"
COMMS_DIR="${REPO}/comm_coproc_mfg"

# ── Extra config files ──────────────────────────────────────────────────────

EXTRA_CONF="${REPO}/version.conf"

# Add logging.conf for UART output on verbose/debug builds
if [ "$CONCORD_CONFIG_LOG" = "y" ] && [ -f "${REPO}/logging.conf" ]; then
    EXTRA_CONF="${EXTRA_CONF};${REPO}/logging.conf"
fi

# Add default personalization for comms processor
COMMS_EXTRA="${REPO}/version.conf"
if [ -f "${REPO}/default_personalization.conf" ]; then
    COMMS_EXTRA="${COMMS_EXTRA};${REPO}/default_personalization.conf"
fi

# MFG builds enable the manufacturing shell via dev.conf
COMMS_OVERLAY=""
if [ "$CONCORD_FW_TYPE" = "mfg" ]; then
    COMMS_OVERLAY="dev.conf"
fi

# ── Build Application Processor (nRF52840) ──────────────────────────────────

echo -e "${CYAN}Building Application (nRF52840)...${NC}"
west build --pristine \
    -d ${REPO}/build/app \
    -b ${BOARD}/nrf52840 \
    --sysbuild ${REPO} \
    -- -DBOARD_ROOT=${REPO}/ck_boards/current/ \
       -DEXTRA_CONF_FILE="${EXTRA_CONF}"

# Merge PSP hex (vitals processing library)
PSP_HEX="${REPO}/vsm_drv/src/corekinect/module/vsm/threads/vitals/lib/bin/psp.hex"
if [ -f "$PSP_HEX" ]; then
    mergehex -m ${REPO}/build/app/merged.hex "$PSP_HEX" -o ${REPO}/build/app/merged.hex
fi

# ── Build Communications Coprocessor (nRF9151) ──────────────────────────────

echo -e "${CYAN}Building Comms (${COMMS_SOC})...${NC}"

# Fix encryption key path (SDK already deployed the key, just fix the config path)
sed -i "s|/workspaces/[a-z_]*/comms_encryption_key.pem|${REPO}/comms_encryption_key.pem|g" \
    ${COMMS_DIR}/sysbuild.conf 2>/dev/null || true

# Clear FIPS hash for first build
echo "# FIPS placeholder" > ${COMMS_DIR}/fips.conf

# First comms build
west build --pristine \
    -d ${COMMS_DIR}/build \
    -b ${BOARD}/${COMMS_SOC}/ns \
    --sysbuild ${COMMS_DIR} \
    -- -DBOARD_ROOT=${REPO}/ck_boards/current/ \
       ${COMMS_OVERLAY:+-DOVERLAY_CONFIG=${COMMS_OVERLAY}} \
       -DEXTRA_CONF_FILE="${COMMS_EXTRA}"

# ── FIPS Hash + Rebuild ─────────────────────────────────────────────────────

echo -e "${CYAN}Calculating FIPS hash...${NC}"
python3 ${COMMS_DIR}/wolfssl/scripts/gen_fips_hash.py \
    ${COMMS_DIR}/build/merged.hex \
    ${COMMS_DIR}/build/comm_coproc_mfg/zephyr/zephyr.map > ${COMMS_DIR}/fips.conf

if grep -q "Errno" ${COMMS_DIR}/fips.conf 2>/dev/null; then
    echo -e "${RED}FIPS hash generation failed${NC}"
    cat ${COMMS_DIR}/fips.conf
    exit 1
fi

# Rebuild with FIPS hash
FIPS_OVERLAY="fips.conf"
if [ -n "$COMMS_OVERLAY" ]; then
    FIPS_OVERLAY="${COMMS_OVERLAY};fips.conf"
fi

west build \
    -d ${COMMS_DIR}/build \
    -b ${BOARD}/${COMMS_SOC}/ns \
    --sysbuild ${COMMS_DIR} \
    -- -DBOARD_ROOT=${REPO}/ck_boards/current/ \
       -DOVERLAY_CONFIG="${FIPS_OVERLAY}" \
       -DEXTRA_CONF_FILE="${COMMS_EXTRA}"

# ── Collect Artifacts ────────────────────────────────────────────────────────

echo -e "${CYAN}Collecting artifacts...${NC}"

# App hex — always at ${REPO}/build/app/merged.hex
concord_collect_hex app ${REPO}/build/app/merged.hex

# Comms hex — always at ${COMMS_DIR}/build/merged.hex
concord_collect_hex comms ${COMMS_DIR}/build/merged.hex

# App CFW — the sysbuild project name matches the repo directory name
# alpha_fw → build/app/alpha_fw/zephyr/zephyr.signed.encrypted.bin
# alpha_mfg_fw → build/app/alpha_mfg_fw/zephyr/zephyr.signed.encrypted.bin
REPO_NAME=$(basename ${REPO})
APP_BIN="${REPO}/build/app/${REPO_NAME}/zephyr/zephyr.signed.encrypted.bin"
concord_collect_cfw app "$APP_BIN"

# Comms CFW — always comm_coproc_mfg
COMMS_BIN="${COMMS_DIR}/build/comm_coproc_mfg/zephyr/zephyr.signed.encrypted.bin"
concord_collect_cfw comms "$COMMS_BIN"

concord_finalize
