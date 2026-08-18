#!/usr/bin/env bash
#
# embedded-entrypoint.sh — PID 1 of the embedded image, in both of its modes.
#
# The image is `zephyr` and `zephyr-devbox` folded into 1, and 1 image cannot
# carry 2 users: the pod half needs root for sshd, the toolchain half is `dev`.
# So the image ships `USER root` and this file picks the identity, keyed on
# GOPHERSYS_EMBEDDED_MODE:
#
#   devbox           the pod. Runs as root: prepares persistent SSH host keys,
#                    the `dev` user's authorized_keys, and mounted-volume
#                    ownership, starts code-server (as `dev`, backgrounded,
#                    supplementary), then execs sshd in the foreground.
#                    Interactive work happens over SSH as `dev` or in the
#                    browser via code-server on :8443.
#   anything else,   the toolchain. Execs the argv docker hands us — the image
#   unset included   CMD when the caller named none — as `dev`, which is what
#                    the zephyr image did through `USER dev` and what every
#                    other layer of this repository still does.
#
set -Eeuo pipefail
IFS=$'\n\t'

HOSTKEY_DIR=/etc/ssh/hostkeys
AUTHORIZED_KEYS_FILE=/etc/devbox/authorized_keys
DEV_HOME=/home/dev
DEV_SSH_DIR="${DEV_HOME}/.ssh"
CODE_SERVER_SEED_EXT_DIR="${CODE_SERVER_SEED_EXTENSIONS:-/opt/code-server-extensions}"
DEV_CODE_SERVER_EXT_DIR="${DEV_HOME}/.local/share/code-server/extensions"
CODE_SERVER_LOG=/var/log/code-server.log

function log() { printf '[embedded-entrypoint] %s\n' "$*" >&2; }

# ERROR, not WARNING: every caller of this is a real defect or a missing
# credential, and a pod that reports Running while a declared service is
# absent is the failure mode this file used to have. The marker file is
# machine-readable state a probe or an operator can find.
DEGRADED_MARKER=/run/devbox-degraded
function degraded() {
  log "ERROR: $*"
  printf '%s\n' "$*" >>"${DEGRADED_MARKER}"
}

