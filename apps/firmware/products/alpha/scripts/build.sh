#!/bin/bash
# Alpha firmware build wrapper for Concord monorepo
# Builds alpha_fw (production) and alpha_mfg_fw (manufacturing) with correct
# monorepo paths, then collects artifacts to artifacts/
#
# Usage:
#   bash scripts/build.sh all               # Build both app + mfg firmware
#   bash scripts/build.sh app [-b BOARD]     # Build production firmware only
#   bash scripts/build.sh mfg               # Build manufacturing firmware only
#   bash scripts/build.sh clean             # Remove all build dirs and artifacts
#   bash scripts/build.sh all --pristine    # Force clean rebuild of everything
#
# MTIB revision and variant support:
#   bash scripts/build.sh app --mtib-rev 1.2              # Production release for REV 1.2
#   bash scripts/build.sh app --mtib-rev 1.1 --variant debug  # Debug build for REV 1.1
#   bash scripts/build.sh mfg --mtib-rev 1.2              # Mfg firmware for REV 1.2

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Resolve absolute paths from this script's location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ARTIFACTS_DIR="${PROJECT_DIR}/artifacts"

APP_FW_DIR="${PROJECT_DIR}/alpha_fw"
MFG_FW_DIR="${PROJECT_DIR}/alpha_mfg_fw"
OVERLAYS_DIR="${PROJECT_DIR}/overlays"

# ---------- argument parsing ----------

TARGET="${1:-all}"
shift || true

BOARD="alpha_b0"
PRISTINE=""
MTIB_REV="1.1"       # Default: REV 1.1 (pin swap) for backward compatibility
VARIANT=""            # Default: release-like (no extra logging). Options: debug

while [[ $# -gt 0 ]]; do
    case $1 in
        -b|--board)     BOARD="$2"; shift 2 ;;
        --pristine)     PRISTINE="--pristine"; shift ;;
        --mtib-rev)     MTIB_REV="$2"; shift 2 ;;
        --variant)      VARIANT="$2"; shift 2 ;;
        *)              echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
    esac
done

# Validate MTIB revision
case $MTIB_REV in
    1.1|1.2) ;;
    *)
        echo -e "${RED}Unsupported MTIB revision: ${MTIB_REV}${NC}"
        echo "Supported revisions: 1.1, 1.2"
        exit 1
        ;;
esac

echo -e "${CYAN}MTIB revision: REV ${MTIB_REV}${NC}"
if [ -n "$VARIANT" ]; then
    echo -e "${CYAN}Build variant: ${VARIANT}${NC}"
fi

# Determine comms SOC from board
case $BOARD in
    alpha_a0) COMM_SOC="nrf9160" ;;
    alpha_b0) COMM_SOC="nrf9151" ;;
    *)
        echo -e "${RED}Unsupported board: ${BOARD}${NC}"
        echo "Supported boards: alpha_a0, alpha_b0"
        exit 1
        ;;
esac

# ---------- helpers ----------

fix_sysbuild_key_path() {
    local conf_file="$1"
    local key_dir="$2"
    # Normalize any previous absolute path to the current one
    sed -i \
        -e "s|SB_CONFIG_BOOT_ENCRYPTION_KEY_FILE=\"[^\"]*\"|SB_CONFIG_BOOT_ENCRYPTION_KEY_FILE=\"${key_dir}/comms_encryption_key.pem\"|g" \
        "$conf_file"
}

collect_artifacts() {
    local label="$1"
    local out_dir="${ARTIFACTS_DIR}/${label}/${BOARD}"
    local app_hex="$2"
    local comms_hex="$3"
    local dfu_zip="$4"

    mkdir -p "$out_dir"

    if [ -f "$app_hex" ]; then
        cp "$app_hex" "$out_dir/app_nrf52840.hex"
        echo -e "  ${GREEN}app_nrf52840.hex${NC}"
    fi
    if [ -f "$comms_hex" ]; then
        cp "$comms_hex" "$out_dir/comms_${COMM_SOC}.hex"
        echo -e "  ${GREEN}comms_${COMM_SOC}.hex${NC}"
    fi
    if [ -n "$dfu_zip" ] && [ -f "$dfu_zip" ]; then
        cp "$dfu_zip" "$out_dir/dfu_application.zip"
        echo -e "  ${GREEN}dfu_application.zip${NC}"
    fi

    echo -e "${GREEN}Artifacts → ${out_dir}/${NC}"
}

