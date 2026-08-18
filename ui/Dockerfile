# NOTE: no `# syntax=` directive, deliberately. It made every cold builder
# pull the dockerfile frontend from docker.io — the LAST Docker Hub
# dependency on the build path, and a 502 from auth.docker.io killed a
# build through it (run 2026-08-18). The builder's own built-in frontend
# (BuildKit v0.32) supersedes dockerfile:1.7, and no feature here needs
# the external one.
#
# ui — the headless browser layer on top of gophersys/cloud (research-ui
# ADR-0003).
#
# The consumer is gophersys/research-ui, whose whole gate loop drives headless
# Chrome through tools/densui — `probe.py` reads DENSUI_CHROME — and renders text
# off macOS with the DejaVu fallback font. Its ci/Dockerfile carries the same
# browser and the same font package today and its .devcontainer/Dockerfile builds
# FROM that image; folding both into this set gives them one pin home, one smoke
# gate and one nightly scan instead of three of their own, and dev and CI then
# pin ONE digest — the zero-drift property that repository already has and must
# not lose.
#
# Conventions, and the 1 that differs from its siblings:
#   - ARGs at the top, VALUE-LESS, like base and cloud and unlike the 3 children
#     that spell their own pins. This image is a CHILD that reads versions.env:
#     `pins: versions.env` on its images.yaml entry is what generates the
#     --build-args, and the gate below fails the build naming any pin that did
#     not arrive.
#   - No hardcoded versions in RUN statements.
#   - No `--version` check in any layer. Every pin of this image is compared
#     against what it installed by .ci/smoke.sh, and what a version cannot say is
#     the content-ui group of .ci/image-checks.sh.
#   - The non-root user is the literal `dev`. The parent's SHELL is zsh, which
#     auto-sets $USERNAME to the EFFECTIVE user, so ${USERNAME} in a RUN here
#     would read the layer's uid — see zephyr/Dockerfile for the full account.

ARG BASE_TAG=latest
FROM ghcr.io/gophersys/cloud:${BASE_TAG}

# -------------------------------------------------------------------------
# Tool versions — value-less ARGs, fed from versions.env via generated
# --build-arg. The "latest stable as of" comments live in versions.env, next
# to the values they date.
# -------------------------------------------------------------------------

# The parent's Node, whose version is IN the path this image links from. See the
# toolchain-exposure layer at the foot of this file.
ARG NODE_VERSION

# CHROME_MAJOR_VERSION is deliberately NOT an ARG here. Nothing in this file may
# consume it: google-chrome-stable is installed UNPINNED, because Google's apt
# repo publishes only the current stable — an `=${major}.*` constraint would fail
# the build the day the major moves rather than report the move. The row lives in
# versions.env and .ci/smoke.sh asserts it against `${DENSUI_CHROME} --version`,
# so a browser bump is a red smoke naming the pin and never a silent content
# change. The full account is beside the row.

# -------------------------------------------------------------------------
# The pin gate. Every version above must have arrived from versions.env; an
# absent pin would otherwise expand to the empty string and surface much
# later as a symlink into a path with a hole in it. FAIL-NOT-SKIP: the build
# stops HERE and the message names the variable.
# -------------------------------------------------------------------------
RUN : "${NODE_VERSION:?not in versions.env}"

USER root

