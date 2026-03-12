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
#
# CI worker mode (set env vars):
#   REPO_DIR=/path/to/cloned/repo OUTPUT_DIR=/path/to/artifacts BOARD=alpha_b0 VARIANT=debug MTIB_REV=1.2 bash build.sh

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
    # CI mode: REPO_DIR is the cloned firmware repo (alpha_fw or alpha_mfg_fw)
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
    BOARD="${BOARD:-alpha_b0}"
    MTIB_REV="${MTIB_REV:-1.2}"
    VARIANT="${VARIANT:-}"
    ARTIFACTS_DIR="${OUTPUT_DIR:-${REPO_DIR}/artifacts}"
    OVERLAYS_DIR="${REPO_DIR}/overlays"  # May not exist in standalone repos

    # Version override for N+1 builds (FUOTA testing)
    # If VERSION_BUILD_OVERRIDE is set, modify BUILD_NUM in VersionDevice.h files
    # The BUILD_NUM is hardcoded in VersionDevice.h, not in version.conf
    if [ -n "$VERSION_BUILD_OVERRIDE" ]; then
        echo -e "${CYAN}Version override: build=${VERSION_BUILD_OVERRIDE}${NC}"

        # Find all VersionDevice.h files and update BUILD_NUM
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
    APP_FW_DIR="${PROJECT_DIR}/alpha_fw"
    MFG_FW_DIR="${PROJECT_DIR}/alpha_mfg_fw"
    OVERLAYS_DIR="${PROJECT_DIR}/overlays"
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
fi

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

# ---------- Create overlays in CI mode if missing ----------
if [ "$CI_MODE" == "true" ] && [ ! -d "$OVERLAYS_DIR" ]; then
    echo -e "${CYAN}Creating overlay files for CI mode...${NC}"
    mkdir -p "$OVERLAYS_DIR"

    # nRF52840 pin swap overlay for REV 1.1 (UART TX/RX swapped)
    cat > "${OVERLAYS_DIR}/nrf52840_pinswap.overlay" << 'OVERLAY_EOF'
/* Pin swap overlay for REV 1.1 MTIB - UART TX/RX reversed */
&uart0 {
    tx-pin = <7>;
    rx-pin = <6>;
};
OVERLAY_EOF

    # nRF52840 default pins overlay for REV 1.2 (corrects pin swap in submodule)
    cat > "${OVERLAYS_DIR}/nrf52840_default_pins.overlay" << 'OVERLAY_EOF'
/* Default pins overlay for REV 1.2 MTIB - no pin swap needed */
&uart0 {
    tx-pin = <6>;
    rx-pin = <7>;
};
OVERLAY_EOF

    # nRF9151 pin swap overlay for REV 1.1
    cat > "${OVERLAYS_DIR}/nrf9151_ns_pinswap.overlay" << 'OVERLAY_EOF'
/* Pin swap overlay for REV 1.1 MTIB - UART TX/RX reversed */
&uart0 {
    tx-pin = <29>;
    rx-pin = <28>;
};
OVERLAY_EOF

    # nRF9151 default pins overlay for REV 1.2
    cat > "${OVERLAYS_DIR}/nrf9151_ns_default_pins.overlay" << 'OVERLAY_EOF'
/* Default pins overlay for REV 1.2 MTIB - no pin swap needed */
&uart0 {
    tx-pin = <28>;
    rx-pin = <29>;
};
OVERLAY_EOF

    echo -e "${GREEN}Overlay files created in ${OVERLAYS_DIR}${NC}"
fi

# ---------- Create VAL server config in CI mode ----------
# Override default server URL to point to VAL CoreCloud instead of DEV
if [ "$CI_MODE" == "true" ]; then
    VAL_SERVER_CONF="${OVERLAYS_DIR}/val_server.conf"
    mkdir -p "$OVERLAYS_DIR"
    cat > "$VAL_SERVER_CONF" << 'VAL_CONF_EOF'
