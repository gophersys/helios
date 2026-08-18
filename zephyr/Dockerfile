# NOTE: no `# syntax=` directive, deliberately. It made every cold builder
# pull the dockerfile frontend from docker.io — the LAST Docker Hub
# dependency on the build path, and a 502 from auth.docker.io killed a
# build through it (run 2026-08-18). The builder's own built-in frontend
# (BuildKit v0.32) supersedes dockerfile:1.7, and no feature here needs
# the external one.
#
# zephyr — Zephyr RTOS build host on top of gophersys/base.
#
# Adds the Zephyr-specific system deps, the `west` meta-tool (installed via
# uv into an isolated venv), and the Zephyr SDK for cross-compilation.
# Default toolchain set is arm-zephyr-eabi + riscv64-zephyr-elf; override via
# ZSDK_TOOLCHAINS to include more arches at the cost of image size.

ARG BASE_TAG=latest
FROM ghcr.io/gophersys/base:${BASE_TAG}

# Buildx-injected platform vars.
ARG TARGETPLATFORM
ARG BUILDPLATFORM

# -------------------------------------------------------------------------
# Tool versions — latest LTS / stable as of 2026-04-19.
# -------------------------------------------------------------------------
ARG WEST_VERSION=1.5.0                                                 # latest LTS as of 2026-04-19
ARG ZEPHYR_SDK_VERSION=1.0.1                                           # latest LTS as of 2026-04-19
ARG ZEPHYR_SDK_SHA256_AMD64=ca9bc0ff66fafca1dac9d592a36d953cf16d096a9d09b1c0357f021cf9f6a7eb  # upstream-published: https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v1.0.1/sha256.sum
ARG ZEPHYR_SDK_SHA256_ARM64=d79c5bfc68e679488659bea289a4026e52a64f03338875c8c9c850fff13cee30  # upstream-published: https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v1.0.1/sha256.sum
ARG ZSDK_TOOLCHAINS=arm-zephyr-eabi,riscv64-zephyr-elf                 # latest LTS as of 2026-04-19

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
      echo '# gophersys/zephyr — common dev board udev rules.'; \
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

ENV GOPHERSYS_DEVCONTAINER=zephyr

LABEL org.opencontainers.image.source="https://github.com/gophersys/.devcontainer"
LABEL org.opencontainers.image.description="gophersys zephyr layer: west ${WEST_VERSION} + Zephyr SDK ${ZEPHYR_SDK_VERSION}"

USER dev
WORKDIR /workspace
CMD ["/usr/bin/zsh"]
