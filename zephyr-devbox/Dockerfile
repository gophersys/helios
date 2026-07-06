# syntax=docker/dockerfile:1.7
#
# zephyr-devbox — remote SSH-able embedded dev box on top of gophersys/zephyr.
#
# Runs as a Kubernetes pod and is targeted with VS Code Remote-SSH. Adds
# sshd (key-auth only, host keys on a persistent volume), the flash/debug
# stack for the lab bench (openocd, stlink-tools, esptool, picocom,
# gdb-multiarch), the full Espressif Xtensa SDK toolchain set, and udev
# rules for the USB-UART bridges the bench boards use (CP210x, CH340).
#
# The container starts as ROOT so sshd can bind and manage host keys;
# interactive work happens over SSH as the `dev` user. Local devcontainer
# use still works: the entrypoint execs any provided argv instead of sshd.

ARG BASE_TAG=latest
FROM ghcr.io/gophersys/zephyr:${BASE_TAG}

# Buildx-injected platform vars.
ARG TARGETPLATFORM
ARG BUILDPLATFORM

# -------------------------------------------------------------------------
# Tool versions — latest LTS / stable as of 2026-07-05.
# -------------------------------------------------------------------------
ARG ESPTOOL_VERSION=5.3.1                                              # latest stable as of 2026-07-05
# Extra Zephyr SDK toolchains installed on top of the parent layer's set
# (arm-zephyr-eabi + riscv64-zephyr-elf). This is EVERY Espressif toolchain
# sdk-ng v1.0.1 ships (names verified against the release's toolchain
# assets): the three Xtensa variants. Espressif's RISC-V parts (ESP32-C3,
# rv32imc) have no dedicated SDK toolchain — they build with the multilib
# riscv64-zephyr-elf the parent layer already installs.
ARG ZSDK_EXTRA_TOOLCHAINS=xtensa-espressif_esp32_zephyr-elf,xtensa-espressif_esp32s2_zephyr-elf,xtensa-espressif_esp32s3_zephyr-elf

# NOTE: the non-root user is hardcoded as `dev` throughout this Dockerfile
# (matching the base image's invariant). An ARG USERNAME is intentionally NOT
# used here because the parent image's SHELL is zsh-with-pipefail, and zsh
# unconditionally auto-sets the special parameter $USERNAME to the effective
# logname. See zephyr/Dockerfile for the full rationale.

# -------------------------------------------------------------------------
# apt layer — SSH server + flash/debug/serial tooling.
#   openssh-server  remote entry point (config hardened below)
#   openocd         SWD/JTAG flash + debug server (ST-Link on the Nucleos)
#   stlink-tools    st-info/st-flash for quick ST-Link operations
#   picocom         serial terminal for board consoles
#   gdb-multiarch   single host gdb for `target extended-remote` debugging
#                   against openocd, regardless of target arch (the SDK's
#                   per-toolchain gdbs exist but one multiarch gdb is what
#                   IDE debug configs point at)
# The host keys Debian's postinst generates are removed: this image is
# shared, and the real keys live on a per-pod persistent volume
# (/etc/ssh/hostkeys), created by the entrypoint on first boot.
# -------------------------------------------------------------------------
USER root
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      gdb-multiarch \
      openocd \
      openssh-server \
      picocom \
      stlink-tools \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* \
 && rm -f /etc/ssh/ssh_host_*_key /etc/ssh/ssh_host_*_key.pub

# -------------------------------------------------------------------------
# esptool — installed into an isolated uv-managed venv, same pattern as the
# parent layer's west venv, so its deps don't collide with project tooling.
# -------------------------------------------------------------------------
ENV ESPTOOL_VENV=/opt/esptool-venv \
    PATH=/opt/esptool-venv/bin:${PATH}

# NOTE: zsh auto-sets $USERNAME to the effective logname (here: "root"), so
# the `dev` user and its ~/.local/bin/uv path are addressed directly — see
# the matching note in zephyr/Dockerfile.
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
# Extra Zephyr SDK toolchains — same setup.sh mechanism the parent layer
# uses; setup.sh resolves its own host arch and fetches the matching
# toolchain archive into ${ZEPHYR_SDK_INSTALL_DIR} (inherited env).
# -------------------------------------------------------------------------
# hadolint ignore=DL4006,DL3003,SC2086
RUN ( cd "${ZEPHYR_SDK_INSTALL_DIR}" \
      && TOOL_ARGS=""; \
         for t in ${(s:,:)ZSDK_EXTRA_TOOLCHAINS}; do TOOL_ARGS="${TOOL_ARGS} -t ${t}"; done; \
         eval ./setup.sh ${TOOL_ARGS} )
