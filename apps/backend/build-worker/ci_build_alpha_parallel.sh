#!/bin/bash
# CI Build Script for Alpha firmware - PARALLEL VERSION
# Builds app (nRF52840) and comms (nRF9151) concurrently
#
# Environment variables:
#   REPO_DIR    - Path to cloned firmware repo
#   OUTPUT_DIR  - Path to output artifacts
#   BOARD       - Board name (alpha_a0, alpha_b0)
#   VARIANT     - Build variant (debug, release)
#   PARALLEL    - Set to 0 to disable parallel builds (default: 1)

set -e
CYAN='\033[0;36m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

REPO_DIR="${REPO_DIR:-$(pwd)}"
OUTPUT_DIR="${OUTPUT_DIR:-${REPO_DIR}/artifacts}"
BOARD="${BOARD:-alpha_b0}"
VARIANT="${VARIANT:-debug}"
PARALLEL="${PARALLEL:-1}"

# Determine comm processor SOC based on board
case $BOARD in
    alpha_a0) COMM_SOC="nrf9160" ;;
    alpha_b0) COMM_SOC="nrf9151" ;;
    *) echo -e "${RED}Unsupported board: ${BOARD}${NC}"; exit 1 ;;
esac

mkdir -p "${OUTPUT_DIR}"

# Initialize build logs (separate files for parallel builds)
BUILD_LOG="${OUTPUT_DIR}/build.log"
APP_LOG="${OUTPUT_DIR}/build_app.log"
COMM_LOG="${OUTPUT_DIR}/build_comm.log"
> "$BUILD_LOG"
> "$APP_LOG"
> "$COMM_LOG"

# Tee function to capture output while still printing
log_tee() {
    tee -a "$BUILD_LOG"
}

# Merge logs at the end
merge_logs() {
    echo "=== APP BUILD LOG ===" >> "$BUILD_LOG"
    cat "$APP_LOG" >> "$BUILD_LOG" 2>/dev/null || true
    echo "" >> "$BUILD_LOG"
    echo "=== COMMS BUILD LOG ===" >> "$BUILD_LOG"
    cat "$COMM_LOG" >> "$BUILD_LOG" 2>/dev/null || true
}

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  Alpha Firmware Build (${PARALLEL:+PARALLEL}${PARALLEL:-SEQUENTIAL})${NC}"
echo -e "${CYAN}========================================${NC}"
echo "Board: ${BOARD} (comm SOC: ${COMM_SOC})"
echo "REPO_DIR: ${REPO_DIR}"
echo "OUTPUT_DIR: ${OUTPUT_DIR}"
echo "VARIANT: ${VARIANT}"
START_TIME=$(date +%s)

# Generate dev encryption keys if not present
if [ ! -f "${REPO_DIR}/encryption_key.pem" ]; then
    echo -e "${CYAN}Generating dev encryption key...${NC}"
    openssl ecparam -name prime256v1 -genkey -noout -out "${REPO_DIR}/encryption_key.pem"
fi
if [ ! -f "${REPO_DIR}/comms_encryption_key.pem" ]; then
    echo -e "${CYAN}Generating dev comms encryption key...${NC}"
    openssl ecparam -name prime256v1 -genkey -noout -out "${REPO_DIR}/comms_encryption_key.pem"
fi

# Fix hardcoded paths in sysbuild.conf
for conf in $(find "${REPO_DIR}" -name "sysbuild.conf" -type f 2>/dev/null); do
    sed -i "s|/workspaces/alpha_fw|${REPO_DIR}|g" "$conf" 2>/dev/null || true
    sed -i "s|/workspaces/comm_coproc_mfg|${REPO_DIR}/comm_coproc_mfg|g" "$conf" 2>/dev/null || true
done

COMM_DIR="${REPO_DIR}/comm_coproc_mfg"