# ---------- alpha_fw (production) ----------

build_app_fw() {
    local FW_DIR="$APP_FW_DIR"
    local COMM_DIR="${FW_DIR}/comm_coproc_mfg"

    # --- Resolve DTS overlays based on MTIB revision ---
    # Overlays are in overlays/ (repo level), NOT in the submodule.
    # Submodule overlay files are referenced read-only when combining.
    local APP_DTS_OVERLAY=""
    local COMMS_DTS_OVERLAY=""
    if [[ "$MTIB_REV" == "1.1" ]]; then
        # REV 1.1: submodule I2C overlay + repo-level pin swap overlay
        APP_DTS_OVERLAY="-DDTC_OVERLAY_FILE=${FW_DIR}/boards/${BOARD}_nrf52840.overlay;${OVERLAYS_DIR}/nrf52840_pinswap.overlay"
        # nRF9151 needs pin swap overlay for REV 1.1
        COMMS_DTS_OVERLAY="-DDTC_OVERLAY_FILE=${OVERLAYS_DIR}/nrf9151_ns_pinswap.overlay"
    else
        # REV 1.2: auto-discovered overlay from submodule (I2C only, no pin swap)
        # Don't pass -DDTC_OVERLAY_FILE so Zephyr auto-discovers the submodule's
        # boards/alpha_b0_nrf52840.overlay which has I2C sensors but no pin swap.
        APP_DTS_OVERLAY=""
        # No DTS overlay needed for comms on REV 1.2 (base DTS pins are correct)
        COMMS_DTS_OVERLAY=""
    fi

    # --- Resolve extra configs based on variant ---
    local APP_EXTRA_CONF="${FW_DIR}/version.conf"
    local COMMS_EXTRA_CONF="${FW_DIR}/version.conf;${FW_DIR}/default_personalization.conf"
    if [[ "$VARIANT" == "debug" ]]; then
        APP_EXTRA_CONF="${FW_DIR}/version.conf;${FW_DIR}/logging.conf"
        COMMS_EXTRA_CONF="${FW_DIR}/version.conf;${FW_DIR}/default_personalization.conf;${COMM_DIR}/dev.conf"
    fi

    echo -e "${CYAN}══════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Building alpha_fw (${BOARD} / ${COMM_SOC})${NC}"
    echo -e "${CYAN}  MTIB REV ${MTIB_REV} | variant: ${VARIANT:-release}${NC}"
    echo -e "${CYAN}══════════════════════════════════════════${NC}"

    # --- Application processor (nRF52840) ---
    echo -e "\n${CYAN}[1/4] Application Processor (nRF52840)${NC}"
    west build ${PRISTINE:---pristine} \
        -d "${FW_DIR}/build" \
        -b "${BOARD}/nrf52840" \
        --sysbuild "${FW_DIR}" \
        -- \
        -DBOARD_ROOT="${FW_DIR}/ck_boards/current/" \
        "-DEXTRA_CONF_FILE=${APP_EXTRA_CONF}" \
        ${APP_DTS_OVERLAY}

    # --- Merge VSM PSP hex ---
    echo -e "\n${CYAN}[2/4] Merging VSM PSP hex${NC}"
    mergehex -m \
        "${FW_DIR}/build/merged.hex" \
        "${FW_DIR}/vsm_drv/src/corekinect/module/vsm/threads/vitals/lib/bin/psp.hex" \
        -o "${FW_DIR}/build/merged.hex"

    # --- Communications coprocessor ---
    echo -e "\n${CYAN}[3/4] Communication Coprocessor (${COMM_SOC})${NC}"
    fix_sysbuild_key_path "${COMM_DIR}/sysbuild.conf" "${FW_DIR}"
    echo "# FIPS hash - placeholder for first build" > "${COMM_DIR}/fips.conf"

    west build --pristine \
        -d "${COMM_DIR}/build" \
        -b "${BOARD}/${COMM_SOC}/ns" \
        --sysbuild "${COMM_DIR}" \
        -- \
        -DBOARD_ROOT="${FW_DIR}/ck_boards/current/" \
        "-DEXTRA_CONF_FILE=${COMMS_EXTRA_CONF}" \
        ${COMMS_DTS_OVERLAY}

    # --- FIPS hash recalculation + final rebuild ---
    echo -e "\n${CYAN}[4/4] FIPS hash recalculation + final rebuild${NC}"
    python3 "${COMM_DIR}/wolfssl/scripts/gen_fips_hash.py" \
        "${COMM_DIR}/build/merged.hex" \
        "${COMM_DIR}/build/comm_coproc_mfg/zephyr/zephyr.map" \
        > "${COMM_DIR}/fips.conf"

    west build \
        -d "${COMM_DIR}/build" \
        -b "${BOARD}/${COMM_SOC}/ns" \
        --sysbuild "${COMM_DIR}" \
        -- \
        -DBOARD_ROOT="${FW_DIR}/ck_boards/current/" \
        -DOVERLAY_CONFIG=fips.conf \
        "-DEXTRA_CONF_FILE=${COMMS_EXTRA_CONF}" \
        ${COMMS_DTS_OVERLAY}

    echo -e "\n${GREEN}alpha_fw build complete${NC}"
    collect_artifacts "alpha_fw" \
        "${FW_DIR}/build/merged.hex" \
        "${COMM_DIR}/build/merged.hex" \
        "${FW_DIR}/build/dfu_application.zip"
}

