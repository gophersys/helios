#!/bin/bash
# Theta firmware build wrapper for Concord monorepo
# Builds theta_fw (production) and theta_mfg_fw (manufacturing) with correct
# monorepo paths, then collects artifacts to artifacts/
#
# Usage:
#   bash scripts/build.sh all               # Build both app + mfg firmware
#   bash scripts/build.sh app [-b BOARD]    # Build production firmware only
#   bash scripts/build.sh mfg               # Build manufacturing firmware only
#   bash scripts/build.sh clean             # Remove all build dirs and artifacts
#   bash scripts/build.sh all --pristine    # Force clean rebuild of everything
#
# CI worker mode (set env vars):
#   REPO_DIR=/path/to/cloned/repo OUTPUT_DIR=/path/to/artifacts BOARD=theta_c0 VARIANT=debug bash build.sh

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ---------- CI mode detection ----------
# When REPO_DIR is set, we're running via CI worker with a standalone repo clone
CI_MODE="${REPO_DIR:+true}"

if [ "$CI_MODE" == "true" ]; then
    # CI mode: REPO_DIR is the cloned firmware repo (theta_fw or theta_mfg_fw)
    # OUTPUT_DIR is where artifacts should go
    # FIRMWARE_TYPE is set by the worker (app or mfg)
    if [ -n "$FIRMWARE_TYPE" ]; then
        CI_PRODUCT="$FIRMWARE_TYPE"
    elif [ -f "${REPO_DIR}/comm_coproc_mfg/dev.conf" ] && grep -q "IS_MANUFACTURING=y" "${REPO_DIR}/comm_coproc_mfg/dev.conf" 2>/dev/null; then
        # Fallback: detect from files
        CI_PRODUCT="mfg"
    else
        CI_PRODUCT="app"
    fi
    echo -e "${CYAN}CI mode: Building ${CI_PRODUCT} (FIRMWARE_TYPE=${FIRMWARE_TYPE:-auto}) from REPO_DIR=${REPO_DIR}${NC}"

    # Use env vars for build config
    BOARD="${BOARD:-theta_c0}"
    VARIANT="${VARIANT:-}"
    ARTIFACTS_DIR="${OUTPUT_DIR:-${REPO_DIR}/artifacts}"

    # Version override for N+1 builds (FUOTA testing)
    if [ -n "$VERSION_BUILD_OVERRIDE" ]; then
        echo -e "${CYAN}Version override: build=${VERSION_BUILD_OVERRIDE}${NC}"

        VERSION_FILES=$(find "${REPO_DIR}" -name "VersionDevice.h" -type f 2>/dev/null)
        VERSION_UPDATED=false

        for version_file in $VERSION_FILES; do
            if grep -q "^#define BUILD_NUM" "$version_file"; then
                sed -i "s/^#define BUILD_NUM.*/#define BUILD_NUM         ${VERSION_BUILD_OVERRIDE}/" "$version_file"
                echo -e "${GREEN}Updated BUILD_NUM in $version_file${NC}"
                VERSION_UPDATED=true
            fi
        done

        if [ "$VERSION_UPDATED" = "true" ]; then
            echo -e "${GREEN}Version override applied: BUILD_NUM=${VERSION_BUILD_OVERRIDE}${NC}"
        else
            echo -e "${YELLOW}Warning: No VersionDevice.h files found to update${NC}"
        fi
    fi

    # Set FW_DIR based on product type (same directory in CI mode)
    APP_FW_DIR="${REPO_DIR}"
    MFG_FW_DIR="${REPO_DIR}"
else
    # Monorepo mode: resolve paths from script location
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    ARTIFACTS_DIR="${PROJECT_DIR}/artifacts"
    APP_FW_DIR="${PROJECT_DIR}/theta_fw"
    MFG_FW_DIR="${PROJECT_DIR}/theta_mfg_fw"
fi

# ---------- argument parsing ----------

if [ "$CI_MODE" == "true" ]; then
    # CI mode: target is auto-detected, args come from env vars
    TARGET="${CI_PRODUCT}"
    PRISTINE="--pristine"  # Always pristine in CI
else
    # Monorepo mode: parse command line args
    TARGET="${1:-all}"
    shift || true

    BOARD="theta_c0"
    PRISTINE=""
    VARIANT=""            # Default: release-like (no extra logging). Options: debug

    while [[ $# -gt 0 ]]; do
        case $1 in
            -b|--board)     BOARD="$2"; shift 2 ;;
            --pristine)     PRISTINE="--pristine"; shift ;;
            --variant)      VARIANT="$2"; shift 2 ;;
            *)              echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
        esac
    done
fi

