SUMMARY = "A tool for measuring network performance"
DESCRIPTION = "iperf3 is a tool for active measurements of the maximum achievable bandwidth on IP networks"
HOMEPAGE = "https://github.com/esnet/iperf"
LICENSE = "BSD-3-Clause"
LIC_FILES_CHKSUM = "file://LICENSE;md5=b51332d7f45357a9410daa9a14a3655f"

SRC_URI = "https://github.com/esnet/iperf/archive/refs/tags/${PV}.tar.gz;downloadfilename=iperf-${PV}.tar.gz"
SRC_URI[sha256sum] = "84640ea0f43831850434e50134d0554b7a94f97fb02e2488ffbe252c9fb05a56"

DEPENDS = ""

inherit autotools-brokensep

S = "${WORKDIR}/iperf-${PV}"

EXTRA_OECONF = "--enable-static --disable-shared"

# Generate configure script if needed
do_configure:prepend() {
    if [ -f ${S}/bootstrap.sh ]; then
        cd ${S}
        ./bootstrap.sh
    fi
}

FILES:${PN} = "${bindir}/iperf3"
FILES:${PN}-dev = "${includedir} ${libdir}/libiperf.a"
