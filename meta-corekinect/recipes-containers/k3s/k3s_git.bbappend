# We need to override the BIN_PREFIX variable to use /usr instead of /usr/local
# because OSTree does not preserve /usr/local in the rootfs
BIN_PREFIX = "/usr"

# Enable k3s-agent to start automatically at boot
SYSTEMD_AUTO_ENABLE:${PN}-agent = "enable"