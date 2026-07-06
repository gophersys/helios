#!/usr/bin/env bash
# Idempotent host bootstrap for k3s-w-4 — the USB-passthrough embedded node.
# Re-runnable; run as root on the node:  sudo ./bootstrap.sh
#
# Captures the changes made by hand on 2026-07-06 (docs/debt-register.md, D3).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

# 1. USB-serial kernel modules. The stock Ubuntu cloud kernel ships without
#    cp210x/cdc_acm; `linux-generic` pulls the matching modules-extra and keeps
#    future kernel upgrades covered (the 2026-07-06 reboot broke USB because
#    only modules-extra for the OLD kernel was installed).
if ! dpkg -s linux-generic >/dev/null 2>&1; then
	DEBIAN_FRONTEND=noninteractive apt-get update -q
	DEBIAN_FRONTEND=noninteractive apt-get install -y \
		linux-generic "linux-modules-extra-$(uname -r)"
fi
for m in cp210x cdc_acm ch341 ftdi_sio; do
	modprobe "$m" 2>/dev/null || true
done

# 2. QEMU guest agent — graceful Proxmox shutdown/quiesce. The cluster expects
#    it (identity.yaml) but it was missing on the k3s VMs.
if ! dpkg -s qemu-guest-agent >/dev/null 2>&1; then
	DEBIAN_FRONTEND=noninteractive apt-get install -y qemu-guest-agent
fi
systemctl enable --now qemu-guest-agent 2>/dev/null || \
	systemctl start qemu-guest-agent || true

# 3. Stable per-slot /dev/mcu-slot-N symlinks for the passed-through boards.
install -m 0644 "${HERE}/99-mcu-slots.rules" /etc/udev/rules.d/99-mcu-slots.rules
udevadm control --reload
udevadm trigger --subsystem-match=tty --subsystem-match=usb --action=add

echo "k3s-w-4 bootstrap complete."
