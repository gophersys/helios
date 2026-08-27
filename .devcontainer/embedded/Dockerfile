# NOTE: no `# syntax=` directive, deliberately. It made every cold builder
# pull the dockerfile frontend from docker.io — the LAST Docker Hub
# dependency on the build path, and a 502 from auth.docker.io killed a
# build through it (run 2026-08-18). The builder's own built-in frontend
# (BuildKit v0.32) supersedes dockerfile:1.7, and no feature here needs
# the external one.
#
# embedded — the Zephyr toolchain image.
#
# It was 2 images: `zephyr` (the toolchain) and `zephyr-devbox` (that same
# toolchain plus 9 layers, for a k8s pod). The fold made them 1, and the DEVBOX
# HALF IS NOW DELETED — Mateo, 2026-08-19: "yes strip and delete and clean up
# anything devbox we don't need any of it anymore". Its consumer had already
# gone (gophersys/infrastructure #192 deleted the only Deployment that set
# DEVBOX_AUTHORIZED_KEYS), and no manifest, workflow or pod anywhere in the org
# set GOPHERSYS_EMBEDDED_MODE. The record is "The devbox mode is deleted" in
# .claude/rules/00-identity.md.
#
# WHAT WENT: sshd and its hardened drop-in, /etc/ssh/hostkeys, /etc/devbox,
# code-server and its baked clangd extension seed, EXPOSE 22 and EXPOSE 8443,
# and the CODE_SERVER_VERSION pin with its 2 digest rows.
#
# WHAT STAYED, and it is everything the TOOLCHAIN uses: the Zephyr-specific
# system deps, the `west` meta-tool (installed via uv into an isolated venv),
# the Zephyr SDK for cross-compilation (default toolchain set arm-zephyr-eabi +
# riscv64-zephyr-elf, override via ZSDK_TOOLCHAINS at the cost of image size),
# the full Espressif Xtensa SDK toolchain set, the flash/debug stack for the lab
# bench (openocd, stlink-tools, esptool, picocom, gdb-multiarch), clangd, and
# the udev rules for the debug probes and for the USB-UART bridges the bench
# boards use (CP210x, CH340). None of those is reached over SSH: they are what a
# developer runs inside the devcontainer and what CI runs in the same image.
#
# IT STILL SHIPS `USER root`, and embedded-entrypoint.sh is what drops to `dev`
# before it execs the command — so `docker run embedded id` is dev exactly as it
# was. With sshd gone nothing here needs root any more, and collapsing the pair
# into a plain `USER dev` is open work stated in that file, not a thing this
# change already did.

ARG BASE_TAG=latest
FROM ghcr.io/gophersys/base:${BASE_TAG}

# Buildx-injected platform vars.
ARG TARGETPLATFORM
ARG BUILDPLATFORM

# -------------------------------------------------------------------------
# Tool versions. 2 ARG blocks stood here — one in zephyr/Dockerfile dated
# 2026-04-19, one in zephyr-devbox/Dockerfile dated 2026-07-05 — and the fold
# merged them WITHOUT moving a value: every row below, and every evidence
# comment beside it, is the one that was reviewed in its own image. Each date
# comment therefore records the day somebody looked at THAT pin, which is what
# a date beside a value means everywhere else in this repository.
#
# CODE_SERVER_VERSION and its 2 digest rows left this block with the devbox
# deletion (2026-08-19). They were the only pin here that no toolchain layer
# read, so the block is 5 rows now and _build/upstreams.txt lost its row in the
# same change — a pin with no home is what upstream-coverage.test.sh refuses.
# -------------------------------------------------------------------------
ARG WEST_VERSION=1.5.0                                                 # latest LTS as of 2026-04-19
ARG ZEPHYR_SDK_VERSION=1.0.1                                           # latest LTS as of 2026-04-19
ARG ZEPHYR_SDK_SHA256_AMD64=ca9bc0ff66fafca1dac9d592a36d953cf16d096a9d09b1c0357f021cf9f6a7eb  # upstream-published: https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v1.0.1/sha256.sum
ARG ZEPHYR_SDK_SHA256_ARM64=d79c5bfc68e679488659bea289a4026e52a64f03338875c8c9c850fff13cee30  # upstream-published: https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v1.0.1/sha256.sum
ARG ZSDK_TOOLCHAINS=arm-zephyr-eabi,riscv64-zephyr-elf                 # latest LTS as of 2026-04-19
ARG ESPTOOL_VERSION=5.3.1                                              # latest stable as of 2026-07-05
# Extra Zephyr SDK toolchains installed on top of the set ZSDK_TOOLCHAINS
# names (arm-zephyr-eabi + riscv64-zephyr-elf). This is EVERY Espressif
# toolchain sdk-ng v1.0.1 ships (names verified against the release's toolchain
# assets): the three Xtensa variants. Espressif's RISC-V parts (ESP32-C3,
# rv32imc) have no dedicated SDK toolchain — they build with the multilib
# riscv64-zephyr-elf the layer above installs.
ARG ZSDK_EXTRA_TOOLCHAINS=xtensa-espressif_esp32_zephyr-elf,xtensa-espressif_esp32s2_zephyr-elf,xtensa-espressif_esp32s3_zephyr-elf

