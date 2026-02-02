#!/bin/bash

# Define tools version
FLUIDNC_VERSION="3.9.4"

# ----------------------------------------------------------------------------------
#                                                                            FluidNc
# --------------------------------------------------------------------------------*/
function _generate_fluidnc_install_script() {
    local script_dir=$(dirname $(readlink -f $0))
    local work_dir="/tmp/fluidnc-work"
    cat > "${work_dir}/fluidNc/install-no-radio.sh" << 'EOF'
#!/bin/sh

set -e

if ! . ./tools.sh; then exit 1; fi

# The elf2image command creates firmware.bin in the current directory
# Set up the paths for flashing
Bootloader="0x1000 wifi/bootloader.bin"
Bootapp="0xe000 common/boot_app0.bin"
Firmware="0x10000 noradio-firmware.bin"
Partitions="0x8000 wifi/partitions.bin"

if ! check_security; then
    exit 1
fi

# Flash all components
esptool_write $Bootloader $Bootapp $Firmware $Partitions

echo "Starting fluidterm"

# Deactivate the virtual environment
deactivate
EOF

    # Make the script executable
    chmod +x "${work_dir}/fluidNc/install-no-radio.sh"
}

function generate_fluidnc_assets() {
    local zip_file="/tmp/fluidnc-v${FLUIDNC_VERSION}-posix.zip"
    local work_dir="/tmp/fluidnc-work"
    local script_dir=$(dirname $(readlink -f $0))
    
    # Clean up any existing files
    rm -rf "${zip_file}" "${work_dir}"
    mkdir -p "${work_dir}"
    
    # Change to work directory
    cd "${work_dir}"
    
    echo "Downloading FluidNC assets..."
    
    # Fetch the latest version of FluidNC assets with error checking
    if ! curl -L "https://github.com/bdring/FluidNC/releases/download/v${FLUIDNC_VERSION}/fluidnc-v${FLUIDNC_VERSION}-posix.zip" -o "${zip_file}"; then
        echo "Failed to download FluidNC assets"
        return 1
    fi

    # Verify file size is reasonable (more than 1KB)
    if [ $(stat -c%s "${zip_file}") -lt 1024 ]; then
        echo "Downloaded file is too small, likely corrupted"
        rm -f "${zip_file}"
        return 1
    fi

    echo "Unzipping assets..."
    # Unzip the assets
    if ! unzip "${zip_file}"; then
        echo "Failed to unzip assets"
        return 1
    fi

    # Delete the zip file
    rm -f "${zip_file}"

    echo "Downloading no-radio firmware..."
    # Fetch the latest "no-radio" firmware
    if ! curl -L "https://github.com/bdring/FluidNC/releases/download/v${FLUIDNC_VERSION}/noradio-firmware.elf" -o "noradio-firmware.elf"; then
        echo "Failed to download no-radio firmware"
        return 1
    fi

    # Change into the unzipped directory
    cd "fluidnc-v${FLUIDNC_VERSION}-posix"

    # Source the tools.sh file from the current directory
    source ./tools.sh

    # Convert the "no-radio" firmware to a binary using esptool
    esptool_basic elf2image ../noradio-firmware.elf

    # Go back to work directory
    cd ..

    # Create output directory structure
    mkdir -p "fluidNc"
    
    # Copy only the needed files to the final location
    cp -r fluidnc-v${FLUIDNC_VERSION}-posix/* fluidNc/
    cp noradio-firmware.elf fluidNc/
    cp noradio-firmware.bin fluidNc/

    # Add script to assets directory to flash newly generated no radio firmware
    _generate_fluidnc_install_script

    # Move the final directory to the script location
    rm -rf "${script_dir}/fluidNc"
    mv fluidNc "${script_dir}/"

    # Clean up
    cd -
    rm -rf "${work_dir}"
    
    echo "FluidNC assets generated successfully"
}

# ----------------------------------------------------------------------------------
#                                                                               Main
# --------------------------------------------------------------------------------*/
function main() {
    generate_fluidnc_assets
}

main