# Update encryption key paths for comms
sed -i "s|/workspaces/comm_coproc_mfg/comms_encryption_key.pem|${REPO_DIR}/comms_encryption_key.pem|g" ${COMM_DIR}/sysbuild.conf
sed -i "s|/workspaces/alpha_fw/comms_encryption_key.pem|${REPO_DIR}/comms_encryption_key.pem|g" ${COMM_DIR}/sysbuild.conf
echo "# FIPS hash - placeholder for first build" > ${COMM_DIR}/fips.conf

# Function to build application (nRF52840)
build_app() {
    local app_start=$(date +%s)
    echo -e "${CYAN}[APP] Building Application (nRF52840)...${NC}"

    # Use all available CPU cores for parallel compilation
    JOBS=$(nproc)
    west build --pristine -d ${REPO_DIR}/build -b ${BOARD}/nrf52840 --sysbuild ${REPO_DIR} -- \
        -DBOARD_ROOT=${REPO_DIR}/ck_boards/current/ \
        -DEXTRA_CONF_FILE=${REPO_DIR}/version.conf \
        -j${JOBS} 2>&1 | tee -a "$APP_LOG"

    local status=${PIPESTATUS[0]}
    local app_end=$(date +%s)
    local app_duration=$((app_end - app_start))

    if [ $status -ne 0 ]; then
        echo -e "${RED}[APP] Application build failed after ${app_duration}s${NC}"
        return 1
    fi

    # Merge PSP hex if available
    if [ -f ${REPO_DIR}/vsm_drv/src/corekinect/module/vsm/threads/vitals/lib/bin/psp.hex ]; then
        echo -e "${CYAN}[APP] Merging PSP hex...${NC}"
        mergehex -m ${REPO_DIR}/build/merged.hex ${REPO_DIR}/vsm_drv/src/corekinect/module/vsm/threads/vitals/lib/bin/psp.hex -o ${REPO_DIR}/build/merged.hex
    fi

    echo -e "${GREEN}[APP] Build completed in ${app_duration}s${NC}"
    return 0
}

# Function to build comms coprocessor first pass (nRF9151)
build_comms_pass1() {
    local comms_start=$(date +%s)
    echo -e "${CYAN}[COMMS] Building Communication Coprocessor (nRF9151) - Pass 1...${NC}"

    JOBS=$(nproc)
    west build --pristine -d ${COMM_DIR}/build -b ${BOARD}/${COMM_SOC}/ns --sysbuild ${COMM_DIR} -- \
        -DBOARD_ROOT=${REPO_DIR}/ck_boards/current/ \
        "-DEXTRA_CONF_FILE=${REPO_DIR}/version.conf;${REPO_DIR}/default_personalization.conf" \
        -j${JOBS} 2>&1 | tee -a "$COMM_LOG"

    local status=${PIPESTATUS[0]}
    local comms_end=$(date +%s)
    local comms_duration=$((comms_end - comms_start))

    if [ $status -ne 0 ]; then
        echo -e "${RED}[COMMS] Coprocessor build failed after ${comms_duration}s${NC}"
        return 1
    fi

    echo -e "${GREEN}[COMMS] Pass 1 completed in ${comms_duration}s${NC}"
    return 0
}

# Run builds
if [ "${PARALLEL}" = "1" ]; then
    echo -e "${YELLOW}>>> Running APP and COMMS builds in PARALLEL <<<${NC}"

    # Run both builds in background
    build_app &
    APP_PID=$!

    build_comms_pass1 &
    COMMS_PID=$!

    # Wait for both and capture exit codes
    APP_EXIT=0
    COMMS_EXIT=0
    wait $APP_PID || APP_EXIT=$?
    wait $COMMS_PID || COMMS_EXIT=$?

    if [ $APP_EXIT -ne 0 ]; then
        echo -e "${RED}Application build failed${NC}"
        exit 1
    fi
    if [ $COMMS_EXIT -ne 0 ]; then
        echo -e "${RED}Communication coprocessor build failed${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}>>> Running builds SEQUENTIALLY <<<${NC}"
    build_app || exit 1
    build_comms_pass1 || exit 1
