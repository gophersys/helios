#!/bin/bash

set -euo pipefail

FLUIDNC_VERSION="3.9.4"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[mtib-assets]${NC} $*"; }
warn() { echo -e "${YELLOW}[mtib-assets]${NC} $*"; }
err()  { echo -e "${RED}[mtib-assets]${NC} $*" >&2; }
info() { echo -e "${CYAN}[mtib-assets]${NC} $*"; }

_generate_fluidnc_install_script() {
    local work_dir="/tmp/fluidnc-work"
    cat > "${work_dir}/fluidNc/install-no-radio.sh" << 'EOF'
#!/bin/sh

set -e

if ! . ./tools.sh; then exit 1; fi

Bootloader="0x1000 wifi/bootloader.bin"
Bootapp="0xe000 common/boot_app0.bin"
Firmware="0x10000 noradio-firmware.bin"
Partitions="0x8000 wifi/partitions.bin"

if ! check_security; then
    exit 1
fi

esptool_write $Bootloader $Bootapp $Firmware $Partitions

echo "Starting fluidterm"

deactivate
EOF

    chmod +x "${work_dir}/fluidNc/install-no-radio.sh"
}

generate_fluidnc_assets() {
    local zip_file="/tmp/fluidnc-v${FLUIDNC_VERSION}-posix.zip"
    local work_dir="/tmp/fluidnc-work"
    local script_dir=$(dirname $(readlink -f $0))

    rm -rf "${zip_file}" "${work_dir}"
    mkdir -p "${work_dir}"
    cd "${work_dir}"

    info "Downloading FluidNC v${FLUIDNC_VERSION}..."
    if ! curl -L "https://github.com/bdring/FluidNC/releases/download/v${FLUIDNC_VERSION}/fluidnc-v${FLUIDNC_VERSION}-posix.zip" -o "${zip_file}"; then
        err "Failed to download FluidNC assets"
        return 1
    fi

    if [ $(stat -c%s "${zip_file}") -lt 1024 ]; then
        err "Downloaded file is too small, likely corrupted"
        rm -f "${zip_file}"
        return 1
    fi

    info "Unzipping assets..."
    if ! unzip "${zip_file}"; then
        err "Failed to unzip assets"
        return 1
    fi

    rm -f "${zip_file}"

    info "Downloading no-radio firmware..."
    if ! curl -L "https://github.com/bdring/FluidNC/releases/download/v${FLUIDNC_VERSION}/noradio-firmware.elf" -o "noradio-firmware.elf"; then
        err "Failed to download no-radio firmware"
        return 1
    fi

    cd "fluidnc-v${FLUIDNC_VERSION}-posix"
    source ./tools.sh
    esptool_basic elf2image ../noradio-firmware.elf
    cd ..

    mkdir -p "fluidNc"
    cp -r fluidnc-v${FLUIDNC_VERSION}-posix/* fluidNc/
    cp noradio-firmware.elf fluidNc/
    cp noradio-firmware.bin fluidNc/

    _generate_fluidnc_install_script

    rm -rf "${script_dir}/fluidNc"
    mv fluidNc "${script_dir}/"

    cd -
    rm -rf "${work_dir}"

    log "FluidNC assets generated successfully"
}

ACTION="${1:-generate}"

case "$ACTION" in
    generate)
        generate_fluidnc_assets
        ;;
    *)
        err "Unknown command: $ACTION"
        echo "Usage: $0 [generate]"
        exit 1
        ;;
esac
