# syntax=docker/dockerfile:1.7
#
# images/base — Ubuntu 24.04 LTS with the shell + git + Bitwarden CLI
# toolchain every other image layers on top of.
#
# Consumed both as the local-dev devcontainer base AND as the CI runtime.
FROM ubuntu:24.04

LABEL org.opencontainers.image.source="https://github.com/gophersys/.devcontainer"
LABEL org.opencontainers.image.description="Base image: ubuntu:24.04 + shell/git/bw toolchain"
LABEL org.opencontainers.image.licenses="MIT"

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=UTC

# Core toolchain: build essentials, shell utilities, git, curl, CA roots,
# tmpfs/cleanup tools used by ctl.sh on_exit traps (shred, mount), and
# the jq + shellcheck pair used by validate targets downstream.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      bash \
      bash-completion \
      ca-certificates \
      curl \
      git \
      gnupg \
      jq \
      less \
      locales \
      make \
      openssh-client \
      shellcheck \
      sudo \
      tzdata \
      unzip \
      util-linux \
      xz-utils \
 && locale-gen C.UTF-8 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Bitwarden CLI — installed from the official release tarball. Pinned to a
# specific version so the base image is reproducible; bump explicitly.
ARG BW_VERSION=2024.7.2
RUN curl -fsSL \
      "https://github.com/bitwarden/clients/releases/download/cli-v${BW_VERSION}/bw-oss-linux-${BW_VERSION}.zip" \
      -o /tmp/bw.zip \
 && unzip /tmp/bw.zip -d /usr/local/bin \
 && chmod +x /usr/local/bin/bw \
 && rm /tmp/bw.zip \
 && bw --version

# Non-root user for daily use. UID/GID 1000 matches the default VS Code
# devcontainer remote user and the typical host user in WSL/Linux dev boxes,
# so bind mounts don't end up root-owned. Ubuntu 24.04 ships with a
# pre-created `ubuntu` user/group at UID 1000 — remove it first.
ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=1000
RUN if id ubuntu >/dev/null 2>&1; then userdel --remove ubuntu 2>/dev/null || userdel ubuntu; fi \
 && if getent group ubuntu >/dev/null 2>&1; then groupdel ubuntu; fi \
 && groupadd --gid "${USER_GID}" "${USERNAME}" \
 && useradd --uid "${USER_UID}" --gid "${USER_GID}" --create-home --shell /bin/bash "${USERNAME}" \
 && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/${USERNAME}" \
 && chmod 0440 "/etc/sudoers.d/${USERNAME}"

USER ${USERNAME}
WORKDIR /home/${USERNAME}

CMD ["/bin/bash"]
