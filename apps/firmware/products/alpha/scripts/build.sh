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

set -eo pipefail

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

    # Patch build metadata (git SHA + variant) into VersionDevice.h
    GIT_SHA_SHORT="${COMMIT_SHA:0:7}"
    [ -z "$GIT_SHA_SHORT" ] && GIT_SHA_SHORT="unknown"
    BUILD_VARIANT_STR="${VARIANT:-release}"

    VERSION_FILES=$(find "${REPO_DIR}" -name "VersionDevice.h" -type f 2>/dev/null)
    for version_file in $VERSION_FILES; do
        if grep -q "^#define BUILD_GIT_SHA" "$version_file"; then
            sed -i "s/^#define BUILD_GIT_SHA.*/#define BUILD_GIT_SHA     \"${GIT_SHA_SHORT}\"/" "$version_file"
            sed -i "s/^#define BUILD_VARIANT.*/#define BUILD_VARIANT     \"${BUILD_VARIANT_STR}\"/" "$version_file"
            echo -e "${GREEN}Patched build metadata: sha=${GIT_SHA_SHORT} variant=${BUILD_VARIANT_STR}${NC}"
        fi
    done

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

# ---------- Create overlays ----------
# Always create overlays dir (needed for REV 1.2 MFG sensor overlay)
mkdir -p "$OVERLAYS_DIR"

# REV 1.2 MFG APP overlay: I2C sensors + explicit UART pins (board defaults).
# The submodule's boards/alpha_b0_nrf52840.overlay gets auto-detected by Zephyr
# and swaps UART TX/RX (for REV 1.1 wiring). Sysbuild auto-detection bypasses
# -DDTC_OVERLAY_FILE, so we MUST explicitly set the correct REV 1.2 pins here
# AND remove the auto-detected overlay (done in build_mfg below).
cat > "${OVERLAYS_DIR}/mfg_app_rev12.overlay" << 'OVERLAY_EOF'
/* REV 1.2 MFG overlay: sensors + explicit UART pins (board defaults).
 * Must include pinctrl to override any auto-detected boards/ overlay
 * that swaps TX/RX for REV 1.1. */
/ {
    aliases {
        ioexpander = &lp5814;
        vsm-enable = &vsm_enable;
        i2c-gpio = &ir_i2c;
    };

    ir_i2c: ir_i2c {
        compatible = "gpio-i2c-fast";
        status = "okay";
        clock-frequency = <100000>;
        cpu-frequency = <64000000>;
        #address-cells = <1>;
        #size-cells = <0>;
        scl-gpios = <&gpio1 4 (GPIO_ACTIVE_HIGH | GPIO_PULL_UP)>;
        sda-gpios = <&gpio1 6 (GPIO_ACTIVE_HIGH | GPIO_PULL_UP)>;

        mlx90614: mlx90614@5a {
            status = "okay";
            compatible = "melexis,mlx90614";
            reg = <0x5a>;
            emissivity = <65535>;
        };
    };
};

&i2c1 {
    clock-frequency = <I2C_BITRATE_FAST>;

    bme280: bme280@76 {
        compatible = "bosch,bme280";
        reg = <0x76>;
    };

    lp5814: lp5814@2c {
        compatible = "ti,lp5814";
        reg = <0x2C>;
    };

    pah8151: pah8151@15 {
        status = "okay";
        compatible = "pixart,pah8151";
        reg = <0x15>;
        irq-gpios = <&gpio0 20 GPIO_ACTIVE_HIGH>;
        int1-gpios = <&gpio0 20 GPIO_ACTIVE_HIGH>;
        int2-gpios = <&gpio0 20 GPIO_ACTIVE_HIGH>;
        int-pin = <1>;
        led-current-ir = <255>;
        led-current-red = <255>;
        led-current-green = <255>;
    };
};

/* UART0 pinctrl: REV 1.2 board-default pins (no swap).
 * TX=P0.23, RX=P0.25 — matches alpha_b0_nrf52840-pinctrl.dtsi.
 * Must be explicit to override auto-detected boards/ overlay. */
&pinctrl {
    uart0_default: uart0_default {
        group1 {
            psels = <NRF_PSEL(UART_TX, 0, 23)>;
        };
        group2 {
            psels = <NRF_PSEL(UART_RX, 0, 25)>;
            bias-pull-up;
        };
    };

    uart0_sleep: uart0_sleep {
        group1 {
            psels = <NRF_PSEL(UART_TX, 0, 23)>,
                    <NRF_PSEL(UART_RX, 0, 25)>;
            low-power-enable;
        };
    };
};
OVERLAY_EOF