# ---------- alpha_mfg_fw (manufacturing) ----------

build_mfg_fw() {
    local FW_DIR="$MFG_FW_DIR"
    local COMM_DIR="${FW_DIR}/comm_coproc_mfg"
    # mfg always builds alpha_b0
    local MFG_BOARD="alpha_b0"
    local MFG_SOC="nrf9151"

    # --- Resolve DTS overlays based on MTIB revision ---
    # Overlays are in overlays/ (repo level), NOT in the submodule.
    # Submodule overlay files are referenced read-only when combining.
    local APP_DTS_OVERLAY=""
    local COMMS_DTS_OVERLAY=""
    if [[ "$MTIB_REV" == "1.1" ]]; then
        # REV 1.1: submodule overlays already have pin swap baked in
        APP_DTS_OVERLAY="-DDTC_OVERLAY_FILE=${FW_DIR}/boards/alpha_b0_nrf52840.overlay"
        COMMS_DTS_OVERLAY="-DDTC_OVERLAY_FILE=${FW_DIR}/boards/alpha_b0_nrf9151_ns.overlay"
    else
        # REV 1.2: submodule overlay (I2C + pin swap) + correction overlay (pins back to default)
        APP_DTS_OVERLAY="-DDTC_OVERLAY_FILE=${FW_DIR}/boards/alpha_b0_nrf52840.overlay;${OVERLAYS_DIR}/nrf52840_default_pins.overlay"
        # nRF9151: submodule overlay is pin swap only; correction restores defaults
        COMMS_DTS_OVERLAY="-DDTC_OVERLAY_FILE=${OVERLAYS_DIR}/nrf9151_ns_default_pins.overlay"
    fi

    echo -e "${CYAN}══════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Building alpha_mfg_fw (${MFG_BOARD})${NC}"
    echo -e "${CYAN}  MTIB REV ${MTIB_REV}${NC}"
    echo -e "${CYAN}══════════════════════════════════════════${NC}"

    # --- Application processor (nRF52840) ---
    echo -e "\n${CYAN}[1/4] Application Processor (nRF52840)${NC}"
    west build ${PRISTINE:---pristine} \
        -d "${FW_DIR}/build" \
        -b "${MFG_BOARD}/nrf52840" \
        --sysbuild "${FW_DIR}" \
        -- \
        -DBOARD_ROOT="${FW_DIR}/ck_boards/current/" \
        -DEXTRA_CONF_FILE="${FW_DIR}/version.conf" \
        ${APP_DTS_OVERLAY}

    # --- Merge VSM PSP hex ---
    echo -e "\n${CYAN}[2/4] Merging VSM PSP hex${NC}"
    mergehex -m \
        "${FW_DIR}/build/merged.hex" \
        "${FW_DIR}/vsm_drv/src/corekinect/module/vsm/threads/vitals/lib/bin/psp.hex" \
        -o "${FW_DIR}/build/merged.hex"

    # --- Communications coprocessor with mfg shell ---
    echo -e "\n${CYAN}[3/4] Communication Coprocessor (${MFG_SOC}) + mfg shell${NC}"
    fix_sysbuild_key_path "${COMM_DIR}/sysbuild.conf" "${FW_DIR}"
    echo "# FIPS hash - placeholder for first build" > "${COMM_DIR}/fips.conf"

    west build --pristine \
        -d "${COMM_DIR}/build" \
        -b "${MFG_BOARD}/${MFG_SOC}/ns" \
        --sysbuild "${COMM_DIR}" \
        -- \
        -DBOARD_ROOT="${FW_DIR}/ck_boards/current/" \
        -DOVERLAY_CONFIG=dev.conf \
        "-DEXTRA_CONF_FILE=${FW_DIR}/version.conf;${FW_DIR}/default_personalization.conf" \
        ${COMMS_DTS_OVERLAY}

    # --- FIPS hash recalculation + final rebuild ---
    echo -e "\n${CYAN}[4/4] FIPS hash recalculation + final rebuild${NC}"
    if [ ! -f "${COMM_DIR}/build/merged.hex" ] || [ ! -f "${COMM_DIR}/build/comm_coproc_mfg/zephyr/zephyr.map" ]; then
        echo -e "${RED}ERROR: First build failed - missing required files for FIPS hash${NC}"
        exit 1
    fi

    python3 "${COMM_DIR}/wolfssl/scripts/gen_fips_hash.py" \
        "${COMM_DIR}/build/merged.hex" \
        "${COMM_DIR}/build/comm_coproc_mfg/zephyr/zephyr.map" \
        > "${COMM_DIR}/fips.conf"

    if grep -q "Errno" "${COMM_DIR}/fips.conf"; then
        echo -e "${RED}ERROR: FIPS hash generation failed${NC}"
        cat "${COMM_DIR}/fips.conf"
        exit 1
    fi

    west build \
        -d "${COMM_DIR}/build" \
        -b "${MFG_BOARD}/${MFG_SOC}/ns" \
        --sysbuild "${COMM_DIR}" \
        -- \
        -DBOARD_ROOT="${FW_DIR}/ck_boards/current/" \
        "-DOVERLAY_CONFIG=dev.conf;fips.conf" \
        "-DEXTRA_CONF_FILE=${FW_DIR}/version.conf;${FW_DIR}/default_personalization.conf" \
        ${COMMS_DTS_OVERLAY}

    echo -e "\n${GREEN}alpha_mfg_fw build complete${NC}"
    collect_artifacts "alpha_mfg_fw" \
        "${FW_DIR}/build/merged.hex" \
        "${COMM_DIR}/build/merged.hex" \
        "${FW_DIR}/build/dfu_application.zip"
}

