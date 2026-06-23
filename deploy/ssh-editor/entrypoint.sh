#!/usr/bin/env bash
# deploy/ssh-editor/entrypoint.sh — provision the ssh-remote read-only editor sshd at start.
#
# Runs as root (sshd must bind :22 and own /etc/ssh host keys) but the SESSION user is always 'eden'
# (sshd_config: PermitRootLogin no, AllowUsers eden). Steps, in order:
#   1. Install the operator-supplied PUBLIC key as eden's only authorized key (key-only auth).
#   2. Generate the host keys into the writable /etc/ssh (never baked into the image).
#   3. Repair ownership of the writable home volume (VS Code Server installs into ~/.vscode-server).
#   4. exec sshd in the foreground so the container's lifecycle is sshd's.
#
# SECRET SAFETY: a PUBLIC key is not a secret, but we still never echo its bytes — only its presence
# and a fingerprint count. The private half NEVER touches this container (it stays on the Mac host's
# ~/.ssh and is presented over the wire by the user's ssh client).
set -Eeuo pipefail

log() { printf '[ssh-editor] %s\n' "$*" >&2; }
die() { printf '[ssh-editor] ERROR: %s\n' "$*" >&2; exit 1; }

EDEN_HOME="/home/eden"
AUTH_KEYS="${EDEN_HOME}/.ssh/authorized_keys"

# ── 1. authorized key (public-key auth ONLY) ──────────────────────────────────────────────────────.
# The host hands the eden public key in EDEN_SSH_EDITOR_AUTHORIZED_KEY (an env var, not a file in the
# image). Without it nobody can ever authenticate — fail loudly rather than start an unreachable sshd.
[ -n "${EDEN_SSH_EDITOR_AUTHORIZED_KEY:-}" ] || die "EDEN_SSH_EDITOR_AUTHORIZED_KEY is unset — no key to authorize (the editor would be unreachable)"

install -d -m 700 -o eden -g eden "${EDEN_HOME}/.ssh"
printf '%s\n' "${EDEN_SSH_EDITOR_AUTHORIZED_KEY}" > "${AUTH_KEYS}"
chmod 600 "${AUTH_KEYS}"
chown eden:eden "${AUTH_KEYS}"
log "authorized_keys provisioned ($(wc -l < "${AUTH_KEYS}" | tr -d ' ') key line(s); value not printed)"

# ── 2. host keys (generated, never baked) ─────────────────────────────────────────────────────────.
# ssh-keygen -A creates any missing host keys for the enabled types into /etc/ssh. /etc/ssh is writable
# in the image, so this re-generates a fresh host identity each container start.
ssh-keygen -A >/dev/null 2>&1 || die "host key generation failed"
log "host keys generated in /etc/ssh"

# sshd refuses to start without its privilege-separation directory.
install -d -m 755 /var/empty 2>/dev/null || true
mkdir -p /run/sshd

# ── 3. writable home for the VS Code Server bootstrap ─────────────────────────────────────────────.
# The worktree (/workspace) is mounted READ-ONLY, but VS Code Server must write its server + extensions
# into ~/.vscode-server. deploy/ctl.sh mounts a SEPARATE writable named volume at /home/eden; repair its
# ownership so the eden user can install into it (a fresh named volume mounts as root-owned).
chown eden:eden "${EDEN_HOME}" 2>/dev/null || true
install -d -m 755 -o eden -g eden "${EDEN_HOME}/.vscode-server"
log "writable home ready at ${EDEN_HOME} (worktree stays read-only)"

# ── 4. run sshd in the foreground ─────────────────────────────────────────────────────────────────.
log "starting sshd (public-key only, user 'eden', worktree read-only) ..."
exec /usr/sbin/sshd -D -e
