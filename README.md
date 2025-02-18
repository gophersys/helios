# Heavily inspired by
-  https://developer.toradex.com/torizon/in-depth/build-torizoncore-from-source-with-yocto-projectopenembedded/#manifest-file

# Build your own meta layer
- https://developer.toradex.com/linux-bsp/os-development/build-yocto/custom-meta-layers-recipes-and-images-in-yocto-project-hello-world-examples/#create-a-meta-layer

# Machine requirements
- Needs at least 24GB memory
- Needs at least 100GB disk space
- Needs at least 8 CPU cores

# To find the Device Tree files

To find the Device Tree Source (DTS) files for the Verdin iMX8M Mini:
```bash
find torizon/build/tmp/work-shared/verdin-imx8mm/kernel-source -name "imx8mm-verdin*.dts"
```

To find the Device Tree Source Include (DTSI) files:
```bash
find torizon/build/tmp/work-shared/verdin-imx8mm/kernel-source -name "imx8mm-verdin*.dtsi"
```

These files define the hardware configuration:
- `.dts` files are the main device tree source files
- `.dtsi` files are include files containing common definitions (like the base SoM configuration and carrier board specifics)

The relevant files are:
- `imx8mm-verdin.dtsi` - Base SoM configuration
- `imx8mm-verdin-wifi.dtsi` - WiFi-specific configuration
- `imx8mm-verdin-mallow.dtsi` - Carrier board configuration for Mallow

Which can be found at:
```
torizon/build/tmp/work-shared/verdin-imx8mm/kernel-source/arch/arm64/boot/dts/freescale/imx8mm-verdin.dtsi
torizon/build/tmp/work-shared/verdin-imx8mm/kernel-source/arch/arm64/boot/dts/freescale/imx8mm-verdin-wifi.dtsi
torizon/build/tmp/work-shared/verdin-imx8mm/kernel-source/arch/arm64/boot/dts/freescale/imx8mm-verdin-mallow.dtsi
```

# Force rebuild the image
```bash
bitbake -C do_image corekinect-mtib
```

# Custom username and password
https://community.toradex.com/t/build-torizon-os-with-custom-username-and-password/20745