# NOTE: -c (cmake registration) omitted — the parent layer already ran it.
# zsh-native ${(s:,:)VAR} split + eval re-tokenization: see zephyr/Dockerfile.

# -------------------------------------------------------------------------
# udev rules for the USB-UART bridges on the bench boards. The parent layer
# covers the debug probes (ST-Link, J-Link, DAPLink, ...) and Espressif
# native USB (303a); this adds the serial bridge chips.
# -------------------------------------------------------------------------
RUN mkdir -p /etc/udev/rules.d \
 && { \
      echo '# gophersys/zephyr-devbox — USB-UART bridge udev rules.'; \
      echo '# Silicon Labs CP210x (classic ESP32 devkits)'; \
      echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE="0666", GROUP="plugdev"'; \
      echo '# WCH CH340/CH341'; \
      echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE="0666", GROUP="plugdev"'; \
    } > /etc/udev/rules.d/99-gophersys-devbox.rules

# -------------------------------------------------------------------------
# sshd hardening drop-in. Ubuntu's stock sshd_config Includes
# /etc/ssh/sshd_config.d/*.conf and ships with all HostKey lines commented
# out, so the paths below are the only host keys sshd loads.
# /etc/ssh/hostkeys is intended to be a mounted PVC subpath so the box
# keeps its SSH identity across pod restarts; the entrypoint generates the
# keys on first boot.
# -------------------------------------------------------------------------
RUN mkdir -p /etc/ssh/sshd_config.d /etc/ssh/hostkeys /etc/devbox \
 && { \
      echo '# gophersys/zephyr-devbox — hardened sshd for the remote dev box.'; \
      echo 'HostKey /etc/ssh/hostkeys/ssh_host_ed25519_key'; \
      echo 'HostKey /etc/ssh/hostkeys/ssh_host_rsa_key'; \
      echo 'PermitRootLogin no'; \
      echo 'PasswordAuthentication no'; \
      echo 'KbdInteractiveAuthentication no'; \
      echo 'AllowUsers dev'; \
      echo 'X11Forwarding no'; \
      echo '# Keep long flash/debug sessions alive across cluster ingress idle timeouts.'; \
      echo 'ClientAliveInterval 30'; \
      echo 'ClientAliveCountMax 4'; \
    } > /etc/ssh/sshd_config.d/10-gophersys-devbox.conf

# -------------------------------------------------------------------------
# SSH login shells do NOT inherit container ENV, so the toolchain paths the
# parent layers export via Docker ENV must also land in /etc/zsh/zshenv
# (the base layer already does this for its own toolchains).
# -------------------------------------------------------------------------
RUN { \
      echo '# Set by gophersys/zephyr-devbox Dockerfile — SSH logins do not inherit container ENV.'; \
      echo 'export PATH=/opt/west-venv/bin:/opt/esptool-venv/bin:${PATH}'; \
      echo 'export ZEPHYR_SDK_INSTALL_DIR=/opt/zephyr-sdk'; \
      echo 'export ZEPHYR_BASE=/workspace/zephyr'; \
    } >> /etc/zsh/zshenv

COPY --chmod=0755 devbox-entrypoint.sh /usr/local/bin/devbox-entrypoint.sh

ENV GOPHERSYS_DEVCONTAINER=zephyr-devbox

LABEL org.opencontainers.image.source="https://github.com/gophersys/.devcontainer"
LABEL org.opencontainers.image.description="gophersys zephyr-devbox layer: SSH-able k8s embedded dev box (sshd + openocd + stlink + esptool ${ESPTOOL_VERSION} + picocom)"

EXPOSE 22

# Root by design: the entrypoint prepares host keys / volume ownership and
# execs sshd. Interactive logins land as `dev` (AllowUsers dev).
USER root
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/devbox-entrypoint.sh"]
