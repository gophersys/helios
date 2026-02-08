# https://community.toradex.com/t/adding-custom-overlays-to-yocto-image/21209/9

FILESEXTRAPATHS:prepend := "${THISDIR}/device-tree-overlays:"

# Add DTC flags for symbol generation
DTC_FLAGS += "-@"

CUSTOM_OVERLAYS_SOURCE = " \
    ina219-overlay.dts \
    mtib-v2-overlay.dts \
    no-i2s.dts \
    no-i2c.dts \
    usb.dts \
"

# There's a bug in the build system that doesn't allow the inclusion of custom
# overlays without including the `verdin-imx8mm_spidev_overlay.dtbo` overlay.
#
# The custom overlays added by CoreKinect are:
#
# - ina219-overlay.dtbo: INA219 + ADS1115 + LIS2DE12, connected to I2C4
# - mtib-v2-overlay.dtbo: BME280 + TCA9534A + AT24C02C on I2C4 (Rev 1.2)
# - no-i2s.dtbo: Disables I2S (SAI2) interface to free pins for GPIO
# - no-i2c.dtbo: Disables I2C (I2C4) interface to free pins for GPIO
# - usb.dtbo: USB configuration
#
CUSTOM_OVERLAYS_BINARY = " \
    verdin-imx8mm_spidev_overlay.dtbo \
    ina219-overlay.dtbo \
    mtib-v2-overlay.dtbo \
    no-i2s.dtbo \
    no-i2c.dtbo \
    usb.dtbo \
"

SRC_URI += " \
    file://ina219-overlay.dts \
    file://mtib-v2-overlay.dts \
    file://no-i2s.dts \
    file://no-i2c.dts \
    file://usb.dts \
"

TEZI_EXTERNAL_KERNEL_DEVICETREE += " \
    ${CUSTOM_OVERLAYS_BINARY} \
"

TEZI_EXTERNAL_KERNEL_DEVICETREE:use-mainline-bsp += " \
    ${CUSTOM_OVERLAYS_BINARY} \
"

TEZI_EXTERNAL_KERNEL_DEVICETREE_BOOT += " \
    ${CUSTOM_OVERLAYS_BINARY} \
"

TEZI_EXTERNAL_KERNEL_DEVICETREE_BOOT:use-mainline-bsp += " \
    ${CUSTOM_OVERLAYS_BINARY} \
"

do_collect_overlays:prepend() {
    for DTS in ${CUSTOM_OVERLAYS_SOURCE}; do
        cp ${WORKDIR}/${DTS} ${S}
    done
}
