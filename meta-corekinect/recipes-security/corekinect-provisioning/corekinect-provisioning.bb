SUMMARY = "CoreKinect MTIB node provisioning"
DESCRIPTION = "Pre-provisions CA certificates, Docker registry trust, and K3s agent configuration"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

# Pull files from both the recipe files/ dir and the secrets/ dir
# ${THISDIR}/../../secrets resolves to meta-corekinect/secrets/
FILESEXTRAPATHS:prepend := "${THISDIR}/files:${THISDIR}/../../secrets:"

SRC_URI = " \
    file://corekinect-root-ca.crt \
    file://corekinect-sub-ca.crt \
    file://k3s-server-url \
    file://k3s-token \
    file://k3s-registries.yaml \
    file://k3s-logs.conf \
    file://corekinect-password.service \
    file://corekinect-set-password.sh \
"

RDEPENDS:${PN} = "ca-certificates"

do_install() {
    # ── CA certificates (system trust store) ──
    # Use /usr/share (not /usr/local/share) so OSTree preserves them
    install -d ${D}${sysconfdir}/ssl/certs
    install -d ${D}${datadir}/ca-certificates
    install -m 0644 ${WORKDIR}/corekinect-root-ca.crt \
        ${D}${datadir}/ca-certificates/corekinect-root-ca.crt
    install -m 0644 ${WORKDIR}/corekinect-sub-ca.crt \
        ${D}${datadir}/ca-certificates/corekinect-sub-ca.crt

    # ── Docker registry trust ──
    install -d ${D}${sysconfdir}/docker/certs.d/containers.ad.corekinect.com
    cat ${WORKDIR}/corekinect-root-ca.crt ${WORKDIR}/corekinect-sub-ca.crt \
        > ${D}${sysconfdir}/docker/certs.d/containers.ad.corekinect.com/ca.crt
    chmod 0644 ${D}${sysconfdir}/docker/certs.d/containers.ad.corekinect.com/ca.crt

    # ── K3s agent configuration ──
    install -d ${D}${sysconfdir}/rancher/k3s

    # Store the token under /usr/lib so OSTree preserves it
    install -d ${D}/usr/lib/rancher/k3s
    install -m 0600 ${WORKDIR}/k3s-token \
        ${D}/usr/lib/rancher/k3s/agent-token

    # config.yaml — read server URL from secrets file
    K3S_URL=$(cat ${WORKDIR}/k3s-server-url | tr -d '[:space:]')
    printf 'server: %s\ntoken-file: /usr/lib/rancher/k3s/agent-token\n' "${K3S_URL}" \
        > ${D}${sysconfdir}/rancher/k3s/config.yaml
    chmod 0600 ${D}${sysconfdir}/rancher/k3s/config.yaml

    # registries.yaml
    install -m 0644 ${WORKDIR}/k3s-registries.yaml \
        ${D}${sysconfdir}/rancher/k3s/registries.yaml

    # ── tmpfiles.d for K3s log directories ──
    install -d ${D}${sysconfdir}/tmpfiles.d
    install -m 0644 ${WORKDIR}/k3s-logs.conf \
        ${D}${sysconfdir}/tmpfiles.d/k3s-logs.conf

    # ── Password service (firstboot oneshot) ──
    install -d ${D}${sysconfdir}/systemd/system/multi-user.target.wants
    install -m 0644 ${WORKDIR}/corekinect-password.service \
        ${D}${sysconfdir}/systemd/system/corekinect-password.service
    ln -sf ../corekinect-password.service \
        ${D}${sysconfdir}/systemd/system/multi-user.target.wants/corekinect-password.service
    install -d ${D}/usr/lib/corekinect
    install -m 0755 ${WORKDIR}/corekinect-set-password.sh \
        ${D}/usr/lib/corekinect/set-password.sh
    touch ${D}${sysconfdir}/corekinect-password-pending
}

FILES:${PN} = " \
    ${datadir}/ca-certificates/*.crt \
    ${sysconfdir}/ssl/certs \
    ${sysconfdir}/docker/certs.d/containers.ad.corekinect.com/ca.crt \
    ${sysconfdir}/rancher/k3s/config.yaml \
    ${sysconfdir}/rancher/k3s/registries.yaml \
    /usr/lib/rancher/k3s/agent-token \
    ${sysconfdir}/tmpfiles.d/k3s-logs.conf \
    ${sysconfdir}/systemd/system/corekinect-password.service \
    ${sysconfdir}/systemd/system/multi-user.target.wants/corekinect-password.service \
    ${sysconfdir}/corekinect-password-pending \
    /usr/lib/corekinect/set-password.sh \
"
