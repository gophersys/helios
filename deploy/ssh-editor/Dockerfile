# deploy/ssh-editor/Dockerfile — the LOCAL (docker) read-only ssh-remote VS Code substrate.
#
# This is the SIBLING container the desktop "Open in VS Code" path attaches to. The native VS Code
# on the user's Mac opens a `vscode://vscode-remote/ssh-remote+<host><worktreePath>` URI; that drives
# an SSH connection to THIS sshd, into which VS Code Server bootstraps itself and opens the project
# worktree. The worktree is mounted READ-ONLY (deploy/ctl.sh start_ssh_editor passes
# `--volumes-from base-devcontainer:ro`), so every project worktree under /workspace/.eden-runtime is
# VIEWABLE but never editable — the EROFS guarantee is structural (OD-EDITOR-2), not a setting that can
# drift. VS Code Server itself needs a WRITABLE place to install its server + extensions; that is the
# eden user's HOME, mounted from a SEPARATE writable named volume (also start_ssh_editor) so the
# bootstrap succeeds while the source tree stays immutable.
#
# Posture (defence in depth, mirrors the strict-sandbox standing directive):
#   - openssh-server only; a non-root 'eden' user owns the session (PermitRootLogin no).
#   - PUBLIC-KEY auth ONLY (PasswordAuthentication no, no password set on any account) — the
#     AuthorizedKeys are provisioned at START from a key the host generated, never baked into the image.
#   - sftp is enabled (the VS Code Server bootstrap copies its server tarball over the sftp subsystem).
#   - the worktree read-only-ness is enforced by the bind mode at run time, not by the image.
#
# In KUBERNETES this LOCAL adapter is replaced by a per-project sshd Deployment+Service mounting the
# project's workspace PVC read-only with the same authorized-key provisioning — the desktop URI contract
# (ssh-remote+<host><path>) is identical, only the host alias resolution differs.

FROM alpine:3.21

# openssh-server provides sshd + the sftp subsystem VS Code Server needs; the rest are the minimal
# runtime VS Code Server's bootstrap shells out to on a remote host (a POSIX sh, bash for its install
# script, coreutils, tar/gzip to unpack the server, and libstdc++/gcompat so the prebuilt Node-based
# server binary loads against musl). git lets the remote editor read repo metadata of the worktree.
RUN apk add --no-cache \
        openssh-server \
        bash \
        coreutils \
        tar \
        gzip \
        git \
        libstdc++ \
        gcompat \
    && rm -rf /var/cache/apk/*

# A non-root, no-password 'eden' user owns every editor session. The home is a real directory now so
# the writable-home volume mounts cleanly over it at run time (VS Code Server installs into ~/.vscode-server).
RUN addgroup -S eden \
    && adduser -S -G eden -h /home/eden -s /bin/bash eden \
    && mkdir -p /home/eden/.ssh \
    && chmod 700 /home/eden/.ssh \
    && chown -R eden:eden /home/eden \
    # Lock both accounts to key-only (no password hash → password auth is impossible even if re-enabled).
    && passwd -u eden 2>/dev/null || true

# Host keys are generated at START (the entrypoint), not baked, so the image carries no key material.
COPY sshd_config /etc/ssh/sshd_config
COPY entrypoint.sh /usr/local/bin/eden-ssh-editor-entrypoint
RUN chmod 0644 /etc/ssh/sshd_config \
    && chmod 0755 /usr/local/bin/eden-ssh-editor-entrypoint

# sshd listens on 22; deploy/ctl.sh publishes it to 127.0.0.1:<port> on the Mac host (loopback-only).
EXPOSE 22

# The entrypoint provisions the authorized key (from EDEN_SSH_EDITOR_AUTHORIZED_KEY), generates the
# host keys into the writable /etc/ssh, fixes home ownership over the mounted writable volume, then
# execs sshd in the foreground (-D) so the container's lifecycle is sshd's.
ENTRYPOINT ["/usr/local/bin/eden-ssh-editor-entrypoint"]
