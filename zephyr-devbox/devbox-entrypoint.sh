#!/usr/bin/env bash
#
# devbox-entrypoint.sh — PID 1 for the zephyr-devbox pod.
#
# Runs as root: prepares persistent SSH host keys, the `dev` user's
# authorized_keys, and mounted-volume ownership, then execs sshd in the
# foreground. Interactive work happens over SSH as `dev`.
#
# Pass-through: any argv (e.g. `docker run <image> zsh`, or a devcontainer
# override command) is exec'd instead of sshd, preserving local-devcontainer
# parity with the other image layers.
#
set -Eeuo pipefail
IFS=$'\n\t'

HOSTKEY_DIR=/etc/ssh/hostkeys
AUTHORIZED_KEYS_FILE=/etc/devbox/authorized_keys
DEV_HOME=/home/dev
DEV_SSH_DIR="${DEV_HOME}/.ssh"

function log() { printf '[devbox-entrypoint] %s\n' "$*" >&2; }

# -------- argv pass-through --------
if [[ $# -gt 0 ]]; then
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
  log "WARNING: no authorized keys (DEVBOX_AUTHORIZED_KEYS or ${AUTHORIZED_KEYS_FILE}) — ssh logins will fail"
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

# -------- sshd --------
mkdir -p /run/sshd
log "starting sshd"
exec /usr/sbin/sshd -D -e
