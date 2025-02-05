FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

# Add IIO config fragment
SRC_URI += "file://iio.cfg"
KERNEL_CONFIG_FRAGMENTS += "${WORKDIR}/iio.cfg"

# Update module autoload
KERNEL_MODULE_AUTOLOAD += "ad7949 ad7949"

# Update module probe configuration
KERNEL_MODULE_PROBECONF += "ina219 ad7949" 