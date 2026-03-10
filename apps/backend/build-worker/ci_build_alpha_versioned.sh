#!/bin/bash
# ============================================================================
# CI Build Script for Alpha Firmware - Versioned FUOTA Builds
# ============================================================================
# Produces versioned artifacts ready for FUOTA delivery:
#   {version}/
#     commit.log
#     debug/
#       app/
#         alpha_app_{build}.hex
#         alpha_app_{build}.hex.sha1
#         signed.encrypted/...
#       comm_coproc_mfg/...
#       {appId}.{major}.{minor}.{build}-{track}.cfw
#     release/  (non-debug variant)
#       ...
#
# For FUOTA, builds TWO consecutive versions (same code, bumped build number).
#
# Environment variables:
#   REPO_DIR      - Path to cloned firmware repo
#   OUTPUT_DIR    - Path to output artifacts
#   BOARD         - Board name (alpha_b0)
#   VARIANT       - Build variant (debug, release)
#   MTIB_REV      - MTIB revision (1.2)
#   BUILD_PAIR    - If "true", build 2 consecutive versions for FUOTA
# ============================================================================

set -e
CYAN='\033[0;36m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${CYAN}=== $* ===${NC}"; }
warn() { echo -e "${YELLOW}[WARN] $*${NC}"; }
err()  { echo -e "${RED}[ERROR] $*${NC}" >&2; }

# ─── Configuration ──────────────────────────────────────────────────────────

REPO_DIR="${REPO_DIR:-$(pwd)}"
OUTPUT_DIR="${OUTPUT_DIR:-${REPO_DIR}/artifacts}"
BOARD="${BOARD:-alpha_b0}"
VARIANT="${VARIANT:-debug}"
MTIB_REV="${MTIB_REV:-1.2}"
BUILD_PAIR="${BUILD_PAIR:-false}"

# Alpha App IDs (from corekinect.firmware.cfw)
APPID_COMMS=108    # nRF9151 comms coprocessor
APPID_APP=109      # nRF52840 application processor

# Release track (0=Bench, 1=Engineering, 2=Production)
# Alpha firmware uses BOOTLOADER_ID=0 (Bench) for all variants
RELEASE_TRACK=0

# Determine comm processor SOC based on board
case $BOARD in
    alpha_a0) COMM_SOC="nrf9160" ;;
    alpha_b0) COMM_SOC="nrf9151" ;;
    *) err "Unsupported board: ${BOARD}"; exit 1 ;;
esac

# Debug flag for CFW - production firmware (NOT manufacturing)
if [ "$VARIANT" = "debug" ]; then
    DEBUG_FLAG=1
    VARIANT_DIR="debug"
    TRACK_SUFFIX="BD"  # Bench + Debug
else
    DEBUG_FLAG=0
    VARIANT_DIR="release"
    TRACK_SUFFIX="B"   # Bench only
fi

# Manufacturing flag - alpha_fw is PRODUCTION firmware (not manufacturing)
# The "M" flag is only for alpha_mfg_fw builds
MFG_FLAG=0

mkdir -p "${OUTPUT_DIR}"

# ─── Extract Version from Firmware ──────────────────────────────────────────

extract_version() {
    # Try to read from version.conf first (Kconfig options)
    local version_conf="${REPO_DIR}/version.conf"
    if [ -f "$version_conf" ]; then
        MAJOR=$(grep "CONFIG_APP_FW_MAJOR_VERSION=" "$version_conf" | cut -d= -f2 | tr -d '\r')
        MINOR=$(grep "CONFIG_APP_FW_MINOR_VERSION=" "$version_conf" | cut -d= -f2 | tr -d '\r')
    fi

    # If not found in version.conf, check VersionDevice.h
    if [ -z "$MAJOR" ] || [ -z "$MINOR" ]; then
        local version_file=$(find "${REPO_DIR}" -name "VersionDevice.h" -type f | head -1)
        if [ -f "$version_file" ]; then
            MAJOR=${MAJOR:-$(grep -E "CONFIG_APP_FW_MAJOR_VERSION|MAJOR_RELEASE_NUM" "$version_file" | grep -oE '[0-9]+' | head -1)}
            MINOR=${MINOR:-$(grep -E "CONFIG_APP_FW_MINOR_VERSION|MINOR_RELEASE_NUM" "$version_file" | grep -oE '[0-9]+' | head -1)}
        fi
    fi

    # Get BUILD_NUM from VersionDevice.h (not a Kconfig option)
    local version_file=$(find "${REPO_DIR}" -name "VersionDevice.h" -type f | head -1)
    if [ -f "$version_file" ]; then
        BUILD=$(grep "#define BUILD_NUM" "$version_file" | grep -oE '[0-9]+' | head -1)
    fi

    # Defaults if still not found
    MAJOR=${MAJOR:-0}
    MINOR=${MINOR:-8}
    BUILD=${BUILD:-0}

    # Handle hex values
    MAJOR=$((MAJOR))
    MINOR=$((MINOR))
    BUILD=$((BUILD))

    log "Extracted version: ${MAJOR}.${MINOR}.${BUILD}"
}

