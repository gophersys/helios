#!/bin/bash
# Sigma5 firmware build wrapper for Concord monorepo
# Builds sigma5_fw (production, NCS 2.4 cmake) and sigma5_mfg_fw (manufacturing, NCS 2.7 west)
# then collects artifacts to artifacts/
#
# Usage:
#   bash scripts/build.sh all                        # Build both app + mfg firmware
#   bash scripts/build.sh app [--target TARGET]      # Build production firmware only
#   bash scripts/build.sh mfg [-b BOARD]             # Build manufacturing firmware only
#   bash scripts/build.sh clean                      # Remove all build dirs and artifacts
#   bash scripts/build.sh all --pristine             # Force clean rebuild of everything
#
# CI worker mode (env vars):
#   BUILD_DIR=/path/to/artifacts BOARD=sigma5_b0 bash scripts/build.sh app

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ---------- CI mode detection ----------
# CI worker sets BUILD_DIR and runs script from work_dir with repos at ./sigma5_fw/
# In CI mode, repos are at work_dir/sigma5_fw/ and work_dir/sigma5_mfg_fw/
CI_MODE=""
if [ -n "${BUILD_DIR:-}" ] && [ -d "./sigma5_fw" ]; then
    CI_MODE="true"
elif [ -n "${REPO_DIR:-}" ]; then
    # Legacy CI mode (REPO_DIR)
    CI_MODE="true"
fi

if [ "$CI_MODE" = "true" ]; then
    # CI mode - repos are cloned by worker to cwd
    if [ -n "${REPO_DIR:-}" ]; then
        # Legacy: REPO_DIR points to the firmware repo
        APP_FW_DIR="$REPO_DIR"
        PROJECT_DIR="$(dirname "$REPO_DIR")"
    else
        # New: repos are at ./sigma5_fw/ and ./sigma5_mfg_fw/
        APP_FW_DIR="$(pwd)/sigma5_fw"
        PROJECT_DIR="$(pwd)"
    fi
    ARTIFACTS_DIR="${BUILD_DIR:-${OUTPUT_DIR:-/tmp/output}}"
    MFG_FW_DIR="${PROJECT_DIR}/sigma5_mfg_fw"
    echo -e "${CYAN}CI mode: APP_FW_DIR=${APP_FW_DIR}${NC}"
    echo -e "${CYAN}CI mode: ARTIFACTS_DIR=${ARTIFACTS_DIR}${NC}"
else
    # Local mode - paths relative to script
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    ARTIFACTS_DIR="${PROJECT_DIR}/artifacts"
    APP_FW_DIR="${PROJECT_DIR}/sigma5_fw"
    MFG_FW_DIR="${PROJECT_DIR}/sigma5_mfg_fw"
fi

# ---------- argument parsing ----------

TARGET="${1:-all}"
shift || true

# Use BOARD env var from CI if set, otherwise default
# sigma5_fw (NCS 2.4) only has sigma5_b0 in its ck_boards submodule
# sigma5_mfg_fw (NCS 2.7) has both sigma5_b0 and sigma5_c0
BOARD="${BOARD:-sigma5_b0}"
BUILD_TARGET=""
PRISTINE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -b|--board)    BOARD="$2"; shift 2 ;;
        --target)      BUILD_TARGET="$2"; shift 2 ;;
        --pristine)    PRISTINE="yes"; shift ;;
        *)             echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
    esac
done

# ---------- helpers ----------

init_submodules() {
    local repo_dir="$1"
    if [ -f "${repo_dir}/ck_boards/.git" ]; then
        echo -e "${CYAN}Initializing ck_boards submodule...${NC}"
        (cd "$repo_dir" && git submodule update --init --recursive ck_boards)
    fi
}

fix_sysbuild_key_path() {
    local conf_file="$1"
    local key_dir="$2"
    sed -i \
        -e "s|SB_CONFIG_BOOT_ENCRYPTION_KEY_FILE=\"[^\"]*\"|SB_CONFIG_BOOT_ENCRYPTION_KEY_FILE=\"${key_dir}/comms_encryption_key.pem\"|g" \
        "$conf_file"
}

collect_artifact() {
    local out_dir="$1"
    local src_file="$2"
    local dest_name="$3"

    mkdir -p "$out_dir"
    if [ -f "$src_file" ]; then
        cp "$src_file" "$out_dir/$dest_name"
        echo -e "  ${GREEN}${dest_name}${NC}"
    else
        echo -e "  ${YELLOW}${dest_name} (not found: $src_file)${NC}"
    fi
}

# ---------- sigma5_fw (production, cmake + ninja) ----------
# NCS 2.3.0 — uses direct cmake, NOT west/sysbuild
# Two separate builds: nrf52840 (app processor) and nrf9160 (comms)

