SUMMARY = "CoreKinect MTIB Image"
DESCRIPTION = "CoreKinect MTIB Image for the Verdin iMX8M Mini with Docker support"

require recipes-images/images/torizon-docker.bb

# Override base image settings
IMAGE_BASENAME = "CoreKinect-MTIB"

# Add Toradex Easy Installer support
IMAGE_CLASSES += "image_type_tezi"
TEZI_IMAGE_NAME = "${IMAGE_BASENAME}"

# This is disabled for now because the system is not booting
# when the container preloading is enabled
# TODO: Enable this again when the system is stable
# 
# # Define insecure registries
# CONTAINER_INSECURE_REGISTRIES = " \
#     kubecop.ad.corekinect.com:5000 \
# "

# # Preload Docker images
# CONTAINER_PRELOAD_IMAGES = " \
#     kubecop.ad.corekinect.com:5000/concord-mtib:dev \
# "

# # Enable container preloading feature
# MACHINE_FEATURES:append = " preload-containers"

# # Add the container preloading class from our layer
# inherit image-preload-container

# Disable Android repo manifest copy
COPY_TEZI_ANDROID_MANIFEST = "0"