# Validate board
case $BOARD in
    theta_a0|theta_b0|theta_c0) ;;
    *)
        echo -e "${RED}Unsupported board: ${BOARD}${NC}"
        echo "Supported boards: theta_a0, theta_b0, theta_c0"
        exit 1
        ;;
esac

echo -e "${CYAN}Board: ${BOARD}${NC}"
if [ -n "$VARIANT" ]; then
    echo -e "${CYAN}Build variant: ${VARIANT}${NC}"
fi

# Theta uses nRF9160 for comms
COMM_SOC="nrf9160"

# ---------- helpers ----------

fix_sysbuild_key_path() {
    local conf_file="$1"
    local key_dir="$2"
    local key_name="${3:-comms_encryption_key.pem}"
    sed -i \
        -e "s|SB_CONFIG_BOOT_ENCRYPTION_KEY_FILE=\"[^\"]*\"|SB_CONFIG_BOOT_ENCRYPTION_KEY_FILE=\"${key_dir}/${key_name}\"|g" \
        "$conf_file"
}

generate_cfw() {
    # Generate a .cfw file from a signed encrypted bin
    local bin_path="$1"
    local app_id="$2"
    local major="$3"
    local minor="$4"
    local build="$5"
    local track="$6"      # 0=Bench, 1=Eng, 2=Prod
    local mfg="$7"        # 0 or 1
    local debug="$8"      # 0 or 1
    local output="$9"

    if [ ! -f "$bin_path" ]; then
        echo -e "${YELLOW}Warning: No encrypted bin at $bin_path, skipping CFW${NC}"
        return 1
    fi

    python3 << PYCFW
import struct
import time
from pathlib import Path

bin_path = "$bin_path"
app_id = $app_id
major = $major
minor = $minor
build = $build
track = $track  # 0=Bench, 1=Eng, 2=Prod
mfg = $mfg
debug = $debug
output = "$output"

# Read encrypted firmware
image_bin = Path(bin_path).read_bytes()

# Encode flags: bit0=mfg, bits2:1=track, bit3=debug
flags = ((track & 0x03) << 1) | (mfg & 0x01) | ((debug & 0x01) << 3)

# Create header (CFW v2: 23 bytes)
header = struct.pack(
    ">HQHBHHHI",  # big-endian
    2,                    # file_version
    int(time.time()),     # timestamp
    app_id,
    flags,
    major,
    minor,
    build,
    len(image_bin),
)

# Write CFW file
Path(output).write_bytes(header + image_bin)

# Generate flag string for display
track_str = {0: "B", 1: "E", 2: "P"}.get(track, "?")
if mfg: track_str += "M"
if debug: track_str += "D"
print(f"  Generated: {output} (flags=0x{flags:02x}, {track_str})")
PYCFW
}

