# CI image for gophersys/hardware — KiCad 10 CLI + the Python test stack.
#
# Deliberately NOT the devcontainer image (.devcontainer/Dockerfile): that one
# carries editors, zsh, Node, gh and Claude Code for interactive work. CI needs
# none of it, and every extra layer is pulled on each cold runner start.
#
# The KiCad install below is the same PPA + package set the devcontainer uses —
# keep the two in sync when bumping KiCad, since the devcontainer is what
# developers reproduce failures in.
#
# Published as ghcr.io/gophersys/hardware-ci by .github/workflows/build-ci-image.yml.

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    PYTHONUNBUFFERED=1

# Pin in one place; referenced by docs/ci.md.
ARG KICAD_PPA_VERSION=10

# ── Base: git for the pilot-data clones, curl/gnupg for the PPA key ──────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        gnupg \
        software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# ── Python ───────────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

# ── KiCad 10 ─────────────────────────────────────────────────────────────────
# kicad-cli drives headless ERC, DRC, netlist export and Gerber generation —
# the pipeline's whole validation loop.
#
# The symbol and footprint libraries are SEPARATE packages and are not pulled in
# by `kicad` under --no-install-recommends. Without them /usr/share/kicad exists
# but is empty, so src/ecad/footprints.py builds a zero-entry index and every
# resolver test fails with `assert 0 > 10000` — which reads like a code bug, not
# a missing package. Name them explicitly.
#
# kicad-packages3d carries the STEP models. FootprintInfo.has_step records their
# presence and validate_footprint warns when a part lacks one, so without this
# package every footprint looks 3D-less and the manufacturing phase exports a
# board with no component geometry.
RUN add-apt-repository -y ppa:kicad/kicad-${KICAD_PPA_VERSION}.0-releases \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        kicad \
        kicad-symbols \
        kicad-footprints \
        kicad-packages3d \
    && rm -rf /var/lib/apt/lists/*

# ── Python test stack ────────────────────────────────────────────────────────
# Matches the working local .venv exactly. kiutils is also vendored in tools/
# (which tests/conftest.py puts ahead on sys.path); the pip copy is the fallback
# for any code path that imports it outside the test harness.
RUN pip3 install --break-system-packages --no-cache-dir \
        kiutils==1.4.8 \
        sexpdata==1.0.2 \
        pytest==9.1.1 \
        ruff==0.16.0

# Fail the build rather than ship an image whose whole purpose is missing.
# The library counts matter as much as the binary: an image with kicad-cli but
# no footprints passes a naive smoke test and then fails the whole resolver
# suite at runtime.
RUN set -eu; \
    kicad-cli version; python3 --version; ruff --version; \
    fp=$(find /usr/share/kicad/footprints -name '*.kicad_mod' 2>/dev/null | wc -l); \
    sym=$(find /usr/share/kicad/symbols -name '*.kicad_sym' 2>/dev/null | wc -l); \
    step=$(find /usr/share/kicad/3dmodels -name '*.step' 2>/dev/null | wc -l); \
    echo "installed: footprints=$fp symbol-libs=$sym step-models=$step"; \
    if [ "$fp" -lt 10000 ]; then echo "ERROR: only $fp footprints"; exit 1; fi; \
    if [ "$sym" -lt 100 ]; then echo "ERROR: only $sym symbol libs"; exit 1; fi; \
    if [ "$step" -lt 1000 ]; then echo "ERROR: only $step STEP models"; exit 1; fi

WORKDIR /workspace
