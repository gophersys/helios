FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

# Ensure we run after Torizon's modifications
do_install[vardeps] += "DOCKER_DAEMON_CONFIG"

# Ensure this runs after Torizon's modifications
DOCKER_DAEMON_CUSTOMIZATION[vardepsexclude] = "DATETIME"
DOCKER_DAEMON_CUSTOMIZATION = "${DATETIME}"

do_install:append() {
    # Create docker config directory
    install -d ${D}${sysconfdir}/docker

    # Read existing daemon.json if it exists
    if [ -f ${D}${sysconfdir}/docker/daemon.json ]; then
        cp ${D}${sysconfdir}/docker/daemon.json ${WORKDIR}/daemon.json.orig
    else
        echo "{}" > ${WORKDIR}/daemon.json.orig
    fi

    # Merge configurations using jq
    # This preserves existing settings and adds/updates our registry
    cat ${WORKDIR}/daemon.json.orig | \
        jq '. * {"insecure-registries": ((.["insecure-registries"] // []) + ["kubecop.ad.corekinect.com:5000"] | unique)}' \
        > ${D}${sysconfdir}/docker/daemon.json
}

DEPENDS += "jq-native" 