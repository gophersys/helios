FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

do_install:append() {
    # Create docker config directory
    install -d ${D}${sysconfdir}/docker

    # Write a clean daemon.json with logging config only
    printf '{\n    "log-driver": "json-file",\n    "log-opts": {\n        "max-size": "10m",\n        "max-file": "3"\n    }\n}\n' > ${D}${sysconfdir}/docker/daemon.json
}