# ─── Generate Encryption Keys ───────────────────────────────────────────────

generate_encryption_keys() {
    log "Generating dev encryption keys..."
    if [ ! -f "${REPO_DIR}/encryption_key.pem" ]; then
        echo "${CYAN}Generating dev encryption key...${NC}"
        openssl ecparam -name prime256v1 -genkey -noout -out "${REPO_DIR}/encryption_key.pem"
    fi
    if [ ! -f "${REPO_DIR}/comms_encryption_key.pem" ]; then
        echo "${CYAN}Generating dev comms encryption key...${NC}"
        openssl ecparam -name prime256v1 -genkey -noout -out "${REPO_DIR}/comms_encryption_key.pem"
    fi
}

# ─── Fix Hardcoded Paths ────────────────────────────────────────────────────

fix_paths() {
    log "Fixing hardcoded paths..."
    for conf in $(find "${REPO_DIR}" -name "sysbuild.conf" -type f 2>/dev/null); do
        sed -i "s|/workspaces/alpha_fw|${REPO_DIR}|g" "$conf" 2>/dev/null || true
        sed -i "s|/workspaces/comm_coproc_mfg|${REPO_DIR}/comm_coproc_mfg|g" "$conf" 2>/dev/null || true
    done
}

# ─── Build Application (nRF52840) ───────────────────────────────────────────

inject_build_number() {
    local build_num=$1
    log "Injecting BUILD_NUM=${build_num} into VersionDevice.h files"

    # Find and update all VersionDevice.h files
    for vdh in $(find "${REPO_DIR}" -name "VersionDevice.h" -type f 2>/dev/null); do
        if grep -q "#define BUILD_NUM" "$vdh"; then
            sed -i "s/#define BUILD_NUM.*/#define BUILD_NUM         ${build_num}/" "$vdh"
            echo "  Updated: $vdh"
        fi
    done
}

build_app() {
    local build_num=$1
    local app_start=$(date +%s)
    log "Building Application (nRF52840) - build ${build_num}"

    # Inject build number by modifying VersionDevice.h
    inject_build_number $build_num

    # Build and capture output for warnings/errors
    local log_file="${OUTPUT_DIR}/app_build.log"
    west build --pristine -d ${REPO_DIR}/build -b ${BOARD}/nrf52840 --sysbuild ${REPO_DIR} -- \
        -DBOARD_ROOT=${REPO_DIR}/ck_boards/current/ \
        -DEXTRA_CONF_FILE="${REPO_DIR}/version.conf" 2>&1 | tee "$log_file"

    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        err "Application build failed"
        BUILD_ERRORS+=("Application build failed")
        exit 1
    fi

    # Parse warnings/errors from log
    while IFS= read -r line; do
        if echo "$line" | grep -qiE "warning:"; then
            BUILD_WARNINGS+=("$(echo "$line" | head -c 200)")
        fi
    done < "$log_file"

    # Merge PSP hex if available
    if [ -f ${REPO_DIR}/vsm_drv/src/corekinect/module/vsm/threads/vitals/lib/bin/psp.hex ]; then
        echo "${CYAN}Merging PSP hex...${NC}"
        mergehex -m ${REPO_DIR}/build/merged.hex ${REPO_DIR}/vsm_drv/src/corekinect/module/vsm/threads/vitals/lib/bin/psp.hex -o ${REPO_DIR}/build/merged.hex
    fi

    APP_BUILD_TIME=$(($(date +%s) - app_start))
    log "App build completed in ${APP_BUILD_TIME}s"
}