# NOTE: the non-root user is hardcoded as `dev` throughout this Dockerfile
# (matching the base image's invariant). An ARG USERNAME is intentionally NOT
# used here because the parent image's SHELL is zsh-with-pipefail, and zsh
# unconditionally auto-sets the special parameter $USERNAME to the effective
# logname. That clobbers any ARG-provided value, producing paths like
# /home/root/.local/bin/uv at build time. Hardcoding `dev` avoids the whole
# class of failure.

# -------------------------------------------------------------------------
# Zephyr's documented Ubuntu host dependencies.
# https://docs.zephyrproject.org/latest/develop/getting_started/index.html
# -------------------------------------------------------------------------
USER root
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ccache \
      device-tree-compiler \
      dfu-util \
      gperf \
      libmagic1 \
      libsdl2-dev \
      ninja-build \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# -------------------------------------------------------------------------
# west — installed into an isolated uv-managed venv so its deps don't
# collide with project-level tooling.
# -------------------------------------------------------------------------
ENV WEST_VENV=/opt/west-venv \
    PATH=/opt/west-venv/bin:${PATH}

# NOTE: zsh auto-sets $USERNAME to the effective logname (here: "root") even
# when Docker passes USERNAME=dev in the env, so we cannot reference ${USERNAME}
# from a zsh-as-root RUN layer — we must address the user via a safer vector.
# The `dev` user and its ~/.local/bin/uv path are fixtures of the base image,
# hence the direct paths below.
RUN mkdir -p "${WEST_VENV}" \
 && chown -R dev:dev "${WEST_VENV}" \
 && runuser -u dev -- /home/dev/.local/bin/uv venv "${WEST_VENV}" \
 && runuser -u dev -- /home/dev/.local/bin/uv pip install \
      --python "${WEST_VENV}/bin/python" \
      --no-cache-dir \
      "west==${WEST_VERSION}" \
      pyelftools \
      pyyaml \
      cryptography \
      intelhex \
      packaging \
      pykwalify \
      colorama \
      anytree \
      canopen \
 && chmod -R a+rx "${WEST_VENV}"
# NOTE: west --version smoke removed — fails under QEMU cross-arch build;
# verified in post-build smoke test (.ci/smoke.sh).

# -------------------------------------------------------------------------
# Zephyr SDK — TARGETPLATFORM-aware archive. Host arch is encoded in the
# asset name; setup.sh installs only the toolchains in ZSDK_TOOLCHAINS.
# -------------------------------------------------------------------------
ENV ZEPHYR_SDK_INSTALL_DIR=/opt/zephyr-sdk \
    ZEPHYR_BASE=/workspace/zephyr

