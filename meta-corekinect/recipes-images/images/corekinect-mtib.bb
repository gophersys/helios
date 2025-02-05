SUMMARY = "CoreKinect MTIB Image"
DESCRIPTION = "CoreKinect MTIB Image for the Verdin iMX8M Mini with Docker support"

require recipes-images/images/torizon-docker.bb

# Override base image settings
IMAGE_BASENAME = "CoreKinect-MTIB"

# Add Toradex Easy Installer support
IMAGE_CLASSES += "image_type_tezi"
TEZI_IMAGE_NAME = "${IMAGE_BASENAME}"

# Ensure device tree overlays are included and loaded at boot
MACHINE_EXTRA_RRECOMMENDS += "kernel-devicetree-overlays"

# Remove the direct dependency on moby-engine since it's handled by torizon-docker.bb
# through VIRTUAL-RUNTIME_container_engine

# Disable Android repo manifest copy
COPY_TEZI_ANDROID_MANIFEST = "0"