fi

# FIPS hash rebuild (must be sequential, depends on first comms build)
echo -e "${CYAN}[COMMS] Calculating FIPS hash and rebuilding...${NC}"
FIPS_START=$(date +%s)

python3 ${COMM_DIR}/wolfssl/scripts/gen_fips_hash.py ${COMM_DIR}/build/merged.hex ${COMM_DIR}/build/comm_coproc_mfg/zephyr/zephyr.map > ${COMM_DIR}/fips.conf

JOBS=$(nproc)
west build -d ${COMM_DIR}/build -b ${BOARD}/${COMM_SOC}/ns --sysbuild ${COMM_DIR} -- \
    -DBOARD_ROOT=${REPO_DIR}/ck_boards/current/ \
    -DOVERLAY_CONFIG=fips.conf \
    "-DEXTRA_CONF_FILE=${REPO_DIR}/version.conf;${REPO_DIR}/default_personalization.conf" \
    -j${JOBS} 2>&1 | log_tee

if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo -e "${RED}[COMMS] FIPS rebuild failed${NC}"
    exit 1
fi

FIPS_END=$(date +%s)
FIPS_DURATION=$((FIPS_END - FIPS_START))
echo -e "${GREEN}[COMMS] FIPS rebuild completed in ${FIPS_DURATION}s${NC}"

# Copy artifacts to output
echo -e "${CYAN}=== Copying artifacts ===${NC}"
cp -v ${REPO_DIR}/build/merged.hex ${OUTPUT_DIR}/app_merged.hex 2>/dev/null || true
cp -v ${REPO_DIR}/build/alpha_fw/zephyr/zephyr.hex ${OUTPUT_DIR}/app.hex 2>/dev/null || true
cp -v ${COMM_DIR}/build/merged.hex ${OUTPUT_DIR}/comm_merged.hex 2>/dev/null || true
cp -v ${COMM_DIR}/build/comm_coproc_mfg/zephyr/zephyr.hex ${OUTPUT_DIR}/comm.hex 2>/dev/null || true

END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))
MINUTES=$((TOTAL_DURATION / 60))
SECONDS=$((TOTAL_DURATION % 60))

# Merge parallel build logs into main log
merge_logs

# === Generate build metrics JSON ===
echo -e "${CYAN}=== Generating build metrics ===${NC}"

# Extract memory usage from .map files
APP_MAP="${REPO_DIR}/build/alpha_fw/zephyr/zephyr.map"
COMM_MAP="${COMM_DIR}/build/comm_coproc_mfg/zephyr/zephyr.map"

get_memory_usage() {
    local map_file="$1"
    if [ -f "$map_file" ]; then
        # Extract memory section sizes from map file
        local text=$(grep -E "^\.text\s+" "$map_file" 2>/dev/null | awk '{print $3}' | head -1)
        local data=$(grep -E "^\.data\s+" "$map_file" 2>/dev/null | awk '{print $3}' | head -1)
        local bss=$(grep -E "^\.bss\s+" "$map_file" 2>/dev/null | awk '{print $3}' | head -1)
        echo "${text:-0},${data:-0},${bss:-0}"
    else
        echo "0,0,0"
    fi
}

APP_MEM=$(get_memory_usage "$APP_MAP")
COMM_MEM=$(get_memory_usage "$COMM_MAP")