# -------- mode dispatch --------
# `devbox` is the ONLY value that reaches the pod preparation below. Anything
# else — unset included — is the toolchain, so a caller who names no mode gets
# exactly the behaviour the zephyr image had, and the pod opts IN.
#
# The DEFAULT arm and not the devbox arm is the one that must be safe by
# absence: an image whose entrypoint fell through to sshd whenever an env was
# missing would start a listener for every `docker run`.
#
# runuser is correct at euid 0 and WRONG below it — under `docker run --user
# dev` (which .ci/smoke.sh does) the binary is there and unprivileged, and it
# would refuse with "may not be used by non-root users", turning a working
# invocation into an error. The euid test is what makes both callers work.
#
# Plain `runuser -u dev --`, deliberately NOT `--preserve-environment`.
# Measured on ubuntu:24.04: it PRESERVES PATH and every exported variable, and
# sets HOME=/home/dev, USER=dev and LOGNAME=dev — which is the environment
# `USER dev` in a Dockerfile produces. --preserve-environment would keep
# HOME=/root, and the toolchain's caches and oh-my-zsh live in /home/dev.
if [[ "${GOPHERSYS_EMBEDDED_MODE:-}" != "devbox" ]]; then
  # An empty argv here would `exec` nothing and fall THROUGH to the pod
  # preparation, which is the silent wrong branch this dispatch exists to
  # prevent. The image declares CMD, so reaching this needs a caller that
  # replaced it with nothing. EXIT 2 — the same code the driver scripts of this
  # repository use for a caller error, and it is documented in README.md and in
  # .claude/rules/00-identity.md beside the steps below.
  if [[ $# -eq 0 ]]; then
    log "ERROR: no command to exec — the image CMD is /usr/bin/zsh and this caller replaced it with an empty argv"
    # The marker is the machine-readable half of every refusal in this file, so
    # this refusal owes one too. It does NOT go through degraded(): this is the
    # 1 refusal reachable as a NON-root caller — `docker run --user dev` is what
    # .ci/smoke.sh does — and there /run is not writable. degraded()'s
    # unguarded redirect would die under `set -e` and turn a NAMED refusal into
    # an unexplained failure, so the write is attempted and a failure to write
    # is reported rather than fatal. The log line above always lands; the marker
    # is the half that needs a writable /run.
    if ! printf '%s\n' "no command to exec in toolchain mode" >>"${DEGRADED_MARKER}" 2>/dev/null; then
      log "note: ${DEGRADED_MARKER} is not writable by uid $(id -u) — the line above is the whole record"
    fi
    exit 2
  fi
  if [[ "$(id -u)" -eq 0 ]]; then
    exec runuser -u dev -- "$@"
  fi
  exec "$@"
fi

# -------- host keys --------
# Generated once into the (PVC-backed) hostkey dir so the box keeps its
# SSH identity across pod restarts. Types match the HostKey lines in
# /etc/ssh/sshd_config.d/10-gophersys-devbox.conf.
mkdir -p "${HOSTKEY_DIR}"
chmod 0755 "${HOSTKEY_DIR}"
for type in ed25519 rsa; do
  key="${HOSTKEY_DIR}/ssh_host_${type}_key"
  if [[ ! -f "${key}" ]]; then
    log "generating ${type} host key"
    ssh-keygen -q -N '' -t "${type}" -f "${key}"
  fi
done

# -------- mounted-volume ownership --------
# A fresh PVC arrives root-owned; hand the mountpoint to dev. Deliberately
# NON-recursive: recursing into a populated persistent homedir on every
# boot is slow and can trample intentional ownership.
for dir in "${DEV_HOME}" /workspace; do
  [[ -d "${dir}" ]] || continue
  if [[ "$(stat -c '%u' "${dir}")" == "0" ]]; then
    log "chown ${dir} -> dev:dev (mountpoint only)"
    chown dev:dev "${dir}"
  fi
  # local-path PVCs mount with mode 0777; sshd StrictModes then refuses
  # authorized_keys ("bad ownership or modes for directory /home/dev").
  # Normalize the mountpoint mode every boot — cheap and idempotent.
  chmod 0755 "${dir}"
done

# -------- authorized_keys --------
# DEVBOX_AUTHORIZED_KEYS (env, e.g. from a k8s Secret) wins; otherwise a
# mounted file at /etc/devbox/authorized_keys. If neither is present the
# existing ~/.ssh/authorized_keys (persistent home) is left as-is.
keys=""
if [[ -n "${DEVBOX_AUTHORIZED_KEYS:-}" ]]; then
  log "installing authorized_keys from DEVBOX_AUTHORIZED_KEYS"
  keys="${DEVBOX_AUTHORIZED_KEYS}"
elif [[ -f "${AUTHORIZED_KEYS_FILE}" ]]; then
  log "installing authorized_keys from ${AUTHORIZED_KEYS_FILE}"
  keys="$(cat "${AUTHORIZED_KEYS_FILE}")"
fi
if [[ -n "${keys}" ]]; then
  mkdir -p "${DEV_SSH_DIR}"
  printf '%s\n' "${keys}" > "${DEV_SSH_DIR}/authorized_keys"
  chown -R dev:dev "${DEV_SSH_DIR}"
  chmod 0700 "${DEV_SSH_DIR}"
  chmod 0600 "${DEV_SSH_DIR}/authorized_keys"
elif [[ ! -f "${DEV_SSH_DIR}/authorized_keys" ]]; then
  degraded "no authorized keys (DEVBOX_AUTHORIZED_KEYS or ${AUTHORIZED_KEYS_FILE}) — sshd will boot and refuse every login"
fi

# -------- mcu slot symlinks --------
# On the k8s node udev creates /dev/mcu-slot-N, but the pod only receives
# hostPath mounts of /dev/serial and /dev/bus/usb — symlinks at the node's
# /dev root do not propagate into the container. Recreate them here from
# the by-path tree: slot N == guest USB port N == physical hub slot N.
# Best-effort by design: outside k8s (plain local devcontainer) these
# paths don't exist, and that must not abort the boot.
for n in 1 2 3 4 5 6; do
  for candidate in /dev/serial/by-path/*-usb-0:"${n}":*; do
    if [[ -e "${candidate}" ]]; then
      if ln -sf "${candidate}" "/dev/mcu-slot-${n}" 2>/dev/null; then
        log "linked /dev/mcu-slot-${n} -> ${candidate}"
      else
        log "WARNING: could not link /dev/mcu-slot-${n}"
      fi
      break
    fi
  done
done

# -------- code-server --------
# Browser VS Code for the workspaces web UI, served alongside sshd.
#
# AUTH IS REQUIRED BY DEFAULT. The account code-server runs as holds
# passwordless sudo, so a reachable unauthenticated :8443 is root on the
# pod for any peer the network lets through — and the network boundary is
# a NetworkPolicy in ANOTHER repository, which this file cannot see and
# must not trust as the only wall. Two sanctioned modes:
#
#   DEVBOX_CODE_SERVER_HASHED_PASSWORD   argon2 hash (code-server's own
#       HASHED_PASSWORD contract); comes from a Secret via the pod env.
#   DEVBOX_CODE_SERVER_AUTH=none-behind-proxy   the operator's EXPLICIT,
#       named statement that an authenticating proxy owns :8443. The old
#       behaviour, opt-in instead of default.
#
# Neither set -> code-server does NOT start, and the refusal is an ERROR
# naming both knobs. sshd still runs: code-server is supplementary, and
# a missing credential must not take the primary service down — but it
# must never silently open either.
#
# Config and extensions live under the default XDG paths in /home/dev
# (~/.config/code-server, ~/.local/share/code-server), i.e. on the PVC,
# so settings and user-installed extensions survive pod restarts.
if command -v code-server >/dev/null 2>&1; then
  # Seed the baked-in extension set (clangd) onto a fresh home. The image
  # keeps it in /opt because the PVC mount masks anything installed into
  # /home/dev at build time. Done as dev so no root-owned dirs land in the
  # home; skipped once the user's extensions dir exists.
  if [[ -d "${CODE_SERVER_SEED_EXT_DIR}" ]] && [[ ! -d "${DEV_CODE_SERVER_EXT_DIR}" ]]; then
    log "seeding code-server extensions -> ${DEV_CODE_SERVER_EXT_DIR}"
    if ! runuser -u dev -- mkdir -p "${DEV_CODE_SERVER_EXT_DIR%/*}" \
      || ! runuser -u dev -- cp -a "${CODE_SERVER_SEED_EXT_DIR}" "${DEV_CODE_SERVER_EXT_DIR}"; then
      degraded "code-server extension seed failed — clangd IntelliSense absent until seeded by hand"
    fi
  fi
  code_server_args=()
  if [[ -n "${DEVBOX_CODE_SERVER_HASHED_PASSWORD:-}" ]]; then
    code_server_args=(--auth password)
    export HASHED_PASSWORD="${DEVBOX_CODE_SERVER_HASHED_PASSWORD}"
  elif [[ "${DEVBOX_CODE_SERVER_AUTH:-}" == "none-behind-proxy" ]]; then
    code_server_args=(--auth none)
    log "code-server auth: none — DEVBOX_CODE_SERVER_AUTH=none-behind-proxy declares the proxy owns :8443"
  else
    degraded "code-server NOT STARTED: set DEVBOX_CODE_SERVER_HASHED_PASSWORD or DEVBOX_CODE_SERVER_AUTH=none-behind-proxy"
  fi
  if [[ ${#code_server_args[@]} -gt 0 ]]; then
    # cwd is already /workspace (image WORKDIR); the trailing folder arg
    # makes the browser UI open it by default. The supervisor loop exists
    # because a bare backgrounded child dies silently: every exit is
    # logged loudly and restarted with a fixed pause, and sshd never
    # inherits the failure.
    log "starting code-server on :8443 (log: ${CODE_SERVER_LOG})"
    (
      # The subshell inherits set -e, under which a non-zero code-server
      # exit would kill this loop at the exact moment it exists for — the
      # first probe of this file proved it. `|| rc=$?` keeps the failing
      # exit inside a condition context, so the loop survives to restart.
      while true; do
        rc=0
        runuser -u dev --preserve-environment -- code-server \
          --bind-addr 0.0.0.0:8443 \
          "${code_server_args[@]}" \
          --disable-telemetry \
          /workspace \
          >>"${CODE_SERVER_LOG}" 2>&1 || rc=$?
        log "ERROR: code-server exited rc=${rc} — restarting in 10s (log: ${CODE_SERVER_LOG})"
        sleep 10
      done
    ) &
  fi
else
  degraded "code-server not installed — the image is defective, this binary is baked in at build time"
fi

# -------- sshd --------
mkdir -p /run/sshd
log "starting sshd"
exec /usr/sbin/sshd -D -e