# ─── Build Comms Processor (nRF9151) ────────────────────────────────────────

build_comms() {
    local build_num=$1
    local comms_start=$(date +%s)
    log "Building Communication Coprocessor (${COMM_SOC}) - build ${build_num}"

    COMM_DIR="${REPO_DIR}/comm_coproc_mfg"

    # Copy encryption key to comm_coproc_mfg where sysbuild.conf expects it
    # (handles the case where sysbuild.conf has relative or subdir path)
    if [ -f "${REPO_DIR}/comms_encryption_key.pem" ]; then
        cp "${REPO_DIR}/comms_encryption_key.pem" "${COMM_DIR}/comms_encryption_key.pem"
    fi

    # Fix encryption key path in sysbuild.conf - handle all variants
    # The path might be absolute with any base dir, or relative
    sed -i "s|SB_CONFIG_BOOT_ENCRYPTION_KEY_FILE=.*|SB_CONFIG_BOOT_ENCRYPTION_KEY_FILE=\"${COMM_DIR}/comms_encryption_key.pem\"|g" ${COMM_DIR}/sysbuild.conf

    # Initial build (for FIPS hash calculation)
    echo "# FIPS hash - placeholder for first build" > ${COMM_DIR}/fips.conf

    local log_file="${OUTPUT_DIR}/comms_build.log"
    west build --pristine -d ${COMM_DIR}/build -b ${BOARD}/${COMM_SOC}/ns --sysbuild ${COMM_DIR} -- \
        -DBOARD_ROOT=${REPO_DIR}/ck_boards/current/ \
        "-DEXTRA_CONF_FILE=${REPO_DIR}/version.conf;${REPO_DIR}/default_personalization.conf" 2>&1 | tee "$log_file"

    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        err "Communication coprocessor initial build failed"
        BUILD_ERRORS+=("Communication coprocessor initial build failed")
        exit 1
    fi

    # Calculate FIPS hash and rebuild
    log "Calculating FIPS hash and rebuilding..."
    python3 ${COMM_DIR}/wolfssl/scripts/gen_fips_hash.py ${COMM_DIR}/build/merged.hex ${COMM_DIR}/build/comm_coproc_mfg/zephyr/zephyr.map > ${COMM_DIR}/fips.conf

    west build -d ${COMM_DIR}/build -b ${BOARD}/${COMM_SOC}/ns --sysbuild ${COMM_DIR} -- \
        -DBOARD_ROOT=${REPO_DIR}/ck_boards/current/ \
        -DOVERLAY_CONFIG=fips.conf \
        "-DEXTRA_CONF_FILE=${REPO_DIR}/version.conf;${REPO_DIR}/default_personalization.conf" 2>&1 | tee -a "$log_file"

    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        err "FIPS rebuild failed"
        BUILD_ERRORS+=("FIPS rebuild failed")
        exit 1
    fi

    # Parse warnings from log
    while IFS= read -r line; do
        if echo "$line" | grep -qiE "warning:"; then
            BUILD_WARNINGS+=("$(echo "$line" | head -c 200)")
        fi
    done < "$log_file"

    COMMS_BUILD_TIME=$(($(date +%s) - comms_start))
    log "Comms build completed in ${COMMS_BUILD_TIME}s"
}

# ─── Generate CFW File ──────────────────────────────────────────────────────

