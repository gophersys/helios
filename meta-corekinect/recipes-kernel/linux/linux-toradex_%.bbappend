FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

# Add IIO config fragment
SRC_URI += "file://iio.cfg"
KERNEL_CONFIG_FRAGMENTS += "${WORKDIR}/iio.cfg"

# Update module autoload
KERNEL_MODULE_AUTOLOAD += "lis2de12 bmp280 bmp280_i2c gpio-pca953x at24"

# Update module probe configuration
KERNEL_MODULE_PROBECONF += "ina219 lis2de12 bmp280 bmp280_i2c gpio-pca953x at24"