echo -e "${GREEN}Overlay files created in ${OVERLAYS_DIR}${NC}"

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

# MFG shell and logging (inline fallback — ensures shell works even if dev.conf is missing
# from the submodule checkout; these are safe to apply in all builds as they match dev.conf)
CONFIG_LOG=y
CONFIG_LOG_MODE_DEFERRED=y
CONFIG_LOG_SPEED=y
CONFIG_LOG_BUFFER_SIZE=4096
CONFIG_LOG_BACKEND_UART=y
CONFIG_SHELL=y
CONFIG_SHELL_CMDS_SELECT=y
CONFIG_SHELL_ASYNC_API=y
CONFIG_SHELL_LOG_BACKEND=n
CONFIG_SHELL_PROMPT_UART="Mfg shell: "
CONFIG_SHELL_BACKEND_SERIAL_ASYNC_RX_BUFFER_SIZE=64
CONFIG_SHELL_BACKEND_SERIAL_ASYNC_RX_BUFFER_COUNT=8
CONFIG_SHELL_CMD_BUFF_SIZE=768
CONFIG_SHELL_STACK_SIZE=8192
CONFIG_SHELL_THREAD_PRIORITY_OVERRIDE=y
CONFIG_SHELL_THREAD_PRIORITY=5
CONFIG_BASE64=y
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
    if [ ! -f "$conf_file" ]; then
        return
    fi

    # In CI mode, ALWAYS use the mounted shared key directory (/keys/alpha/)
    # to ensure both alpha_fw and alpha_mfg_fw use the SAME encryption key.
    # Without this, each repo's own key would be used, causing MCUboot decryption
    # failures when FUOTA delivers a CFW encrypted with a different key than
    # what the device's MCUboot expects.
    if [ "$CI_MODE" == "true" ] && [ -d "/keys/alpha" ]; then
        key_dir="/keys/alpha"
        echo -e "${CYAN}Using shared keys from ${key_dir} for $(basename ${conf_file})${NC}"
    fi

    # Fix all SB_CONFIG_BOOT_ENCRYPTION_KEY_FILE references:
    # Replace any absolute path, keeping the filename intact
    sed -i -E \
        "s|SB_CONFIG_BOOT_ENCRYPTION_KEY_FILE=\"[^\"]*/([-_a-zA-Z0-9]+\.pem)\"|SB_CONFIG_BOOT_ENCRYPTION_KEY_FILE=\"${key_dir}/\1\"|g" \
        "$conf_file"
    # Also fix SB_CONFIG_BOOT_SIGNATURE_KEY_FILE if present
    sed -i -E \
        "s|SB_CONFIG_BOOT_SIGNATURE_KEY_FILE=\"[^\"]*/([-_a-zA-Z0-9]+\.pem)\"|SB_CONFIG_BOOT_SIGNATURE_KEY_FILE=\"${key_dir}/\1\"|g" \
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
        # || true: grep returns 1 when key is absent, which kills the script under pipefail
        VERSION_MAJOR=$(grep -E "^CONFIG_APP_FW_MAJOR_VERSION=" "$version_conf" 2>/dev/null | cut -d'=' -f2 || true)
        VERSION_MINOR=$(grep -E "^CONFIG_APP_FW_MINOR_VERSION=" "$version_conf" 2>/dev/null | cut -d'=' -f2 || true)
        VERSION_BUILD=$(grep -E "^CONFIG_APP_FW_BUILD_VERSION=" "$version_conf" 2>/dev/null | cut -d'=' -f2 || true)

        # Try legacy format if not found
        [ -z "$VERSION_MAJOR" ] && VERSION_MAJOR=$(grep -E "^CONFIG_FW_INFO_VERSION_MAJOR=" "$version_conf" 2>/dev/null | cut -d'=' -f2 || true)
        [ -z "$VERSION_MINOR" ] && VERSION_MINOR=$(grep -E "^CONFIG_FW_INFO_VERSION_MINOR=" "$version_conf" 2>/dev/null | cut -d'=' -f2 || true)
        [ -z "$VERSION_BUILD" ] && VERSION_BUILD=$(grep -E "^CONFIG_FW_INFO_VERSION_BUILD=" "$version_conf" 2>/dev/null | cut -d'=' -f2 || true)
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
            VERSION_BUILD=$(grep -E "^#define BUILD_NUM" "$vh_file" 2>/dev/null | awk '{print $3}' || true)
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

        # Try legacy format first (|| true: grep returns 1 when key is absent under pipefail)
        version_major=$(grep -E "^CONFIG_FW_INFO_VERSION_MAJOR=" "$version_conf" 2>/dev/null | cut -d'=' -f2 || true)
        version_minor=$(grep -E "^CONFIG_FW_INFO_VERSION_MINOR=" "$version_conf" 2>/dev/null | cut -d'=' -f2 || true)
        version_build=$(grep -E "^CONFIG_FW_INFO_VERSION_BUILD=" "$version_conf" 2>/dev/null | cut -d'=' -f2 || true)

        # If not found, try current alpha_fw format
        if [ -z "$version_major" ]; then
            version_major=$(grep -E "^CONFIG_APP_FW_MAJOR_VERSION=" "$version_conf" 2>/dev/null | cut -d'=' -f2 || true)
        fi
        if [ -z "$version_minor" ]; then
            version_minor=$(grep -E "^CONFIG_APP_FW_MINOR_VERSION=" "$version_conf" 2>/dev/null | cut -d'=' -f2 || true)
        fi
        if [ -z "$version_build" ]; then
            version_build=$(grep -E "^CONFIG_APP_FW_BUILD_VERSION=" "$version_conf" 2>/dev/null | cut -d'=' -f2 || true)
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
            h_build_num=$(grep -E "^#define BUILD_NUM" "$version_device_h" 2>/dev/null | awk '{print $3}' || true)
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

    # Determine CFW flags and track string (needed for ALL artifact naming)
    # - Track: 0=Bench (for CI/validation builds)
    # - Mfg: 1 if label contains "mfg"
    # - Debug: 1 if VARIANT=debug
    #
    # IMPORTANT: CoreCloud FUOTA strips the 'D' (debug) flag when matching
    # device firmware to plan targets. MFG builds MUST use variant=release
    # (no debug flag) to produce BM track strings. If variant=debug is used,
    # the device reports BMD but CoreCloud plan targets are BM → no match →
    # FUOTA delivery silently fails (0 pages sent). Verified 2026-03-18.
    local cfw_track=0
    local cfw_mfg=0
    local cfw_debug=0

    if [[ "$label" == *"mfg"* ]]; then
        cfw_mfg=1
    fi
    if [[ "$variant_folder" == "debug" ]]; then
        cfw_debug=1
    fi

    # Build track string for filenames: B=Bench, M=Mfg, D=Debug
    local track_str="B"
    [ $cfw_mfg -eq 1 ] && track_str="${track_str}M"
    [ $cfw_debug -eq 1 ] && track_str="${track_str}D"

    # Name hex files: {appId}.{version}-{track}.hex (e.g. 109.0.8.4-BD.hex)
    local app_hex_name="109.${version_major}.${version_minor}.${version_build}-${track_str}.hex"
    local comms_hex_name="108.${version_major}.${version_minor}.${version_build}-${track_str}.hex"
    if [ -f "$app_hex" ]; then
        cp "$app_hex" "$out_dir/${app_hex_name}"
        echo -e "  ${GREEN}${app_hex_name}${NC}"
    fi
    if [ -f "$comms_hex" ]; then
        cp "$comms_hex" "$out_dir/${comms_hex_name}"
        echo -e "  ${GREEN}${comms_hex_name}${NC}"
    fi
    if [ -n "$dfu_zip" ] && [ -f "$dfu_zip" ]; then
        cp "$dfu_zip" "$out_dir/dfu_application.zip"
        echo -e "  ${GREEN}dfu_application.zip${NC}"
    fi

    echo -e "  ${CYAN}Version: ${version_string}${NC}"
    echo -e "  ${CYAN}Variant: ${variant_folder} (${track_str})${NC}"

    # Generate CFW files from encrypted signed bins
    echo -e "${CYAN}Generating CFW files...${NC}"

    # App processor CFW (app_id=109 for nRF52840)
    # Sysbuild outputs to build/<project_name>/zephyr/ — find the actual bin
    local app_bin=""
    for candidate in \
        "${fw_dir}/build/alpha_fw/zephyr/zephyr.signed.encrypted.bin" \
        "${fw_dir}/build/alpha_mfg_fw/zephyr/zephyr.signed.encrypted.bin" \
        "${fw_dir}/build/repo/zephyr/zephyr.signed.encrypted.bin" \
        $(find "${fw_dir}/build" -path "*/nrf52840*/zephyr/zephyr.signed.encrypted.bin" 2>/dev/null | head -1); do
        if [ -f "$candidate" ]; then
            app_bin="$candidate"
            break
        fi
    done
    if [ -n "$app_bin" ] && [ -f "$app_bin" ]; then
        generate_cfw "$app_bin" 109 "$version_major" "$version_minor" "$version_build" \
            $cfw_track $cfw_mfg $cfw_debug "$out_dir/109.${version_major}.${version_minor}.${version_build}-${track_str}.cfw"
    fi

    # Comms processor CFW (app_id=108 for nRF9151)
    local comms_bin="${comms_dir}/build/comm_coproc_mfg/zephyr/zephyr.signed.encrypted.bin"
    if [ -f "$comms_bin" ]; then
        generate_cfw "$comms_bin" 108 "$version_major" "$version_minor" "$version_build" \
            $cfw_track $cfw_mfg $cfw_debug "$out_dir/108.${version_major}.${version_minor}.${version_build}-${track_str}.cfw"
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
        COMMS_EXTRA_CONF="${FW_DIR}/version.conf;${FW_DIR}/default_personalization.conf"
        if [ -f "${COMM_DIR}/dev.conf" ]; then
            COMMS_EXTRA_CONF="${COMMS_EXTRA_CONF};${COMM_DIR}/dev.conf"
        else
            echo -e "${YELLOW}WARNING: ${COMM_DIR}/dev.conf not found — shell/logging from val_server.conf fallback${NC}"
        fi
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

    # --- Fix key paths in sysbuild configs (CI clones to different path) ---
    fix_sysbuild_key_path "${FW_DIR}/sysbuild.conf" "${FW_DIR}"

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

    # Rebuild with FIPS hash added to EXTRA_CONF_FILE
    local COMMS_FIPS_CONF="${COMMS_EXTRA_CONF};${COMM_DIR}/fips.conf"
    west build \
        -d "${COMM_DIR}/build" \
        -b "${BOARD}/${COMM_SOC}/ns" \
        --sysbuild "${COMM_DIR}" \
        -- \
        -DBOARD_ROOT="${FW_DIR}/ck_boards/current/" \
        "-DEXTRA_CONF_FILE=${COMMS_FIPS_CONF}" \
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
    # The submodule's boards/alpha_b0_nrf52840.overlay has TWO things:
    #   1. I2C sensor definitions (pah8151, mlx90614, bme280, lp5814) — needed always
    #   2. UART TX/RX pin swap — needed for REV 1.1, BREAKS REV 1.2
    # Zephyr auto-detects overlays in boards/ by board name, so we MUST explicitly
    # set DTC_OVERLAY_FILE to suppress auto-detection and control what gets applied.
    local APP_DTS_OVERLAY=""
    local COMMS_DTS_OVERLAY=""
    if [[ "$MTIB_REV" == "1.1" ]]; then
        # REV 1.1: use submodule overlay as-is (sensors + UART pin swap)
        APP_DTS_OVERLAY="-DDTC_OVERLAY_FILE=${FW_DIR}/boards/alpha_b0_nrf52840.overlay"
        COMMS_DTS_OVERLAY="-DDTC_OVERLAY_FILE=${FW_DIR}/boards/alpha_b0_nrf9151_ns.overlay"
    else
        # REV 1.2: use sensors-only overlay (no UART pin swap).
        # This suppresses Zephyr auto-detection of the submodule overlay.
        APP_DTS_OVERLAY="-DDTC_OVERLAY_FILE=${OVERLAYS_DIR}/mfg_app_rev12.overlay"
        COMMS_DTS_OVERLAY=""
    fi

    # --- Resolve extra configs for comms ---
    # dev.conf enables shell + logging for MFG firmware. Must use EXTRA_CONF_FILE
    # with absolute path because -DOVERLAY_CONFIG doesn't propagate through sysbuild.
    local MFG_COMMS_EXTRA_CONF="${FW_DIR}/version.conf;${FW_DIR}/default_personalization.conf"
    if [ -f "${COMM_DIR}/dev.conf" ]; then
        MFG_COMMS_EXTRA_CONF="${MFG_COMMS_EXTRA_CONF};${COMM_DIR}/dev.conf"
    else
        echo -e "${YELLOW}WARNING: ${COMM_DIR}/dev.conf not found — shell/logging configs from val_server.conf fallback${NC}"
    fi
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

    # --- Fix key paths in sysbuild configs (CI clones to different path) ---
    fix_sysbuild_key_path "${FW_DIR}/sysbuild.conf" "${FW_DIR}"

    # --- Remove auto-detected board overlay for REV 1.2 ---
    # Zephyr/sysbuild auto-detects boards/<board>.overlay even when DTC_OVERLAY_FILE
    # is explicitly set. The submodule's overlay swaps UART TX/RX pins for REV 1.1,
    # which breaks REV 1.2 UART communication (especially after FUOTA).
    # Remove it so only the explicit mfg_app_rev12.overlay is applied.
    if [[ "$MTIB_REV" != "1.1" ]]; then
        local auto_overlay="${FW_DIR}/boards/alpha_b0_nrf52840.overlay"
        if [ -f "$auto_overlay" ]; then
            echo -e "${CYAN}Removing auto-detected overlay (REV 1.2 build): ${auto_overlay}${NC}"
            rm -f "$auto_overlay"
        fi
    fi

    # --- Parallel build: APP (nRF52840) + COMMS first pass (nRF9151) ---
    # These are fully independent — different source trees, build dirs, and boards.
    # Run them in parallel, then do post-processing (mergehex + FIPS) after both finish.
    fix_sysbuild_key_path "${COMM_DIR}/sysbuild.conf" "${FW_DIR}"
    echo "# FIPS hash - placeholder for first build" > "${COMM_DIR}/fips.conf"

    local APP_LOG="${FW_DIR}/build_app.log"
    local COMMS_LOG="${COMM_DIR}/build_comms.log"

    echo -e "\n${CYAN}[1/3] Building APP + COMMS in parallel${NC}"
    echo -e "${CYAN}  APP:   nRF52840 (${MFG_BOARD})${NC}"
    echo -e "${CYAN}  COMMS: ${MFG_SOC} (${MFG_BOARD})${NC}"

    # APP build (background) — tee captures log file, sed adds prefix for real-time streaming
    (
        west build ${PRISTINE:---pristine} \
            -d "${FW_DIR}/build" \
            -b "${MFG_BOARD}/nrf52840" \
            --sysbuild "${FW_DIR}" \
            -- \
            -DBOARD_ROOT="${FW_DIR}/ck_boards/current/" \
            -DEXTRA_CONF_FILE="${FW_DIR}/version.conf" \
            ${APP_DTS_OVERLAY} 2>&1 | tee "$APP_LOG" | sed -u 's/^/[APP] /'
    ) &
    local APP_PID=$!

    # COMMS first build (background) — tee captures log file, sed adds prefix for real-time streaming
    (
        west build --pristine \
            -d "${COMM_DIR}/build" \
            -b "${MFG_BOARD}/${MFG_SOC}/ns" \
            --sysbuild "${COMM_DIR}" \
            -- \
            -DBOARD_ROOT="${FW_DIR}/ck_boards/current/" \
            "-DEXTRA_CONF_FILE=${MFG_COMMS_EXTRA_CONF}" \
            ${COMMS_DTS_OVERLAY} 2>&1 | tee "$COMMS_LOG" | sed -u 's/^/[COMMS] /'
    ) &
    local COMMS_PID=$!

    echo -e "${CYAN}  APP PID:   ${APP_PID}${NC}"
    echo -e "${CYAN}  COMMS PID: ${COMMS_PID}${NC}"

    # Wait for both — pipefail ensures we catch west build failures through the tee|sed pipe
    local APP_RC=0 COMMS_RC=0
    wait $APP_PID || APP_RC=$?
    wait $COMMS_PID || COMMS_RC=$?

    if [ $APP_RC -ne 0 ]; then
        echo -e "${RED}APP build failed (exit $APP_RC)${NC}"
        exit 1
    fi
    if [ $COMMS_RC -ne 0 ]; then
        echo -e "${RED}COMMS first-pass build failed (exit $COMMS_RC)${NC}"
        exit 1
    fi
    echo -e "${GREEN}Both parallel builds succeeded${NC}"

    # --- Post-processing (can also run in parallel) ---
    echo -e "\n${CYAN}[2/3] Merging VSM PSP hex${NC}"
    mergehex -m \
        "${FW_DIR}/build/merged.hex" \
        "${FW_DIR}/vsm_drv/src/corekinect/module/vsm/threads/vitals/lib/bin/psp.hex" \
        -o "${FW_DIR}/build/merged.hex"

    # --- FIPS hash recalculation + final rebuild ---
    echo -e "\n${CYAN}[3/3] FIPS hash recalculation + final COMMS rebuild${NC}"
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

    # Rebuild with FIPS hash — add fips.conf to EXTRA_CONF_FILE for the final build
    local MFG_COMMS_FIPS_CONF="${MFG_COMMS_EXTRA_CONF};${COMM_DIR}/fips.conf"
    west build \
        -d "${COMM_DIR}/build" \
        -b "${MFG_BOARD}/${MFG_SOC}/ns" \
        --sysbuild "${COMM_DIR}" \
        -- \
        -DBOARD_ROOT="${FW_DIR}/ck_boards/current/" \
        "-DEXTRA_CONF_FILE=${MFG_COMMS_FIPS_CONF}" \
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