# hadolint ignore=DL4006,DL3003,SC2086
RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=x86_64; SHA256="${ZEPHYR_SDK_SHA256_AMD64}"; SHA256_PIN=ZEPHYR_SDK_SHA256_AMD64 ;; \
      linux/arm64) ARCH=aarch64; SHA256="${ZEPHYR_SDK_SHA256_ARM64}"; SHA256_PIN=ZEPHYR_SDK_SHA256_ARM64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && mkdir -p "${ZEPHYR_SDK_INSTALL_DIR}" \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${ZEPHYR_SDK_VERSION}/zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-${ARCH}_minimal.tar.xz" \
      /tmp/zsdk.tar.xz \
      "${SHA256}" "${SHA256_PIN}" \
 && tar -C "${ZEPHYR_SDK_INSTALL_DIR}" --strip-components=1 -xJf /tmp/zsdk.tar.xz \
 && rm /tmp/zsdk.tar.xz \
 && ( cd "${ZEPHYR_SDK_INSTALL_DIR}" \
      && TOOL_ARGS=""; \
         for t in ${(s:,:)ZSDK_TOOLCHAINS}; do TOOL_ARGS="${TOOL_ARGS} -t ${t}"; done; \
         eval ./setup.sh ${TOOL_ARGS} -c )
# NOTE: -h means "help" in the Zephyr SDK setup.sh, not "host tools";
# omitted so the script doesn't exit with help text.
# Uses zsh-native ${(s:,:)VAR} parameter expansion to split ZSDK_TOOLCHAINS
# on commas — plain `set -- ${VAR}` does NOT word-split in zsh the way it
# does in bash. `eval` is required to re-tokenize TOOL_ARGS as separate
# argv slots rather than one big positional arg.

