SUMMARY = "A modern resource monitor that shows usage and stats for processor, memory, disks, network and processes"
DESCRIPTION = "btop++ is a C++ version/port of the bashtop and bpytop system monitors, with additional features and improvements"
HOMEPAGE = "https://github.com/aristocratos/btop"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

SRC_URI = "https://github.com/aristocratos/btop/archive/refs/tags/v${PV}.tar.gz;downloadfilename=btop-${PV}.tar.gz"
SRC_URI[sha256sum] = "0ffe03d3e26a3e9bbfd5375adf34934137757994f297d6b699a46edd43c3fc02"

DEPENDS = "ncurses"

inherit cmake

EXTRA_OECMAKE = "-DCMAKE_BUILD_TYPE=Release"

S = "${WORKDIR}/btop-${PV}"

FILES:${PN} = "${bindir}/btop \
                ${datadir}/icons/hicolor/48x48/apps/btop.png \
                ${datadir}/icons/hicolor/scalable/apps/btop.svg \
                ${datadir}/applications/btop.desktop \
                ${datadir}/btop/themes"