collect_artifacts() {
    local label="$1"
    local app_hex="$2"
    local comms_hex="$3"
    local dfu_zip="$4"
    local fw_dir="$5"
    local comms_dir="$6"

    # Extract version from version.conf
    local version_conf="${fw_dir:-$REPO_DIR}/version.conf"
    local version_major=""
    local version_minor=""
    local version_build=""

    if [ -f "$version_conf" ]; then
        echo -e "${CYAN}Reading version from: ${version_conf}${NC}"
        cat "$version_conf"

        version_major=$(grep -E "^CONFIG_APP_FW_MAJOR_VERSION=" "$version_conf" 2>/dev/null | cut -d'=' -f2)
        version_minor=$(grep -E "^CONFIG_APP_FW_MINOR_VERSION=" "$version_conf" 2>/dev/null | cut -d'=' -f2)
        version_build=$(grep -E "^CONFIG_APP_FW_BUILD_VERSION=" "$version_conf" 2>/dev/null | cut -d'=' -f2)
    else
        echo -e "${YELLOW}Warning: version.conf not found at ${version_conf}${NC}"
    fi

    version_major="${version_major:-0}"
    version_minor="${version_minor:-0}"
    if [ -n "$VERSION_BUILD_OVERRIDE" ]; then
        version_build="$VERSION_BUILD_OVERRIDE"
    elif [ -z "$version_build" ]; then
        version_build="${BUILD_NUM:-1}"
    fi
    local version_string="${version_major}.${version_minor}.${version_build}"
    echo -e "${GREEN}Resolved version: ${version_string}${NC}"

    local variant_folder="no_debug"
    if [[ "$VARIANT" == "debug" ]]; then
        variant_folder="debug"
    fi

    local out_dir
    if [ "$CI_MODE" == "true" ]; then
        out_dir="${ARTIFACTS_DIR}/${version_string}/${variant_folder}"
    else
        out_dir="${ARTIFACTS_DIR}/${label}/${BOARD}"
    fi

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

    echo -e "  ${CYAN}Version: ${version_string}${NC}"
    echo -e "  ${CYAN}Variant: ${variant_folder}${NC}"

    # Determine CFW flags
    local cfw_track=0  # Bench for CI builds
    local cfw_mfg=0
    local cfw_debug=0

    if [[ "$label" == *"mfg"* ]]; then
        cfw_mfg=1
    fi
    if [[ "$variant_folder" == "debug" ]]; then
        cfw_debug=1
    fi

    # Generate CFW files
    echo -e "${CYAN}Generating CFW files...${NC}"

    # App processor CFW (app_id=107 for Theta nRF52840)
    local app_bin="${fw_dir}/build/repo/zephyr/zephyr.signed.encrypted.bin"
    if [ -f "$app_bin" ]; then
        generate_cfw "$app_bin" 107 "$version_major" "$version_minor" "$version_build" \
            $cfw_track $cfw_mfg $cfw_debug "$out_dir/107.${version_major}.${version_minor}.${version_build}.cfw"
    fi

    # Comms processor CFW (app_id=100 for shared comm_coproc_mfg)
    local comms_bin="${comms_dir}/build/comm_coproc_mfg/zephyr/zephyr.signed.encrypted.bin"
    if [ -f "$comms_bin" ]; then
        generate_cfw "$comms_bin" 100 "$version_major" "$version_minor" "$version_build" \
            $cfw_track $cfw_mfg $cfw_debug "$out_dir/100.${version_major}.${version_minor}.${version_build}.cfw"
    fi

    # Generate build.json with version info
    if [ "$CI_MODE" == "true" ]; then
        local track_str="B"
        [ $cfw_mfg -eq 1 ] && track_str="${track_str}M"
        [ $cfw_debug -eq 1 ] && track_str="${track_str}D"
        local cfw_flags=$(( (cfw_track << 1) | cfw_mfg | (cfw_debug << 3) ))

        cat > "$out_dir/build.json" << EOF
{
  "product": "${label}",
  "board": "${BOARD}",
  "variant": "${VARIANT:-release}",
  "variant_folder": "${variant_folder}",
  "version": "${version_string}",
  "cfw_flags": ${cfw_flags},
  "cfw_track": "${track_str}",
  "built_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
        echo -e "  ${GREEN}build.json${NC}"
    fi

    echo -e "${GREEN}Artifacts -> ${out_dir}/${NC}"
}

# ---------- theta_fw (production) ----------

build_app_fw() {
    local FW_DIR="$APP_FW_DIR"
    local COMM_DIR="${FW_DIR}/comm_coproc_mfg"

    local APP_EXTRA_CONF="${FW_DIR}/version.conf"
    local COMMS_EXTRA_CONF="${FW_DIR}/version.conf;${FW_DIR}/default_personalization.conf"
    if [[ "$VARIANT" == "debug" ]]; then
        APP_EXTRA_CONF="${FW_DIR}/version.conf;${FW_DIR}/logging.conf"
        COMMS_EXTRA_CONF="${FW_DIR}/version.conf;${FW_DIR}/default_personalization.conf;${COMM_DIR}/dev.conf"
    fi

    echo -e "${CYAN}======================================${NC}"
    echo -e "${CYAN}  Building theta_fw (${BOARD} / ${COMM_SOC})${NC}"
    echo -e "${CYAN}  variant: ${VARIANT:-release}${NC}"
    echo -e "${CYAN}======================================${NC}"

    # --- Application processor (nRF52840) ---
    echo -e "\n${CYAN}[1/4] Application Processor (nRF52840)${NC}"
    west build ${PRISTINE:---pristine} \
        -d "${FW_DIR}/build" \
        -b "${BOARD}/nrf52840" \
        --sysbuild "${FW_DIR}" \
        -- \
        -DBOARD_ROOT="${FW_DIR}/ck_boards/current/" \
        "-DEXTRA_CONF_FILE=${APP_EXTRA_CONF}"

    # --- Skip VSM PSP hex merge for Theta (no VSM) ---
    echo -e "\n${CYAN}[2/4] Skipping VSM merge (Theta has no VSM)${NC}"

    # --- Communications coprocessor ---
    echo -e "\n${CYAN}[3/4] Communication Coprocessor (${COMM_SOC})${NC}"
    fix_sysbuild_key_path "${COMM_DIR}/sysbuild.conf" "${FW_DIR}" "comms_encryption_key.pem"
    echo "# FIPS hash - placeholder for first build" > "${COMM_DIR}/fips.conf"

    west build --pristine \
        -d "${COMM_DIR}/build" \
        -b "${BOARD}/${COMM_SOC}/ns" \
        --sysbuild "${COMM_DIR}" \
        -- \
        -DBOARD_ROOT="${FW_DIR}/ck_boards/current/" \
        "-DEXTRA_CONF_FILE=${COMMS_EXTRA_CONF}"

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
        "-DEXTRA_CONF_FILE=${COMMS_EXTRA_CONF}"

    echo -e "\n${GREEN}theta_fw build complete${NC}"
    collect_artifacts "theta_fw" \
        "${FW_DIR}/build/merged.hex" \
        "${COMM_DIR}/build/merged.hex" \
        "${FW_DIR}/build/dfu_application.zip" \
        "${FW_DIR}" \
        "${COMM_DIR}"
}

# ---------- theta_mfg_fw (manufacturing) ----------

build_mfg_fw() {
    local FW_DIR="$MFG_FW_DIR"
    local COMM_DIR="${FW_DIR}/comm_coproc_mfg"

    echo -e "${CYAN}======================================${NC}"
    echo -e "${CYAN}  Building theta_mfg_fw (${BOARD})${NC}"
    echo -e "${CYAN}======================================${NC}"

    # --- Fix encryption key paths ---
    echo -e "${CYAN}Fixing encryption key paths...${NC}"
    fix_sysbuild_key_path "${FW_DIR}/sysbuild.conf" "${FW_DIR}" "encryption_key.pem"
    fix_sysbuild_key_path "${COMM_DIR}/sysbuild.conf" "${FW_DIR}" "comms_encryption_key.pem"

    # --- Application processor (nRF52840) ---
    echo -e "\n${CYAN}[1/4] Application Processor (nRF52840)${NC}"
    west build ${PRISTINE:---pristine} \
        -d "${FW_DIR}/build" \
        -b "${BOARD}/nrf52840" \
        --sysbuild "${FW_DIR}" \
        -- \
        -DBOARD_ROOT="${FW_DIR}/ck_boards/current/" \
        -DEXTRA_CONF_FILE="${FW_DIR}/version.conf"

    # --- Skip VSM PSP hex merge for Theta ---
    echo -e "\n${CYAN}[2/4] Skipping VSM merge (Theta has no VSM)${NC}"

    # --- Communications coprocessor with mfg shell ---
    echo -e "\n${CYAN}[3/4] Communication Coprocessor (${COMM_SOC}) + mfg shell${NC}"
    echo "# FIPS hash - placeholder for first build" > "${COMM_DIR}/fips.conf"

    west build --pristine \
        -d "${COMM_DIR}/build" \
        -b "${BOARD}/${COMM_SOC}/ns" \
        --sysbuild "${COMM_DIR}" \
        -- \
        -DBOARD_ROOT="${FW_DIR}/ck_boards/current/" \
        -DOVERLAY_CONFIG=dev.conf \
        "-DEXTRA_CONF_FILE=${FW_DIR}/version.conf;${FW_DIR}/default_personalization.conf"

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
        -b "${BOARD}/${COMM_SOC}/ns" \
        --sysbuild "${COMM_DIR}" \
        -- \
        -DBOARD_ROOT="${FW_DIR}/ck_boards/current/" \
        "-DOVERLAY_CONFIG=dev.conf;fips.conf" \
        "-DEXTRA_CONF_FILE=${FW_DIR}/version.conf;${FW_DIR}/default_personalization.conf"

    echo -e "\n${GREEN}theta_mfg_fw build complete${NC}"
    collect_artifacts "theta_mfg_fw" \
        "${FW_DIR}/build/merged.hex" \
        "${COMM_DIR}/build/merged.hex" \
        "${FW_DIR}/build/dfu_application.zip" \
        "${FW_DIR}" \
        "${COMM_DIR}"
}

# ---------- clean ----------

do_clean() {
    echo -e "${YELLOW}Cleaning theta build artifacts...${NC}"
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
        echo "Usage: $0 {all|app|mfg|clean} [-b BOARD] [--variant debug] [--pristine]"
        echo ""
        echo "Targets:"
        echo "  all    Build both theta_fw and theta_mfg_fw"
        echo "  app    Build theta_fw (production) only"
        echo "  mfg    Build theta_mfg_fw (manufacturing) only"
        echo "  clean  Remove all build directories and artifacts"
        echo ""
        echo "Options:"
        echo "  -b, --board BOARD       Board variant (default: theta_c0)"
        echo "                          Supported: theta_a0, theta_b0, theta_c0"
        echo "  --variant debug         Build variant for production firmware"
        echo "                          debug = UART logging + shell enabled"
        echo "                          (omit for release: UART silent)"
        echo "  --pristine              Force clean rebuild"
        echo ""
        echo "Artifacts are placed in: artifacts/<variant>/<board>/"
        exit 1
        ;;
esac
