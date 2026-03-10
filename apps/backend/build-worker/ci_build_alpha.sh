#!/bin/bash
# CI Build Script for Alpha firmware
# Environment variables:
#   REPO_DIR    - Path to cloned firmware repo
#   OUTPUT_DIR  - Path to output artifacts
#   BOARD       - Board name (alpha_a0, alpha_b0)
#   VARIANT     - Build variant (debug, release)
#   BOOT_KEY    - Boot signing key (optional, for CFW generation)

set -e
CYAN='\033[0;36m'
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

REPO_DIR="${REPO_DIR:-$(pwd)}"
OUTPUT_DIR="${OUTPUT_DIR:-${REPO_DIR}/artifacts}"
BOARD="${BOARD:-alpha_b0}"
VARIANT="${VARIANT:-debug}"

# Determine comm processor SOC based on board
case $BOARD in
    alpha_a0) COMM_SOC="nrf9160" ;;
    alpha_b0) COMM_SOC="nrf9151" ;;
    *) echo "${RED}Unsupported board: ${BOARD}${NC}"; exit 1 ;;
esac

mkdir -p "${OUTPUT_DIR}"

echo "${CYAN}*****Building for board: ${BOARD} (comm SOC: ${COMM_SOC})*****${NC}"
echo "REPO_DIR: ${REPO_DIR}"
echo "OUTPUT_DIR: ${OUTPUT_DIR}"
echo "VARIANT: ${VARIANT}"

# Generate dev encryption keys if not present
if [ ! -f "${REPO_DIR}/encryption_key.pem" ]; then
    echo "${CYAN}Generating dev encryption key...${NC}"
    openssl ecparam -name prime256v1 -genkey -noout -out "${REPO_DIR}/encryption_key.pem"
fi
if [ ! -f "${REPO_DIR}/comms_encryption_key.pem" ]; then
    echo "${CYAN}Generating dev comms encryption key...${NC}"
    openssl ecparam -name prime256v1 -genkey -noout -out "${REPO_DIR}/comms_encryption_key.pem"
fi

# Fix hardcoded paths in sysbuild.conf
for conf in $(find "${REPO_DIR}" -name "sysbuild.conf" -type f 2>/dev/null); do
    sed -i "s|/workspaces/alpha_fw|${REPO_DIR}|g" "$conf" 2>/dev/null || true
    sed -i "s|/workspaces/comm_coproc_mfg|${REPO_DIR}/comm_coproc_mfg|g" "$conf" 2>/dev/null || true
done

echo "${CYAN}*****Building Application*****${NC}"
west build --pristine -d ${REPO_DIR}/build -b ${BOARD}/nrf52840 --sysbuild ${REPO_DIR} -- \
    -DBOARD_ROOT=${REPO_DIR}/ck_boards/current/ \
    -DEXTRA_CONF_FILE=${REPO_DIR}/version.conf

if [ $? -ne 0 ]; then
    echo "${RED}Application build failed${NC}"
    exit 1
fi

# Merge PSP hex if available
if [ -f ${REPO_DIR}/vsm_drv/src/corekinect/module/vsm/threads/vitals/lib/bin/psp.hex ]; then
    echo "${CYAN}Merging PSP hex...${NC}"
    mergehex -m ${REPO_DIR}/build/merged.hex ${REPO_DIR}/vsm_drv/src/corekinect/module/vsm/threads/vitals/lib/bin/psp.hex -o ${REPO_DIR}/build/merged.hex
fi

echo "${CYAN}*****Building Communication Coprocessor*****${NC}"

COMM_DIR="${REPO_DIR}/comm_coproc_mfg"

# Update encryption key path
sed -i "s|/workspaces/comm_coproc_mfg/comms_encryption_key.pem|${REPO_DIR}/comms_encryption_key.pem|g" ${COMM_DIR}/sysbuild.conf
sed -i "s|/workspaces/alpha_fw/comms_encryption_key.pem|${REPO_DIR}/comms_encryption_key.pem|g" ${COMM_DIR}/sysbuild.conf

echo "# FIPS hash - placeholder for first build" > ${COMM_DIR}/fips.conf

west build --pristine -d ${COMM_DIR}/build -b ${BOARD}/${COMM_SOC}/ns --sysbuild ${COMM_DIR} -- \
    -DBOARD_ROOT=${REPO_DIR}/ck_boards/current/ \
    "-DEXTRA_CONF_FILE=${REPO_DIR}/version.conf;${REPO_DIR}/default_personalization.conf"

if [ $? -ne 0 ]; then
    echo "${RED}Communication coprocessor build failed${NC}"
    exit 1
fi

echo "${CYAN}*****Calculating FIPS hash and rebuilding*****${NC}"
python3 ${COMM_DIR}/wolfssl/scripts/gen_fips_hash.py ${COMM_DIR}/build/merged.hex ${COMM_DIR}/build/comm_coproc_mfg/zephyr/zephyr.map > ${COMM_DIR}/fips.conf

west build -d ${COMM_DIR}/build -b ${BOARD}/${COMM_SOC}/ns --sysbuild ${COMM_DIR} -- \
    -DBOARD_ROOT=${REPO_DIR}/ck_boards/current/ \
    -DOVERLAY_CONFIG=fips.conf \
    "-DEXTRA_CONF_FILE=${REPO_DIR}/version.conf;${REPO_DIR}/default_personalization.conf"

if [ $? -ne 0 ]; then
    echo "${RED}FIPS rebuild failed${NC}"
    exit 1
fi

# Copy artifacts to output
echo "${CYAN}*****Copying artifacts*****${NC}"
cp -v ${REPO_DIR}/build/merged.hex ${OUTPUT_DIR}/app_merged.hex 2>/dev/null || true
cp -v ${REPO_DIR}/build/alpha_fw/zephyr/zephyr.hex ${OUTPUT_DIR}/app.hex 2>/dev/null || true
cp -v ${COMM_DIR}/build/merged.hex ${OUTPUT_DIR}/comm_merged.hex 2>/dev/null || true
cp -v ${COMM_DIR}/build/comm_coproc_mfg/zephyr/zephyr.hex ${OUTPUT_DIR}/comm.hex 2>/dev/null || true

echo "${GREEN}*****BUILD COMPLETE*****${NC}"
echo "Artifacts:"
ls -la ${OUTPUT_DIR}/