# -------------------------------------------------------------------------
# udev rules for common development boards (ST-Link, J-Link, Black Magic
# Probe, DAPLink, Nordic nRF, Espressif). These rules are the ONLY source: the
# SDK ships none.
# -------------------------------------------------------------------------
# A branch that copied 60-openocd.rules out of the SDK stood here, and it was
# dead code twice over. MEASURED on 2026-08-18, both platforms, by listing the
# pinned tarballs:
#
#   zephyr-sdk-1.0.1_linux-x86_64_minimal.tar.xz    20 entries
#   zephyr-sdk-1.0.1_linux-aarch64_minimal.tar.xz   20 entries
#
# and in NEITHER of them is there a `sysroots/` directory or a file named
# 60-openocd.rules. A 1.0.1 minimal tarball carries cmake/, hosttools/,
# setup.sh, sdk_version and sdk_gnu_toolchains — nothing else. `setup.sh -c`
# installs the gnu toolchains; `-h` is deliberately omitted 20 lines above, so
# the host tools never unpack either. The comment that described a
# `sysroots/<arch>-pokysdk-linux/usr/share/openocd/contrib` layout was reading
# the 0.16.x SDK, which this image has not pinned for some time.
#
# So the copy could never fire, and the version of it that used `find` was
# WORSE than dead: find exits 1 on a path that does not exist, and under this
# `&&` chain that killed the RUN on amd64 and arm64 alike — a layer that had
# always worked, broken by a guard written for a layout nobody listed.
#
# The fallback rules below are therefore unconditional, and they are what the
# image has actually been shipping all along.
RUN mkdir -p /etc/udev/rules.d \
 && { \
      echo '# gophersys/embedded — common dev board udev rules.'; \
      echo '# ST-Link (STM32)'; \
      echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="374b", MODE="0666", GROUP="plugdev"'; \
      echo '# SEGGER J-Link'; \
      echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="1366", MODE="0666", GROUP="plugdev"'; \
      echo '# Nordic nRF'; \
      echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="1915", MODE="0666", GROUP="plugdev"'; \
      echo '# Black Magic Probe'; \
      echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6018", MODE="0666", GROUP="plugdev"'; \
      echo '# DAPLink / CMSIS-DAP'; \
      echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="0d28", ATTRS{idProduct}=="0204", MODE="0666", GROUP="plugdev"'; \
      echo '# Espressif'; \
      echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="303a", MODE="0666", GROUP="plugdev"'; \
    } > /etc/udev/rules.d/99-gophersys-zephyr.rules \
 && (getent group plugdev >/dev/null || groupadd plugdev) \
 && usermod -aG plugdev,dialout dev

# -------------------------------------------------------------------------
# apt layer — the flash/debug/serial stack for the lab bench.
#   openocd         SWD/JTAG flash + debug server (ST-Link on the Nucleos)
#   stlink-tools    st-info/st-flash for quick ST-Link operations
#   picocom         serial terminal for board consoles
#   gdb-multiarch   single host gdb for `target extended-remote` debugging
#                   against openocd, regardless of target arch (the SDK's
#                   per-toolchain gdbs exist but one multiarch gdb is what
#                   IDE debug configs point at)
#   clangd          C/C++ language server backing VS Code IntelliSense
#                   (the repo's committed .vscode settings point at it)
#
# `openssh-server` was the 6th name here and it is GONE with the devbox
# deletion, and so is the `rm -f /etc/ssh/ssh_host_*` that only existed to
# throw away the keys its postinst generates. Every other name is a tool a
# developer runs INSIDE the container — clangd included: the VS Code clangd
# extension in a "Reopen in Container" session drives this same binary, and it
# was never reached only through code-server.
# -------------------------------------------------------------------------
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      clangd \
      gdb-multiarch \
      openocd \
      picocom \
      stlink-tools \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# -------------------------------------------------------------------------
# esptool — installed into an isolated uv-managed venv, the same pattern the
# west venv above uses, so its deps don't collide with project tooling.
# -------------------------------------------------------------------------
ENV ESPTOOL_VENV=/opt/esptool-venv \
    PATH=/opt/esptool-venv/bin:${PATH}

# NOTE: zsh auto-sets $USERNAME to the effective logname (here: "root"), so
# the `dev` user and its ~/.local/bin/uv path are addressed directly — see
# the matching note at the top of this file.
RUN mkdir -p "${ESPTOOL_VENV}" \
 && chown -R dev:dev "${ESPTOOL_VENV}" \
 && runuser -u dev -- /home/dev/.local/bin/uv venv "${ESPTOOL_VENV}" \
 && runuser -u dev -- /home/dev/.local/bin/uv pip install \
      --python "${ESPTOOL_VENV}/bin/python" \
      --no-cache-dir \
      "esptool==${ESPTOOL_VERSION}" \
 && chmod -R a+rx "${ESPTOOL_VENV}"
# NOTE: esptool version smoke deliberately omitted — fails under QEMU
# cross-arch build; verified in post-build smoke test (.ci/smoke.sh).

# -------------------------------------------------------------------------
# West venv runtime deps the venv layer above misses. West extension commands
# (`west build`, `west flash`) and the blob fetchers (`west blobs fetch`)
# import `requests` and `jsonschema` at runtime; without them all three
# crash (masked by a west bug as "AttributeError: 'NoneType' object has no
# attribute 'err'"). The espressif extension (`west espressif monitor`)
# does `import esptool` INSIDE the west venv — the standalone esptool venv
# above does not satisfy that — and pyserial is imported by the monitor
# and by runner code. uv-created venvs ship WITHOUT pip, so install via
# the same uv-as-dev mechanism that created the venv.
# -------------------------------------------------------------------------
RUN runuser -u dev -- /home/dev/.local/bin/uv pip install \
      --python "${WEST_VENV}/bin/python" \
      --no-cache-dir \
      requests \
      jsonschema \
      "esptool==${ESPTOOL_VERSION}" \
      pyserial \
 && chmod -R a+rx "${WEST_VENV}"

# -------------------------------------------------------------------------
# Extra Zephyr SDK toolchains — the same setup.sh mechanism the SDK layer
# above uses; setup.sh resolves its own host arch and fetches the matching
# toolchain archive into ${ZEPHYR_SDK_INSTALL_DIR} (inherited env).
# -------------------------------------------------------------------------
# hadolint ignore=DL4006,DL3003,SC2086
RUN ( cd "${ZEPHYR_SDK_INSTALL_DIR}" \
      && TOOL_ARGS=""; \
         for t in ${(s:,:)ZSDK_EXTRA_TOOLCHAINS}; do TOOL_ARGS="${TOOL_ARGS} -t ${t}"; done; \
         eval ./setup.sh ${TOOL_ARGS} )
# NOTE: -c (cmake registration) omitted — the SDK layer above already ran it.
# zsh-native ${(s:,:)VAR} split + eval re-tokenization: see that layer.

# -------------------------------------------------------------------------
# udev rules for the USB-UART bridges on the bench boards. The rules layer
# above covers the debug probes (ST-Link, J-Link, DAPLink, ...) and Espressif
# native USB (303a); this adds the serial bridge chips.
# -------------------------------------------------------------------------
# The file was `99-gophersys-devbox.rules` and it is renamed with the devbox
# deletion. Nothing reads the NAME — udev reads the directory — and a rules
# file named after a mode that no longer exists is the stale reference this
# repository refuses everywhere else.
RUN mkdir -p /etc/udev/rules.d \
 && { \
      echo '# gophersys/embedded — USB-UART bridge udev rules.'; \
      echo '# Silicon Labs CP210x (classic ESP32 devkits)'; \
      echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE="0666", GROUP="plugdev"'; \
      echo '# WCH CH340/CH341'; \
      echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE="0666", GROUP="plugdev"'; \
    } > /etc/udev/rules.d/99-gophersys-usb-uart.rules

# -------------------------------------------------------------------------
# The toolchain paths the layers above export via Docker ENV also land in
# /etc/zsh/zshenv, the same shim base writes for its own toolchains: a zsh
# that starts without inheriting this container's environment — `zsh -l`,
# `su - dev` — otherwise sees neither venv.
#
# Its comment used to give SSH logins as the reason. That reason left with
# sshd; the shim stays because base's does, for every other shell.
# -------------------------------------------------------------------------
# The single quotes are the point: ${PATH} must reach the profile file as literal
# text, to be expanded at login and not at build time. Expanding it here would
# freeze the build-time PATH into every SSH session.
# hadolint ignore=SC2016
RUN { \
      echo '# Set by the gophersys/embedded Dockerfile — a zsh that does not inherit container ENV.'; \
      echo 'export PATH=/opt/west-venv/bin:/opt/esptool-venv/bin:${PATH}'; \
      echo 'export ZEPHYR_SDK_INSTALL_DIR=/opt/zephyr-sdk'; \
      echo 'export ZEPHYR_BASE=/workspace/zephyr'; \
    } >> /etc/zsh/zshenv

COPY --chmod=0755 embedded-entrypoint.sh /usr/local/bin/embedded-entrypoint.sh

ENV GOPHERSYS_DEVCONTAINER=embedded

LABEL org.opencontainers.image.source="https://github.com/gophersys/.devcontainer"
LABEL org.opencontainers.image.description="gophersys embedded layer: west ${WEST_VERSION} + Zephyr SDK ${ZEPHYR_SDK_VERSION} + Espressif Xtensa toolchains + flash/debug bench (openocd + stlink + esptool ${ESPTOOL_VERSION} + picocom + gdb-multiarch + clangd)"

# `EXPOSE 22` and `EXPOSE 8443` stood here and went with sshd and code-server.
# This image listens on nothing.

# Root, and embedded-entrypoint.sh is what drops to `dev` before it execs the
# command — so `docker run embedded id` answers dev, which is what `USER dev`
# in the pre-fold Dockerfile did. NOTHING NEEDS ROOT HERE ANY MORE now that the
# pod half is deleted; collapsing this pair into a plain `USER dev` is stated as
# open work at the top of the entrypoint, because it also moves .ci/smoke.sh's
# embedded-only `--user dev` arm.
# hadolint ignore=DL3002
USER root
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/embedded-entrypoint.sh"]
CMD ["/usr/bin/zsh"]