generate_cfw() {
    local signed_bin=$1
    local app_id=$2
    local major=$3
    local minor=$4
    local build=$5
    local output_dir=$6

    local track_char="B"  # Bench
    local flags=""
    if [ "$MFG_FLAG" = "1" ]; then flags="${flags}M"; fi
    if [ "$DEBUG_FLAG" = "1" ]; then flags="${flags}D"; fi

    local cfw_name="${app_id}.${major}.${minor}.${build}-${track_char}${flags}.cfw"
    local cfw_path="${output_dir}/${cfw_name}"

    log "Generating CFW: ${cfw_name}"

    # Generate CFW inline (no external dependencies)
    # Note: unquoted heredoc allows shell variable expansion
    python3 <<PYCFW
import struct
import time
from pathlib import Path

# CFW v2 format: 23-byte header + encrypted binary
# Header: >HQHBHHHI (uint16, uint64, uint16, uint8, uint16, uint16, uint16, uint32)

def encode_flags(track=0, mfg=False, debug=False):
    flags = (track & 0x03) << 1
    if mfg: flags |= 0x01
    if debug: flags |= 0x08
    return flags

def generate_cfw(bin_path, app_id, major, minor, build, track=0, mfg=False, debug=False):
    image = Path(bin_path).read_bytes()
    header = struct.pack(">HQHBHHHI", 2, int(time.time()), app_id, encode_flags(track, mfg, debug), major, minor, build, len(image))
    return header + image

try:
    cfw = generate_cfw("${signed_bin}", ${app_id}, ${major}, ${minor}, ${build}, 0, ${MFG_FLAG}==1, ${DEBUG_FLAG}==1)
    Path("${cfw_path}").write_bytes(cfw)
    print(f"Generated: ${cfw_path} ({len(cfw)} bytes)")
except Exception as e:
    print(f"CFW generation failed: {e}")
PYCFW
}

# ─── Collect Artifacts for One Build ────────────────────────────────────────

collect_artifacts() {
    local build_num=$1
    local version_str="${MAJOR}.${MINOR}.${build_num}"
    local version_dir="${OUTPUT_DIR}/${version_str}"
    local variant_dir="${version_dir}/${VARIANT_DIR}"

    mkdir -p "${variant_dir}/app"
    mkdir -p "${variant_dir}/app/signed.encrypted"
    mkdir -p "${variant_dir}/comm_coproc_mfg"
    mkdir -p "${variant_dir}/comm_coproc_mfg/signed.encrypted"

    log "Collecting artifacts for version ${version_str}"

    COMM_DIR="${REPO_DIR}/comm_coproc_mfg"

    # ─── App artifacts ───
    local app_hex_name="alpha_app_${build_num}.hex"
    local app_signed_name="alpha_app_${build_num}.signed.encrypted.hex"

    # Raw hex
    if [ -f "${REPO_DIR}/build/merged.hex" ]; then
        cp "${REPO_DIR}/build/merged.hex" "${variant_dir}/app/${app_hex_name}"
        sha1sum "${variant_dir}/app/${app_hex_name}" | awk '{print $1}' > "${variant_dir}/app/${app_hex_name}.sha1"
    fi

    # Signed+encrypted bin (for CFW)
    # Note: App processor build outputs to build/repo/zephyr/, not build/alpha_fw/zephyr/
    local app_signed_bin="${REPO_DIR}/build/repo/zephyr/zephyr.signed.encrypted.bin"
    if [ -f "$app_signed_bin" ]; then
        # Convert bin to hex for archival
        cp "${REPO_DIR}/build/repo/zephyr/zephyr.signed.encrypted.hex" "${variant_dir}/app/signed.encrypted/${app_signed_name}" 2>/dev/null || true
        if [ -f "${variant_dir}/app/signed.encrypted/${app_signed_name}" ]; then
            sha1sum "${variant_dir}/app/signed.encrypted/${app_signed_name}" | awk '{print $1}' > "${variant_dir}/app/signed.encrypted/${app_signed_name}.sha1"
        fi

        # Generate CFW for app processor
        generate_cfw "$app_signed_bin" $APPID_APP $MAJOR $MINOR $build_num "$variant_dir"
    fi

    # ─── Comms artifacts ───
    local comm_hex_name="alpha_comm_${build_num}.hex"
    local comm_signed_name="alpha_comm_${build_num}.signed.encrypted.hex"

    # Raw hex
    if [ -f "${COMM_DIR}/build/merged.hex" ]; then
        cp "${COMM_DIR}/build/merged.hex" "${variant_dir}/comm_coproc_mfg/${comm_hex_name}"
        sha1sum "${variant_dir}/comm_coproc_mfg/${comm_hex_name}" | awk '{print $1}' > "${variant_dir}/comm_coproc_mfg/${comm_hex_name}.sha1"
    fi

    # Signed+encrypted
    local comm_signed_bin="${COMM_DIR}/build/comm_coproc_mfg/zephyr/zephyr.signed.encrypted.bin"
    if [ -f "$comm_signed_bin" ]; then
        cp "${COMM_DIR}/build/comm_coproc_mfg/zephyr/zephyr.signed.encrypted.hex" "${variant_dir}/comm_coproc_mfg/signed.encrypted/${comm_signed_name}" 2>/dev/null || true
        if [ -f "${variant_dir}/comm_coproc_mfg/signed.encrypted/${comm_signed_name}" ]; then
            sha1sum "${variant_dir}/comm_coproc_mfg/signed.encrypted/${comm_signed_name}" | awk '{print $1}' > "${variant_dir}/comm_coproc_mfg/signed.encrypted/${comm_signed_name}.sha1"
        fi

        # Generate CFW for comms processor
        generate_cfw "$comm_signed_bin" $APPID_COMMS $MAJOR $MINOR $build_num "$variant_dir"
    fi

    # ─── Commit log ───
    git -C "${REPO_DIR}" log -1 --format="commit %H%nAuthor: %an <%ae>%nDate:   %ad%n%n    %s" > "${version_dir}/commit.log" 2>/dev/null || echo "No git info available" > "${version_dir}/commit.log"

    # ─── Build metadata JSON ───
    local total_duration=$(($(date +%s) - BUILD_START_TIME))
    generate_build_json "$variant_dir" "$build_num" "$total_duration"

    echo "Artifacts collected in: ${version_dir}"
}

