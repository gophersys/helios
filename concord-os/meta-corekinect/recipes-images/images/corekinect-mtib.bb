SUMMARY = "CoreKinect MTIB Image"
DESCRIPTION = "CoreKinect MTIB Image for the Verdin iMX8M Mini with Docker support"

require recipes-images/images/torizon-docker.bb

# Override base image settings
IMAGE_BASENAME = "CoreKinect-MTIB"

# Add Toradex Easy Installer support
IMAGE_CLASSES += "image_type_tezi"
TEZI_IMAGE_NAME = "${IMAGE_BASENAME}"

# Enable k3s and virtualization features
DISTRO_FEATURES:append = " k3s"
DISTRO_FEATURES:append = " seccomp"
DISTRO_FEATURES:append = " virtualization"

# Use systemd as init manager for k3s
INIT_MANAGER = "systemd"

# Allocate additional space for containers (2GB)
IMAGE_ROOTFS_EXTRA_SPACE = "2097152"

# Add k3s packages to the image
IMAGE_INSTALL:append = " packagegroup-k3s-node"
IMAGE_INSTALL:append = " corekinect-provisioning"
IMAGE_INSTALL:append = " kernel-modules"

# Add utility tools for testing and monitoring
IMAGE_INSTALL:append = " btop"
IMAGE_INSTALL:append = " iperf3"

# Add UTF-8 locale support (needed for btop and other UTF-8 applications)
IMAGE_LINGUAS = "en-us"
IMAGE_INSTALL:append = " locale-base-en-us glibc-utils"

# Set default locale in environment (create profile script)
create_locale_profile() {
    mkdir -p ${IMAGE_ROOTFS}${sysconfdir}/profile.d
    echo 'export LANG=en_US.UTF-8' > ${IMAGE_ROOTFS}${sysconfdir}/profile.d/locale.sh
    echo 'export LC_ALL=en_US.UTF-8' >> ${IMAGE_ROOTFS}${sysconfdir}/profile.d/locale.sh
    chmod 644 ${IMAGE_ROOTFS}${sysconfdir}/profile.d/locale.sh
}

# ── Trust CoreKinect CA certificates in the system store ──
install_ca_trust() {
    # Add our certs to ca-certificates.conf so update-ca-certificates picks them up
    echo "corekinect-root-ca.crt" >> ${IMAGE_ROOTFS}${sysconfdir}/ca-certificates.conf
    echo "corekinect-sub-ca.crt" >> ${IMAGE_ROOTFS}${sysconfdir}/ca-certificates.conf
    # Append certs to the system trust bundle
    cat ${IMAGE_ROOTFS}${datadir}/ca-certificates/corekinect-root-ca.crt >> \
        ${IMAGE_ROOTFS}${sysconfdir}/ssl/certs/ca-certificates.crt
    cat ${IMAGE_ROOTFS}${datadir}/ca-certificates/corekinect-sub-ca.crt >> \
        ${IMAGE_ROOTFS}${sysconfdir}/ssl/certs/ca-certificates.crt
    # Create OpenSSL hash symlinks for each cert
    HASH_ROOT=$(openssl x509 -hash -noout -in ${IMAGE_ROOTFS}${datadir}/ca-certificates/corekinect-root-ca.crt)
    cp ${IMAGE_ROOTFS}${datadir}/ca-certificates/corekinect-root-ca.crt \
        ${IMAGE_ROOTFS}${sysconfdir}/ssl/certs/${HASH_ROOT}.0
    HASH_SUB=$(openssl x509 -hash -noout -in ${IMAGE_ROOTFS}${datadir}/ca-certificates/corekinect-sub-ca.crt)
    cp ${IMAGE_ROOTFS}${datadir}/ca-certificates/corekinect-sub-ca.crt \
        ${IMAGE_ROOTFS}${sysconfdir}/ssl/certs/${HASH_SUB}.0
}

ROOTFS_POSTPROCESS_COMMAND += "create_locale_profile; install_ca_trust; "

# Disable Android repo manifest copy
COPY_TEZI_ANDROID_MANIFEST = "0"
