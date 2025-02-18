FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

# Add IIO config fragment
SRC_URI += "file://iio.cfg"
KERNEL_CONFIG_FRAGMENTS += "${WORKDIR}/iio.cfg"

# Update module autoload
KERNEL_MODULE_AUTOLOAD += "ad7949 lis2de12 bmp380-i2c bmp390 mcp4017 bmp280 bmp280_i2c"

# Update module probe configuration
KERNEL_MODULE_PROBECONF += "ina219 ad7949 lis2de12 bmp380-i2c bmp390 mcp4017 bmp280 bmp280_i2c"