# ---------- clean ----------

do_clean() {
    echo -e "${YELLOW}Cleaning alpha build artifacts...${NC}"
    rm -rf "${APP_FW_DIR}/build" "${APP_FW_DIR}/comm_coproc_mfg/build"
    rm -rf "${MFG_FW_DIR}/build" "${MFG_FW_DIR}/comm_coproc_mfg/build"
    rm -rf "${ARTIFACTS_DIR}"
    echo -e "${GREEN}Clean complete${NC}"
}

# ---------- main ----------

case $TARGET in
    app)   build_app_fw ;;
    mfg)   build_mfg_fw ;;
    all)   build_app_fw && build_mfg_fw ;;
    clean) do_clean ;;
    *)
        echo "Usage: $0 {all|app|mfg|clean} [-b BOARD] [--mtib-rev 1.1|1.2] [--variant debug] [--pristine]"
        echo ""
        echo "Targets:"
        echo "  all    Build both alpha_fw and alpha_mfg_fw"
        echo "  app    Build alpha_fw (production) only"
        echo "  mfg    Build alpha_mfg_fw (manufacturing) only"
        echo "  clean  Remove all build directories and artifacts"
        echo ""
        echo "Options:"
        echo "  -b, --board BOARD       Board variant (default: alpha_b0)"
        echo "                          Supported: alpha_a0, alpha_b0"
        echo "  --mtib-rev 1.1|1.2      MTIB hardware revision (default: 1.1)"
        echo "                          1.1 = UART pin swap overlay applied"
        echo "                          1.2 = default pins (no swap)"
        echo "  --variant debug         Build variant for production firmware"
        echo "                          debug = UART logging + shell enabled"
        echo "                          (omit for release: UART silent)"
        echo "  --pristine              Force clean rebuild"
        echo ""
        echo "Artifacts are placed in: artifacts/<variant>/<board>/"
        exit 1
        ;;
esac
