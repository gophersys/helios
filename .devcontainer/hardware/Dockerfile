# NOTE: no `# syntax=` directive, deliberately. It made every cold builder
# pull the dockerfile frontend from docker.io — the LAST Docker Hub
# dependency on the build path, and a 502 from auth.docker.io killed a
# build through it (run 2026-08-18). The builder's own built-in frontend
# (BuildKit v0.32) supersedes dockerfile:1.7, and no feature here needs
# the external one.
#
# hardware — the KiCad 10 ECAD toolchain on top of gophersys/cloud.
#
# The consumer is gophersys/research-hardware, whose whole validation loop is
# `kicad-cli` driving headless ERC, DRC, netlist export and Gerber generation.
# Its ci/Dockerfile carries the same PPA and the same 4 packages today; folding
# that image into this set is what gives it one pin home, one smoke gate and one
# nightly scan instead of three of its own.
#
# Conventions, and the 1 that differs from its siblings:
#   - ARGs at the top, VALUE-LESS, like base and cloud and unlike the other 3
#     children. This image is a CHILD that reads versions.env: `pins:
#     versions.env` on its images.yaml entry is what generates the --build-args,
#     and the gate below fails the build naming any pin that did not arrive.
#     Spelling the values here would mint a 4th PIN_VALUE_HOME for 5 pins.
#   - No hardcoded versions in RUN statements.
#   - No `--version` check in any layer. Every pin of this image is compared
#     against what it installed by .ci/smoke.sh, and the library floors are the
#     content-hardware group of .ci/image-checks.sh.
#   - The non-root user is the literal `dev`. The parent's SHELL is zsh, which
#     auto-sets $USERNAME to the EFFECTIVE user, so ${USERNAME} in a RUN here
#     would read the layer's uid — see embedded/Dockerfile for the full account.

ARG BASE_TAG=latest
FROM ghcr.io/gophersys/cloud:${BASE_TAG}

# Buildx-injected platform var. Declared so a RUN layer can branch on arch.
ARG TARGETPLATFORM

# -------------------------------------------------------------------------
# Tool versions — value-less ARGs, fed from versions.env via generated
# --build-arg. The "latest stable as of" comments live in versions.env, next
# to the values they date.
# -------------------------------------------------------------------------

# The KiCad major line inside the PPA name. Not a version: the archive behind
# `ppa:kicad/kicad-10.0-releases` publishes 10.0.5~ubuntu24.04.1 on noble.
ARG KICAD_PPA_VERSION

# The python stack the consumer's suite imports and runs.
ARG KIUTILS_VERSION
ARG SEXPDATA_VERSION
ARG PYTEST_VERSION
ARG RUFF_VERSION

# -------------------------------------------------------------------------
# The pin gate. Every version above must have arrived from versions.env; an
# absent pin would otherwise expand to the empty string and surface much
# later as `kicad==` or a PPA name with a hole in it. FAIL-NOT-SKIP: the
# build stops HERE and the message names the variable.
# -------------------------------------------------------------------------
RUN : "${KICAD_PPA_VERSION:?not in versions.env}" \
 && : "${KIUTILS_VERSION:?not in versions.env}" \
 && : "${SEXPDATA_VERSION:?not in versions.env}" \
 && : "${PYTEST_VERSION:?not in versions.env}" \
 && : "${RUFF_VERSION:?not in versions.env}"

USER root

# -------------------------------------------------------------------------
# KiCad, from the project's own PPA.
#
# The symbol and footprint libraries are SEPARATE packages and `kicad` does
# not pull them in under --no-install-recommends. Without them /usr/share/kicad
# exists and is EMPTY, so the consumer's footprint index builds zero entries and
# every resolver test fails on `assert 0 > 10000` — which reads like a code bug
# rather than a missing package. kicad-packages3d carries the STEP models, and
# without it every footprint looks 3D-less and the manufacturing phase exports a
# board with no component geometry. Naming all 4 is the fix; the floors in
# .ci/image-checks.sh are what keep it true.
#
# add-apt-repository comes from software-properties-common, which the parent
# already installs. The PPA's signing key is fetched by that command and then
# signs the Release file, so every package is verified through apt's own
# signature chain — the reason _build/download-exemptions.txt names no row for
# it: there is no URL in this file for a digest to answer.
# -------------------------------------------------------------------------
# hadolint ignore=DL3008
RUN add-apt-repository -y "ppa:kicad/kicad-${KICAD_PPA_VERSION}.0-releases" \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      kicad \
      kicad-footprints \
      kicad-packages3d \
      kicad-symbols \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# -------------------------------------------------------------------------
# The python stack, into the SYSTEM interpreter.
#
# Not `uv tool install`, which is what this repository uses for every other
# python pin: that gives each tool an isolated venv, and kiutils and sexpdata
# are LIBRARIES the consumer's suite imports from `python3 -m pytest`. A tool
# venv is unreachable from there, so the tools would run and the imports would
# fail. --break-system-packages is what ubuntu 24.04 requires to write into a
# PEP 668 interpreter, and it is deliberate rather than a workaround here: the
# system interpreter IS the environment this image exists to provide.
# -------------------------------------------------------------------------
RUN pip3 install --break-system-packages --no-cache-dir \
      "kiutils==${KIUTILS_VERSION}" \
      "pytest==${PYTEST_VERSION}" \
      "ruff==${RUFF_VERSION}" \
      "sexpdata==${SEXPDATA_VERSION}"

ENV GOPHERSYS_DEVCONTAINER=hardware

LABEL org.opencontainers.image.source="https://github.com/gophersys/.devcontainer"
LABEL org.opencontainers.image.description="gophersys hardware layer: KiCad ${KICAD_PPA_VERSION} + the kiutils/pytest/ruff stack on cloud"
LABEL org.opencontainers.image.licenses="MIT"

USER dev
WORKDIR /workspace
CMD ["/usr/bin/zsh"]