# -------------------------------------------------------------------------
# Chrome, from Google's own apt repo, and the DejaVu font it renders with.
#
# Ubuntu's `chromium` is a snap stub that does not work in a container, and the
# Playwright browser CDN timed out from this fleet's egress on all 3 azureedge
# mirrors (research-ui run 31750517561, 30s each). Google's repo is the source
# that leaves.
#
# THE PACKAGE IS UNPINNED ON PURPOSE, which is the base/cloud shape for an apt
# repo somebody else moves — `docker-ce-cli` is installed the same way. Google's
# stable component carries exactly ONE version of google-chrome-stable at a
# time, so a version constraint would not hold an old browser: it would fail the
# build with "Version '151.*' not found" about 4 weeks after it was written. The
# pin that MEANS something is CHROME_MAJOR_VERSION in versions.env, which the
# smoke compares against the browser this layer installed.
#
# The signing key takes the shape base and cloud already use for docker's:
# fetched to /etc/apt/keyrings as armored .asc and named by `signed-by`, so apt
# verifies every chrome package through the signature that key makes over the
# Release file. It carries 1 `unversioned-url` row in
# _build/download-exemptions.txt, for the reason docker's key carries one.
#
# fonts-dejavu-core is not decoration: research-ui's assemble.py takes
# /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf as its fallback font path off
# macOS, and layout that is COMPUTED from font metrics cannot be computed at all
# without one.
#
# densui-chromium is the ONE entry point every architecture resolves to, and the
# gates read DENSUI_CHROME rather than branching on arch. There is 1 install here
# and not 2: Google's stable component publishes google-chrome-stable for amd64
# AND arm64 at the same version (measured 2026-08-18 — the record is beside this
# image's images.yaml entry), so the arch-specific browser source that
# research-ui's ADR-0003 records as risk R3 is not needed.
# hadolint ignore=DL3008
RUN install -m 0755 -d /etc/apt/keyrings \
 && curl -fsSL https://dl.google.com/linux/linux_signing_key.pub -o /etc/apt/keyrings/google-chrome.asc \
 && chmod a+r /etc/apt/keyrings/google-chrome.asc \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/google-chrome.asc] https://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      fonts-dejavu-core \
      google-chrome-stable \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* \
 && ln -s /usr/bin/google-chrome-stable /usr/local/bin/densui-chromium

# The browser the consumer's probe launches. densui/probe.py reads this name,
# and an EMPTY value is worse than an absent binary: `if env:` is false for "",
# so the probe falls through to its own candidate search and can pass without
# ever proving the baked entry point.
ENV DENSUI_CHROME=/usr/local/bin/densui-chromium

# Gates stream their verdicts: without this, python block-buffers when piped and
# uv mutes progress on a non-tty, so a slow step is indistinguishable from a hung
# one. 9.5 silent minutes read as a stall and got cancelled once (research-ui run
# 31761167311).
ENV PYTHONUNBUFFERED=1

# -------------------------------------------------------------------------
# ONE toolchain, reachable by BOTH users. This answers open question Q4 of
# research-ui docs/image-notes.md — "Node 22 vs Node 24" — with cloud's Node 24
# and no second Node at all.
#
# The image this one replaces installed a second root-wide Node and a second
# root-wide uv, because `base` homed both under the `dev` profile while its gates
# run as root. Cloud already puts node, npm and uv on the image-wide ENV PATH, so
# what is missing is not a toolchain: it is the 2 PATHs that ignore that ENV.
# `sudo` replaces PATH with sudoers' secure_path, and /etc/profile rewrites it in
# every LOGIN shell — and `bash -lc` is how the consumer's gates invoke
# themselves. Both of those PATHs hold /usr/local/bin, so 3 symlinks put the one
# toolchain in reach of both users where a second copy was in reach of one.
#
# Measured through the ghcr.io registry API on 2026-08-18 against
# ghcr.io/gophersys/research-ui-ci:latest: its Node 22 layer is 201,604,608
# uncompressed bytes and its uv layer 59,372,544 — 0.26 GB this image does not
# carry, and one version of each tool for the smoke to compare instead of two.
#
# `ln -s` and not `ln -sf`: the day cloud puts its own node in /usr/local/bin
# this layer fails instead of silently overriding it. `test -x` FOLLOWS the
# link, so a NODE_VERSION whose path no longer exists dies here rather than as
# "node: not found" inside somebody's gate.
# -------------------------------------------------------------------------
RUN ln -s "/home/dev/.nvm/versions/node/v${NODE_VERSION}/bin/node" /usr/local/bin/node \
 && ln -s "/home/dev/.nvm/versions/node/v${NODE_VERSION}/bin/npm" /usr/local/bin/npm \
 && ln -s /home/dev/.local/bin/uv /usr/local/bin/uv \
 && test -x /usr/local/bin/node \
 && test -x /usr/local/bin/npm \
 && test -x /usr/local/bin/uv

ENV GOPHERSYS_DEVCONTAINER=ui

LABEL org.opencontainers.image.source="https://github.com/gophersys/.devcontainer"
LABEL org.opencontainers.image.description="gophersys ui layer: headless google-chrome-stable + the DejaVu fallback font on cloud"
LABEL org.opencontainers.image.licenses="MIT"

USER dev
WORKDIR /workspace
CMD ["/usr/bin/zsh"]
