SUMMARY = "A tool for measuring network performance"
DESCRIPTION = "iperf3 is a tool for active measurements of the maximum achievable bandwidth on IP networks"
HOMEPAGE = "https://github.com/esnet/iperf"
LICENSE = "BSD-3-Clause"
LIC_FILES_CHKSUM = "file://LICENSE;md5=f2eb355b6d3b9d63b6b7a861cdc62440"

SRC_URI = "https://github.com/esnet/iperf/archive/refs/tags/${PV}.tar.gz;downloadfilename=iperf-${PV}.tar.gz"
SRC_URI[sha256sum] = "dd289b6700d3bc33eda7fa3ce6db217d6ca42239edbcb2e7f152bf7bf5c8a5aa"

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
