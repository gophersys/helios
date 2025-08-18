#!/bin/bash

function compile() {
    # Set kernel source path
    export STAGING_KERNEL_DIR=/workspaces/concord-os-yocto/linux-toradex

    # Compile DTS to DTBO
    cpp -nostdinc \
        -I $STAGING_KERNEL_DIR/arch/arm64/boot/dts \
        -I $STAGING_KERNEL_DIR/arch/arm64/boot/dts/freescale \
        -I $STAGING_KERNEL_DIR/include \
        -I $STAGING_KERNEL_DIR/scripts/dtc/include-prefixes \
        -undef -x assembler-with-cpp \
        meta-corekinect/recipes-kernel/linux/device-tree-overlays/ina219-overlay.dts \
        ina219-overlay.dts.preprocessed

    dtc -@ -I dts -O dtb -o ina219-overlay.dtbo ina219-overlay.dts.preprocessed

    echo "Compiled ina219-overlay.dtbo successfully"
}

function deploy() {
    # Copy to device
    scp ina219-overlay.dtbo torizon@imx8:/tmp/
    
    # Execute commands with a terminal allocation
    ssh -t torizon@imx8 '
        echo "Mounting /boot read-write..."
        sudo mount -o remount,rw /boot
        
        echo "Finding OSTree overlays directory..."
        OVERLAYS_DIR=$(find /boot/ostree -type d -path "*/dtb/overlays" | head -n 1)
        if [ -z "$OVERLAYS_DIR" ]; then
            echo "Could not find OSTree overlays directory!"
            exit 1
        fi
        echo "OSTree overlays directory: $OVERLAYS_DIR"
        
        echo "Copying overlay..."
        sudo cp /tmp/ina219-overlay.dtbo "$OVERLAYS_DIR/"
        
        echo "Removing legacy overlay if present..."
        sudo rm -f /boot/overlays/ina219-overlay.dtbo
        
        echo "Verifying setup..."
        ls -l "$OVERLAYS_DIR/"
        
        echo "Rebooting..."
        sudo reboot
    '
    
    echo "Deployed and rebooted device"
}

# If script is run directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    case "$1" in
        "compile")
            compile
            ;;
        "deploy")
            deploy
            ;;
        *)
            echo "Usage: $0 {compile|deploy}"
            exit 1
            ;;
    esac
fi