# ─── Main Build Flow ────────────────────────────────────────────────────────

# ─── Build Metrics and Logging ──────────────────────────────────────────────

BUILD_START_TIME=0
BUILD_WARNINGS=()
BUILD_ERRORS=()
APP_BUILD_TIME=0
COMMS_BUILD_TIME=0

start_timer() {
    BUILD_START_TIME=$(date +%s)
}

capture_build_output() {
    local name=$1
    local log_file=$2
    local start_time=$(date +%s)

    # Run build and capture output
    local exit_code=0

    # Extract warnings and errors from log
    if [ -f "$log_file" ]; then
        while IFS= read -r line; do
            if echo "$line" | grep -qE "warning:|Warning:"; then
                BUILD_WARNINGS+=("$line")
            fi
            if echo "$line" | grep -qE "error:|Error:|ERROR"; then
                BUILD_ERRORS+=("$line")
            fi
        done < "$log_file"
    fi

    local end_time=$(date +%s)
    echo $((end_time - start_time))
}

generate_build_json() {
    local version_dir=$1
    local build_num=$2
    local total_duration=$3

    local json_file="${version_dir}/build.json"
    local warning_count=${#BUILD_WARNINGS[@]}
    local error_count=${#BUILD_ERRORS[@]}

    # Get memory info
    local peak_memory=$(cat /proc/meminfo | grep MemTotal | awk '{print $2}')

    cat > "$json_file" << EOF
{
  "version": "${MAJOR}.${MINOR}.${build_num}",
  "board": "${BOARD}",
  "variant": "${VARIANT}",
  "mtibRev": "${MTIB_REV}",
  "commitSha": "$(git -C ${REPO_DIR} rev-parse HEAD 2>/dev/null || echo 'unknown')",
  "branch": "$(git -C ${REPO_DIR} rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')",
  "buildTimestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "metrics": {
    "totalDurationSeconds": ${total_duration},
    "appBuildDurationSeconds": ${APP_BUILD_TIME},
    "commsBuildDurationSeconds": ${COMMS_BUILD_TIME},
    "warningCount": ${warning_count},
    "errorCount": ${error_count}
  },
  "artifacts": {
    "app": {
      "hex": "app/alpha_app_${build_num}.hex",
      "signedEncrypted": "app/signed.encrypted/alpha_app_${build_num}.signed.encrypted.hex",
      "cfw": "${APPID_APP}.${MAJOR}.${MINOR}.${build_num}-${TRACK_SUFFIX}.cfw"
    },
    "comms": {
      "hex": "comm_coproc_mfg/alpha_comm_${build_num}.hex",
      "signedEncrypted": "comm_coproc_mfg/signed.encrypted/alpha_comm_${build_num}.signed.encrypted.hex",
      "cfw": "${APPID_COMMS}.${MAJOR}.${MINOR}.${build_num}-${TRACK_SUFFIX}.cfw"
    }
  },
  "warnings": [
$(printf '    "%s"' "${BUILD_WARNINGS[0]:-}" | sed 's/"/\\"/g; s/\\/\\\\/g')
$(for ((i=1; i<${#BUILD_WARNINGS[@]}; i++)); do
    printf ',\n    "%s"' "${BUILD_WARNINGS[$i]}" | sed 's/"/\\"/g; s/\\/\\\\/g'
done)
  ],
  "errors": [
$(printf '    "%s"' "${BUILD_ERRORS[0]:-}" | sed 's/"/\\"/g; s/\\/\\\\/g')
$(for ((i=1; i<${#BUILD_ERRORS[@]}; i++)); do
    printf ',\n    "%s"' "${BUILD_ERRORS[$i]}" | sed 's/"/\\"/g; s/\\/\\\\/g'
done)
  ],
  "environment": {
    "ncsVersion": "${NCS_VERSION:-unknown}",
    "zephyrSdkVersion": "${ZEPHYR_SDK_VERSION:-unknown}",
    "hostname": "$(hostname)"
  }
}
EOF

    log "Generated build.json with ${warning_count} warnings, ${error_count} errors"
}

main() {
    start_timer

    log "Building Alpha firmware"
    echo "Board: ${BOARD}"
    echo "Variant: ${VARIANT}"
    echo "MTIB Rev: ${MTIB_REV}"
    echo "Build Pair: ${BUILD_PAIR}"
    echo "Repo Dir: ${REPO_DIR}"
    echo "Output Dir: ${OUTPUT_DIR}"
    echo ""

    # Extract version info
    extract_version

    # Setup
    generate_encryption_keys
    fix_paths

    if [ "$BUILD_PAIR" = "true" ]; then
        # Build TWO consecutive versions for FUOTA
        BUILD_NUM_1=$BUILD
        BUILD_NUM_2=$((BUILD + 1))

        log "Building version pair for FUOTA: ${MAJOR}.${MINOR}.${BUILD_NUM_1} and ${MAJOR}.${MINOR}.${BUILD_NUM_2}"

        # First build
        log "=== BUILD 1: version ${MAJOR}.${MINOR}.${BUILD_NUM_1} ==="
        build_app $BUILD_NUM_1
        build_comms $BUILD_NUM_1
        collect_artifacts $BUILD_NUM_1

        # Second build (bumped version)
        log "=== BUILD 2: version ${MAJOR}.${MINOR}.${BUILD_NUM_2} ==="
        build_app $BUILD_NUM_2
        build_comms $BUILD_NUM_2
        collect_artifacts $BUILD_NUM_2

    else
        # Single build
        log "Building single version: ${MAJOR}.${MINOR}.${BUILD}"
        build_app $BUILD
        build_comms $BUILD
        collect_artifacts $BUILD
    fi

    # Also copy flat artifacts for backward compatibility
    log "Copying flat artifacts for compatibility"
    mkdir -p "${OUTPUT_DIR}/flat"
    cp -v ${REPO_DIR}/build/merged.hex ${OUTPUT_DIR}/flat/app_merged.hex 2>/dev/null || true
    cp -v ${REPO_DIR}/build/alpha_fw/zephyr/zephyr.hex ${OUTPUT_DIR}/flat/app.hex 2>/dev/null || true
    cp -v ${REPO_DIR}/comm_coproc_mfg/build/merged.hex ${OUTPUT_DIR}/flat/comm_merged.hex 2>/dev/null || true
    cp -v ${REPO_DIR}/comm_coproc_mfg/build/comm_coproc_mfg/zephyr/zephyr.hex ${OUTPUT_DIR}/flat/comm.hex 2>/dev/null || true

    echo ""
    echo "${GREEN}=== BUILD COMPLETE ===${NC}"
    echo "Artifacts structure:"
    find "${OUTPUT_DIR}" -type f -name "*.hex" -o -name "*.cfw" -o -name "commit.log" | sort | head -50
}

main "$@"