# VAL CoreCloud server configuration (overrides dev defaults)
CONFIG_SOCKET_SERVER_DEFAULT_URL="val.office.corekinect.cloud"
CONFIG_SOCKET_SERVER_DEFAULT_TIME_PORT=2016
CONFIG_SOCKET_SERVER_DEFAULT_SESS_PORT=2018
CONFIG_SOCKET_SERVER_DEFAULT_DATA_PORT=2017
# VAL time server EC P-256 public key (different from DEV server)
CONFIG_SOCKET_SERVER_DEFAULT_TS_PUB_KEY="044E1C9C3D79BD0972DAFC8EF56E078EDFE44C8B21A57AFDC2AE5F2DDE834A99B8B387E4EBD31A16DFAFA70434F20B2CF3B8C0633A5E45ECDF29D6E61B127673AB"
VAL_CONF_EOF
    echo -e "${CYAN}VAL server config created: ${VAL_SERVER_CONF}${NC}"
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

generate_cfw() {
    # Generate a .cfw file from a signed encrypted bin
    # Usage: generate_cfw <bin_path> <app_id> <major> <minor> <build> <track> <mfg> <debug> <output_path>
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

    # Generate CFW using inline Python (no external dependencies)
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

# Patch VersionDevice.h files with correct BUILD_NUM before compilation
# This ensures the compiled firmware reports the correct version
patch_version_device_h() {
    local fw_dir="$1"
    local build_num="$2"

    if [ -z "$build_num" ]; then
        echo -e "${YELLOW}Warning: No build number provided for patching${NC}"
        return
    fi

    echo -e "${CYAN}Patching VersionDevice.h files with BUILD_NUM=${build_num}...${NC}"

    # Find and patch all VersionDevice.h files in the firmware directory
    local patched=0
    while IFS= read -r -d '' vh_file; do
        if grep -q "^#define BUILD_NUM" "$vh_file"; then
            sed -i "s/^#define BUILD_NUM.*/#define BUILD_NUM         ${build_num}/" "$vh_file"
            echo -e "  ${GREEN}Patched: ${vh_file}${NC}"
            patched=$((patched + 1))
        fi
    done < <(find "$fw_dir" -name "VersionDevice.h" -print0 2>/dev/null)

    if [ $patched -eq 0 ]; then
        echo -e "${YELLOW}Warning: No VersionDevice.h files found to patch${NC}"
    else
        echo -e "${GREEN}Patched ${patched} VersionDevice.h file(s)${NC}"
    fi
}

# Resolve version from version.conf and optionally VersionDevice.h
# Sets: VERSION_MAJOR, VERSION_MINOR, VERSION_BUILD, VERSION_STRING
resolve_version() {
    local fw_dir="$1"
    local version_conf="${fw_dir}/version.conf"

    VERSION_MAJOR=""
    VERSION_MINOR=""
    VERSION_BUILD=""

    if [ -f "$version_conf" ]; then
        echo -e "${CYAN}Reading version from: ${version_conf}${NC}"

        # Try current alpha_fw format first
        VERSION_MAJOR=$(grep -E "^CONFIG_APP_FW_MAJOR_VERSION=" "$version_conf" 2>/dev/null | cut -d'=' -f2)
        VERSION_MINOR=$(grep -E "^CONFIG_APP_FW_MINOR_VERSION=" "$version_conf" 2>/dev/null | cut -d'=' -f2)
        VERSION_BUILD=$(grep -E "^CONFIG_APP_FW_BUILD_VERSION=" "$version_conf" 2>/dev/null | cut -d'=' -f2)

        # Try legacy format if not found
        [ -z "$VERSION_MAJOR" ] && VERSION_MAJOR=$(grep -E "^CONFIG_FW_INFO_VERSION_MAJOR=" "$version_conf" 2>/dev/null | cut -d'=' -f2)
        [ -z "$VERSION_MINOR" ] && VERSION_MINOR=$(grep -E "^CONFIG_FW_INFO_VERSION_MINOR=" "$version_conf" 2>/dev/null | cut -d'=' -f2)
        [ -z "$VERSION_BUILD" ] && VERSION_BUILD=$(grep -E "^CONFIG_FW_INFO_VERSION_BUILD=" "$version_conf" 2>/dev/null | cut -d'=' -f2)
    fi

    # Defaults
    VERSION_MAJOR="${VERSION_MAJOR:-0}"
    VERSION_MINOR="${VERSION_MINOR:-0}"

    # Build number priority: VERSION_BUILD_OVERRIDE > version.conf > VersionDevice.h > BUILD_NUM env > 0
    if [ -n "$VERSION_BUILD_OVERRIDE" ]; then
        VERSION_BUILD="$VERSION_BUILD_OVERRIDE"
        echo -e "${CYAN}Using VERSION_BUILD_OVERRIDE=${VERSION_BUILD}${NC}"
    elif [ -z "$VERSION_BUILD" ]; then
        # Read from VersionDevice.h
        local vh_file="${fw_dir}/src/VersionDevice.h"
        if [ -f "$vh_file" ]; then
            VERSION_BUILD=$(grep -E "^#define BUILD_NUM" "$vh_file" 2>/dev/null | awk '{print $3}')
            [ -n "$VERSION_BUILD" ] && echo -e "${CYAN}Read BUILD_NUM=${VERSION_BUILD} from VersionDevice.h${NC}"
        fi
        VERSION_BUILD="${VERSION_BUILD:-${BUILD_NUM:-0}}"
    fi

    VERSION_STRING="${VERSION_MAJOR}.${VERSION_MINOR}.${VERSION_BUILD}"
    echo -e "${GREEN}Resolved version: ${VERSION_STRING}${NC}"
}

collect_artifacts() {
    local label="$1"
    local app_hex="$2"
    local comms_hex="$3"
    local dfu_zip="$4"
    local fw_dir="$5"      # firmware build dir for finding encrypted bins
    local comms_dir="$6"   # comms build dir

    # Extract version from version.conf early (needed for directory structure)
    # Supports both formats:
    #   - CONFIG_FW_INFO_VERSION_MAJOR/MINOR/BUILD (legacy)
    #   - CONFIG_APP_FW_MAJOR_VERSION/MINOR_VERSION (current alpha_fw)
    local version_conf="${fw_dir:-$REPO_DIR}/version.conf"
    local version_major=""
    local version_minor=""
    local version_build=""

    if [ -f "$version_conf" ]; then
        echo -e "${CYAN}Reading version from: ${version_conf}${NC}"
        cat "$version_conf"

        # Try legacy format first
        version_major=$(grep -E "^CONFIG_FW_INFO_VERSION_MAJOR=" "$version_conf" 2>/dev/null | cut -d'=' -f2)
        version_minor=$(grep -E "^CONFIG_FW_INFO_VERSION_MINOR=" "$version_conf" 2>/dev/null | cut -d'=' -f2)
        version_build=$(grep -E "^CONFIG_FW_INFO_VERSION_BUILD=" "$version_conf" 2>/dev/null | cut -d'=' -f2)

        # If not found, try current alpha_fw format
        if [ -z "$version_major" ]; then
            version_major=$(grep -E "^CONFIG_APP_FW_MAJOR_VERSION=" "$version_conf" 2>/dev/null | cut -d'=' -f2)
        fi
        if [ -z "$version_minor" ]; then
            version_minor=$(grep -E "^CONFIG_APP_FW_MINOR_VERSION=" "$version_conf" 2>/dev/null | cut -d'=' -f2)
        fi
        if [ -z "$version_build" ]; then
            version_build=$(grep -E "^CONFIG_APP_FW_BUILD_VERSION=" "$version_conf" 2>/dev/null | cut -d'=' -f2)
        fi
    else
        echo -e "${YELLOW}Warning: version.conf not found at ${version_conf}${NC}"
    fi

    # Default to 0 if empty, use BUILD_NUM env var if version_build is still empty
    version_major="${version_major:-0}"
    version_minor="${version_minor:-0}"
    # For build number: use VERSION_BUILD_OVERRIDE if set, else version.conf value, else VersionDevice.h, else BUILD_NUM env, else 0
    if [ -n "$VERSION_BUILD_OVERRIDE" ]; then
        version_build="$VERSION_BUILD_OVERRIDE"
    elif [ -z "$version_build" ]; then
        # Try to read BUILD_NUM from VersionDevice.h (source of truth for compiled firmware)
        local version_device_h="${fw_dir:-$REPO_DIR}/src/VersionDevice.h"
        if [ -f "$version_device_h" ]; then
            local h_build_num
            h_build_num=$(grep -E "^#define BUILD_NUM" "$version_device_h" 2>/dev/null | awk '{print $3}')
            if [ -n "$h_build_num" ]; then
                echo -e "${CYAN}Read BUILD_NUM=${h_build_num} from VersionDevice.h${NC}"
                version_build="$h_build_num"
            fi
        fi
        # Final fallback to env var or 0
        version_build="${version_build:-${BUILD_NUM:-0}}"
    fi
    local version_string="${version_major}.${version_minor}.${version_build}"
    echo -e "${GREEN}Resolved version: ${version_string}${NC}"

    # Determine variant folder name: "debug" or "no_debug"
    local variant_folder="no_debug"
    if [[ "$VARIANT" == "debug" ]]; then
        variant_folder="debug"
    fi

    # In CI mode, output to versioned directory structure: <version>/<variant>/
    # In local mode, use nested structure: <label>/<board>/
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

    # Determine CFW flags:
    # - Track: 0=Bench (for CI/validation builds)
    # - Mfg: 1 if label contains "mfg"
    # - Debug: 1 if VARIANT=debug (determined by variant_folder)
    local cfw_track=0  # Always Bench for CI builds
    local cfw_mfg=0
    local cfw_debug=0

    if [[ "$label" == *"mfg"* ]]; then
        cfw_mfg=1
    fi
    if [[ "$variant_folder" == "debug" ]]; then
        cfw_debug=1
    fi

    # Generate CFW files from encrypted signed bins
    echo -e "${CYAN}Generating CFW files...${NC}"

    # App processor CFW (app_id=109 for nRF52840)
    local app_bin="${fw_dir}/build/repo/zephyr/zephyr.signed.encrypted.bin"
    if [ -f "$app_bin" ]; then
        generate_cfw "$app_bin" 109 "$version_major" "$version_minor" "$version_build" \
            $cfw_track $cfw_mfg $cfw_debug "$out_dir/109.${version_major}.${version_minor}.${version_build}.cfw"
    fi

    # Comms processor CFW (app_id=108 for nRF9151)
    local comms_bin="${comms_dir}/build/comm_coproc_mfg/zephyr/zephyr.signed.encrypted.bin"
    if [ -f "$comms_bin" ]; then
        generate_cfw "$comms_bin" 108 "$version_major" "$version_minor" "$version_build" \
            $cfw_track $cfw_mfg $cfw_debug "$out_dir/108.${version_major}.${version_minor}.${version_build}.cfw"
    fi

    # Validate generated CFW files
    echo -e "${CYAN}Validating CFW artifacts...${NC}"
    local validation_failed=0
    for cfw_file in "$out_dir"/*.cfw; do
        [ -f "$cfw_file" ] || continue
        local cfw_name=$(basename "$cfw_file")

        # Parse CFW header using Python (big-endian: >HQHBHHHI)
        local result=$(python3 -c "
import struct
import sys
with open('$cfw_file', 'rb') as f:
    data = f.read(23)
ver, ts, appid, flags, major, minor, build, imglen = struct.unpack('>HQHBHHHI', data)
print(f'{appid} {major} {minor} {build} {imglen}')
" 2>/dev/null)

        if [ -z "$result" ]; then
            echo -e "  ${RED}FAIL: ${cfw_name} - could not parse header${NC}"
            validation_failed=1
            continue
        fi

        read cfw_appid cfw_major cfw_minor cfw_build cfw_imglen <<< "$result"

        # Verify version matches expected
        if [ "$cfw_major" != "$version_major" ] || [ "$cfw_minor" != "$version_minor" ] || [ "$cfw_build" != "$version_build" ]; then
            echo -e "  ${RED}FAIL: ${cfw_name} - version mismatch${NC}"
            echo -e "       Expected: ${version_major}.${version_minor}.${version_build}"
            echo -e "       Got:      ${cfw_major}.${cfw_minor}.${cfw_build}"
            validation_failed=1
        else
            echo -e "  ${GREEN}PASS: ${cfw_name} (${cfw_major}.${cfw_minor}.${cfw_build}, appid=${cfw_appid}, ${cfw_imglen} bytes)${NC}"
        fi
    done

    if [ $validation_failed -eq 1 ]; then
        echo -e "${RED}CFW validation FAILED - build artifacts may be incorrect${NC}"
        exit 1
    fi
    echo -e "${GREEN}CFW validation passed${NC}"

    # Generate build.json with version info
    if [ "$CI_MODE" == "true" ]; then
        # Build flag string for JSON
        local track_str="B"  # Bench
        [ $cfw_mfg -eq 1 ] && track_str="${track_str}M"
        [ $cfw_debug -eq 1 ] && track_str="${track_str}D"
        local cfw_flags=$(( (cfw_track << 1) | cfw_mfg | (cfw_debug << 3) ))

        cat > "$out_dir/build.json" << EOF
{
  "product": "${label}",
  "board": "${BOARD}",
  "variant": "${VARIANT:-release}",
  "variant_folder": "${variant_folder}",
  "mtib_rev": "${MTIB_REV}",
  "version": "${version_string}",
  "cfw_flags": ${cfw_flags},
  "cfw_track": "${track_str}",
  "built_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
        echo -e "  ${GREEN}build.json${NC}"
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
    # In CI mode, add VAL server config to override DEV defaults
    if [ "$CI_MODE" == "true" ] && [ -f "${OVERLAYS_DIR}/val_server.conf" ]; then
        COMMS_EXTRA_CONF="${COMMS_EXTRA_CONF};${OVERLAYS_DIR}/val_server.conf"
        echo -e "${CYAN}Adding VAL server config to comms build${NC}"
    fi

    echo -e "${CYAN}══════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Building alpha_fw (${BOARD} / ${COMM_SOC})${NC}"
    echo -e "${CYAN}  MTIB REV ${MTIB_REV} | variant: ${VARIANT:-release}${NC}"
    echo -e "${CYAN}══════════════════════════════════════════${NC}"

    # --- Resolve version and patch VersionDevice.h BEFORE compilation ---
    resolve_version "$FW_DIR"
    patch_version_device_h "$FW_DIR" "$VERSION_BUILD"
    patch_version_device_h "$COMM_DIR" "$VERSION_BUILD"

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
        "${FW_DIR}/build/dfu_application.zip" \
        "${FW_DIR}" \
        "${COMM_DIR}"
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
        # REV 1.1: submodule overlays have pin swap baked in - use them directly
        APP_DTS_OVERLAY="-DDTC_OVERLAY_FILE=${FW_DIR}/boards/alpha_b0_nrf52840.overlay"
        COMMS_DTS_OVERLAY="-DDTC_OVERLAY_FILE=${FW_DIR}/boards/alpha_b0_nrf9151_ns.overlay"
    else
        # REV 1.2: Let Zephyr auto-discover overlays from boards/ directory
        # This matches production build behavior - submodule overlays should have correct pins
        # Note: If mfg submodule has old pin swap, that needs to be fixed in the firmware repo
        APP_DTS_OVERLAY=""
        COMMS_DTS_OVERLAY=""
    fi

    # --- Resolve extra configs for comms (add VAL server in CI mode) ---
    local MFG_COMMS_EXTRA_CONF="${FW_DIR}/version.conf;${FW_DIR}/default_personalization.conf"
    if [ "$CI_MODE" == "true" ] && [ -f "${OVERLAYS_DIR}/val_server.conf" ]; then
        MFG_COMMS_EXTRA_CONF="${MFG_COMMS_EXTRA_CONF};${OVERLAYS_DIR}/val_server.conf"
        echo -e "${CYAN}Adding VAL server config to mfg comms build${NC}"
    fi

    echo -e "${CYAN}══════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Building alpha_mfg_fw (${MFG_BOARD})${NC}"
    echo -e "${CYAN}  MTIB REV ${MTIB_REV}${NC}"
    echo -e "${CYAN}══════════════════════════════════════════${NC}"

    # --- Resolve version and patch VersionDevice.h BEFORE compilation ---
    resolve_version "$FW_DIR"
    patch_version_device_h "$FW_DIR" "$VERSION_BUILD"
    patch_version_device_h "$COMM_DIR" "$VERSION_BUILD"

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
        "-DEXTRA_CONF_FILE=${MFG_COMMS_EXTRA_CONF}" \
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
        "-DEXTRA_CONF_FILE=${MFG_COMMS_EXTRA_CONF}" \
        ${COMMS_DTS_OVERLAY}

    echo -e "\n${GREEN}alpha_mfg_fw build complete${NC}"
    collect_artifacts "alpha_mfg_fw" \
        "${FW_DIR}/build/merged.hex" \
        "${COMM_DIR}/build/merged.hex" \
        "${FW_DIR}/build/dfu_application.zip" \
        "${FW_DIR}" \
        "${COMM_DIR}"
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
