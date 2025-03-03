#!/bin/bash

function compile() {
    # Set kernel source path
    export STAGING_KERNEL_DIR=/workspaces/concord-os-yocto/linux-toradex

    # Compile DTS to DTBO
    cpp -nostdinc \
        -I $STAGING_KERNEL_DIR/arch/arm64/boot/dts \
        -I $STAGING_KERNEL_DIR/include \
        -I $STAGING_KERNEL_DIR/scripts/dtc/include-prefixes \
        -undef -x assembler-with-cpp \
        meta-corekinect/recipes-kernel/linux/device-tree-overlays/no-i2s.dts \
        no-i2s.dts.preprocessed

    dtc -@ -I dts -O dtb -o no-i2s.dtbo no-i2s.dts.preprocessed

    echo "Compiled no-i2s.dtbo successfully"
}

function deploy() {
    # Copy to device
    scp no-i2s.dtbo torizon@imx8:/tmp/
    
    # Execute commands with a terminal allocation
    ssh -t torizon@imx8 '
        echo "Mounting /boot read-write..."
        sudo mount -o remount,rw /boot
        
        echo "Creating overlays directory..."
        sudo mkdir -p /boot/overlays
        
        echo "Copying overlay..."
        sudo cp /tmp/no-i2s.dtbo /boot/overlays/
        
        echo "Setting U-Boot environment..."
        sudo fw_setenv overlays no-i2s.dtbo
        sudo fw_setenv saveenv
        
        echo "Verifying setup..."
        sudo fw_printenv overlays
        ls -l /boot/overlays/
        
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