# Extract warnings and errors from build output
BUILD_LOG="${OUTPUT_DIR}/build.log"
if [ -f "$BUILD_LOG" ]; then
    WARNINGS=$(grep -c -i "warning:" "$BUILD_LOG" 2>/dev/null || echo 0)
    ERRORS=$(grep -c -i "error:" "$BUILD_LOG" 2>/dev/null || echo 0)

    # Extract warning details (deduplicated)
    WARNINGS_JSON=$(grep -i "warning:" "$BUILD_LOG" 2>/dev/null | sort -u | head -100 | python3 -c "
import sys, json
lines = [line.strip() for line in sys.stdin]
print(json.dumps(lines))
" 2>/dev/null || echo "[]")

    # Extract error details
    ERRORS_JSON=$(grep -i "error:" "$BUILD_LOG" 2>/dev/null | sort -u | head -50 | python3 -c "
import sys, json
lines = [line.strip() for line in sys.stdin]
print(json.dumps(lines))
" 2>/dev/null || echo "[]")
else
    WARNINGS=0
    ERRORS=0
    WARNINGS_JSON="[]"
    ERRORS_JSON="[]"
fi

# Get artifact sizes
get_size() {
    local f="$1"
    if [ -f "$f" ]; then stat -c%s "$f" 2>/dev/null || echo 0; else echo 0; fi
}

APP_HEX_SIZE=$(get_size "${OUTPUT_DIR}/app_merged.hex")
COMM_HEX_SIZE=$(get_size "${OUTPUT_DIR}/comm_merged.hex")

# Extract version from version.conf
VERSION="unknown"
if [ -f "${REPO_DIR}/version.conf" ]; then
    VERSION=$(grep -E "^CONFIG_APP_VERSION=" "${REPO_DIR}/version.conf" | cut -d'"' -f2 || echo "unknown")
fi

# Get git info
GIT_SHA=$(cd "${REPO_DIR}" && git rev-parse HEAD 2>/dev/null || echo "unknown")
GIT_BRANCH=$(cd "${REPO_DIR}" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

# Generate metrics JSON
cat > "${OUTPUT_DIR}/build_metrics.json" << METRICS_EOF
{
  "buildInfo": {
    "board": "${BOARD}",
    "variant": "${VARIANT}",
    "version": "${VERSION}",
    "gitSha": "${GIT_SHA}",
    "gitBranch": "${GIT_BRANCH}",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "hostname": "$(hostname)",
    "cpuCores": $(nproc)
  },
  "timing": {
    "totalSeconds": ${TOTAL_DURATION},
    "totalFormatted": "${MINUTES}m ${SECONDS}s",
    "fipsRebuildSeconds": ${FIPS_DURATION:-0}
  },
  "artifacts": {
    "appHex": {
      "filename": "app_merged.hex",
      "sizeBytes": ${APP_HEX_SIZE}
    },
    "commHex": {
      "filename": "comm_merged.hex",
      "sizeBytes": ${COMM_HEX_SIZE}
    }
  },
  "memory": {
    "app": {
      "text": $(echo $APP_MEM | cut -d, -f1),
      "data": $(echo $APP_MEM | cut -d, -f2),
      "bss": $(echo $APP_MEM | cut -d, -f3)
    },
    "comms": {
      "text": $(echo $COMM_MEM | cut -d, -f1),
      "data": $(echo $COMM_MEM | cut -d, -f2),
      "bss": $(echo $COMM_MEM | cut -d, -f3)
    }
  },
  "diagnostics": {
    "warningCount": ${WARNINGS},
    "errorCount": ${ERRORS},
    "warnings": ${WARNINGS_JSON},
    "errors": ${ERRORS_JSON}
  }
}
METRICS_EOF

echo -e "${GREEN}Generated: ${OUTPUT_DIR}/build_metrics.json${NC}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  BUILD COMPLETE${NC}"
echo -e "${GREEN}  Total time: ${MINUTES}m ${SECONDS}s (${TOTAL_DURATION}s)${NC}"
echo -e "${GREEN}  Warnings: ${WARNINGS}, Errors: ${ERRORS}${NC}"
echo -e "${GREEN}========================================${NC}"
echo "Artifacts:"
ls -la ${OUTPUT_DIR}/