build_app_fw_52840() {
    local BUILD_DIR="${APP_FW_DIR}/nrf52840/build"
    local BOARD_ROOT="${APP_FW_DIR}/ck_boards"

    echo -e "\n${CYAN}[nrf52840] Application Processor${NC}"

    if [ "$PRISTINE" = "yes" ] && [ -d "$BUILD_DIR" ]; then
        rm -rf "$BUILD_DIR"
    fi

    mkdir -p "$BUILD_DIR"
    cmake -S "${APP_FW_DIR}/nrf52840" -B "$BUILD_DIR" -GNinja \
        -DBOARD="${BOARD}_nrf52840" \
        -DBOARD_ROOT="$BOARD_ROOT" || { echo -e "${RED}CMake failed for nrf52840${NC}"; exit 1; }
    ninja -C "$BUILD_DIR" || { echo -e "${RED}Ninja build failed for nrf52840${NC}"; exit 1; }

    local OUT_DIR="${ARTIFACTS_DIR}/sigma5_fw/nrf52840"
    collect_artifact "$OUT_DIR" "${BUILD_DIR}/zephyr/zephyr.hex" "app_nrf52840.hex"
    collect_artifact "$OUT_DIR" "${BUILD_DIR}/zephyr/zephyr.bin" "app_nrf52840.bin"
    collect_artifact "$OUT_DIR" "${BUILD_DIR}/zephyr/zephyr.elf" "app_nrf52840.elf"
}

build_app_fw_9160() {
    local BUILD_DIR="${APP_FW_DIR}/nrf9160/build"
    local BOARD_ROOT="${APP_FW_DIR}/ck_boards"

    echo -e "\n${CYAN}[nrf9160] Communication Coprocessor${NC}"

    if [ "$PRISTINE" = "yes" ] && [ -d "$BUILD_DIR" ]; then
        rm -rf "$BUILD_DIR"
    fi

    mkdir -p "$BUILD_DIR"
    cmake -S "${APP_FW_DIR}/nrf9160" -B "$BUILD_DIR" -GNinja \
        -DBOARD="${BOARD}_nrf9160" \
        -DBOARD_ROOT="$BOARD_ROOT" || { echo -e "${RED}CMake failed for nrf9160${NC}"; exit 1; }
    ninja -C "$BUILD_DIR" || { echo -e "${RED}Ninja build failed for nrf9160${NC}"; exit 1; }

    local OUT_DIR="${ARTIFACTS_DIR}/sigma5_fw/nrf9160"
    collect_artifact "$OUT_DIR" "${BUILD_DIR}/zephyr/zephyr.hex" "comms_nrf9160.hex"
    collect_artifact "$OUT_DIR" "${BUILD_DIR}/zephyr/zephyr.bin" "comms_nrf9160.bin"
    collect_artifact "$OUT_DIR" "${BUILD_DIR}/zephyr/zephyr.elf" "comms_nrf9160.elf"
}

build_app_fw() {
    echo -e "${CYAN}══════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Building sigma5_fw (NCS 2.4 / cmake)${NC}"
    echo -e "${CYAN}══════════════════════════════════════════${NC}"

    init_submodules "$APP_FW_DIR"

    case "$BUILD_TARGET" in
        nrf52840) build_app_fw_52840 ;;
        nrf9160)  build_app_fw_9160 ;;
        ""|all)   build_app_fw_52840 && build_app_fw_9160 ;;
        *)
            echo -e "${RED}Unknown target: ${BUILD_TARGET}${NC}"
            echo "Supported targets: nrf52840, nrf9160"
            exit 1
            ;;
    esac

    echo -e "\n${GREEN}sigma5_fw build complete${NC}"
    echo -e "${GREEN}Artifacts → ${ARTIFACTS_DIR}/sigma5_fw/${NC}"
}

# ---------- sigma5_mfg_fw (manufacturing, west + sysbuild) ----------
# NCS 2.7.0 — uses west + sysbuild, same dual-processor pattern as alpha

