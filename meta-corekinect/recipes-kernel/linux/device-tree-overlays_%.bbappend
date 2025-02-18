# https://community.toradex.com/t/adding-custom-overlays-to-yocto-image/21209/9

FILESEXTRAPATHS:prepend := "${THISDIR}/device-tree-overlays:"

CUSTOM_OVERLAYS_SOURCE = " \
    ina219-overlay.dts \
    ad7689-overlay.dts \
"

# There's a bug in the build system that doesn't allow the inclusion of custom
# overlays without including the `verdin-imx8mm_spidev_overlay.dtbo` overlay.
# 
# The custom overlays added by CoreKinect are:
#
# - ina219-overlay.dtbo: INA219 Current Sensor, connected to I2C4
# - ad7689-overlay.dtbo: AD7689 16-bit ADC, connected to SPI1
#
CUSTOM_OVERLAYS_BINARY = " \
    verdin-imx8mm_spidev_overlay.dtbo \
    ina219-overlay.dtbo \
    ad7689-overlay.dtbo \
"

SRC_URI += " \
    file://ina219-overlay.dts \
    file://ad7689-overlay.dts \
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