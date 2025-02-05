FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI += "file://daemon.json"

do_install:append() {
    # Create docker config directory if it doesn't exist
    install -d ${D}${sysconfdir}/docker
    
    # Install the daemon.json file
    install -m 0644 ${WORKDIR}/daemon.json ${D}${sysconfdir}/docker/daemon.json
} 