build_mfg_fw() {
    local FW_DIR="$MFG_FW_DIR"
    local COMM_DIR="${FW_DIR}/comm_coproc_mfg"
    local OUT_DIR="${ARTIFACTS_DIR}/sigma5_mfg_fw/${BOARD}"

    echo -e "${CYAN}══════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Building sigma5_mfg_fw (${BOARD})${NC}"
    echo -e "${CYAN}══════════════════════════════════════════${NC}"

    # In CI mode, mfg firmware is built separately via sigma5_mfg_fw job
    if [ -n "${REPO_DIR:-}" ]; then
        echo -e "${YELLOW}Skipping mfg firmware build in CI mode${NC}"
        echo -e "${YELLOW}(sigma5_mfg_fw has its own build job)${NC}"
        return 0
    fi

    if [ ! -d "$FW_DIR" ]; then
        echo -e "${RED}ERROR: source directory $FW_DIR does not exist${NC}"
        exit 1
    fi

    # --- Fix encryption key paths in sysbuild.conf ---
    echo -e "${CYAN}Fixing encryption key paths...${NC}"
    # App processor uses encryption_key.pem
    sed -i "s|SB_CONFIG_BOOT_ENCRYPTION_KEY_FILE=\"[^\"]*\"|SB_CONFIG_BOOT_ENCRYPTION_KEY_FILE=\"${FW_DIR}/encryption_key.pem\"|g" "${FW_DIR}/sysbuild.conf"
    # Comms processor uses comms_encryption_key.pem
    sed -i "s|SB_CONFIG_BOOT_ENCRYPTION_KEY_FILE=\"[^\"]*\"|SB_CONFIG_BOOT_ENCRYPTION_KEY_FILE=\"${FW_DIR}/comms_encryption_key.pem\"|g" "${COMM_DIR}/sysbuild.conf"

    # --- Application processor (nRF52840) ---
    echo -e "\n${CYAN}[1/4] Application Processor (nRF52840)${NC}"
    west build ${PRISTINE:+--pristine} ${PRISTINE:-"--pristine"} \
        -d "${FW_DIR}/build" \
        -b "${BOARD}/nrf52840" \
        --sysbuild "${FW_DIR}" \
        -- \
        -DBOARD_ROOT="${FW_DIR}/ck_boards/current/"

    # --- Communications coprocessor (nRF9160) ---
    echo -e "\n${CYAN}[2/4] Communication Coprocessor (nRF9160)${NC}"

    # Clear fips.conf placeholder
    echo "# FIPS hash - placeholder for first build" > "${COMM_DIR}/fips.conf"

    west build --pristine \
        -d "${COMM_DIR}/build" \
        -b "${BOARD}/nrf9160/ns" \
        --sysbuild "${COMM_DIR}" \
        -- \
        -DBOARD_ROOT="${FW_DIR}/ck_boards/current/" \
        -DEXTRA_CONF_FILE="${FW_DIR}/default_personalization.conf"

    # --- FIPS hash recalculation ---
    echo -e "\n${CYAN}[3/4] FIPS hash recalculation${NC}"
    python3 "${COMM_DIR}/wolfssl/scripts/gen_fips_hash.py" \
        "${COMM_DIR}/build/merged.hex" \
        "${COMM_DIR}/build/comm_coproc_mfg/zephyr/zephyr.map" \
        > "${COMM_DIR}/fips.conf"

    # --- Final rebuild with FIPS ---
    echo -e "\n${CYAN}[4/4] Final rebuild with FIPS hash${NC}"
    west build \
        -d "${COMM_DIR}/build" \
        -b "${BOARD}/nrf9160/ns" \
        --sysbuild "${COMM_DIR}" \
        -- \
        -DBOARD_ROOT="${FW_DIR}/ck_boards/current/" \
        -DOVERLAY_CONFIG=fips.conf \
        -DEXTRA_CONF_FILE="${FW_DIR}/default_personalization.conf"

    echo -e "\n${GREEN}sigma5_mfg_fw build complete${NC}"
    mkdir -p "$OUT_DIR"
    collect_artifact "$OUT_DIR" "${FW_DIR}/build/merged.hex" "app_nrf52840.hex"
    collect_artifact "$OUT_DIR" "${COMM_DIR}/build/merged.hex" "comms_nrf9160.hex"
    echo -e "${GREEN}Artifacts → ${OUT_DIR}/${NC}"
}

# ---------- clean ----------

do_clean() {
    echo -e "${YELLOW}Cleaning sigma5 build artifacts...${NC}"
    rm -rf "${APP_FW_DIR}/nrf52840/build" "${APP_FW_DIR}/nrf9160/build"
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
        echo "Usage: $0 {all|app|mfg|clean} [-b BOARD] [--target TARGET] [--pristine]"
        echo ""
        echo "Targets:"
        echo "  all    Build both sigma5_fw and sigma5_mfg_fw"
        echo "  app    Build sigma5_fw (production, cmake/ninja)"
        echo "  mfg    Build sigma5_mfg_fw (manufacturing, west/sysbuild)"
        echo "  clean  Remove all build directories and artifacts"
        echo ""
        echo "Options:"
        echo "  -b, --board BOARD      Board variant for mfg build (default: sigma5_b0)"
        echo "  --target TARGET        For app build: nrf52840, nrf9160, or both (default)"
        echo "  --pristine             Force clean rebuild"
        echo ""
        echo "Artifacts are placed in: artifacts/<variant>/<board|target>/"
        exit 1
        ;;
esac
