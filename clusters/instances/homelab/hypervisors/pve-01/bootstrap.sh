#!/usr/bin/env bash
# Idempotent host bootstrap for pve-01 (ThinkPad P1 — Proxmox hypervisor).
# Re-runnable; run as root on the host:  ./bootstrap.sh
#
# pve-01 is a LAPTOP acting as a hypervisor, so it needs two things stock
# Proxmox doesn't do, plus it hosts the USB-passthrough VM (see the manual
# section). Captures changes made by hand on 2026-07-06 (docs/debt-register.md,
# D3). File-based config is applied here; live device/tailnet operations are
# documented below (not auto-run — they have side effects on running VMs).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

# 1. Never suspend the hypervisor — a laptop that suspends on lid-close would
#    kill every VM it hosts, including a control-plane node.
install -D -m 0644 "${HERE}/logind.conf.d/99-hypervisor-no-sleep.conf" \
	/etc/systemd/logind.conf.d/99-hypervisor-no-sleep.conf
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
systemctl restart systemd-logind

# 2. IP forwarding — pve-01 is the Tailscale subnet router for 10.168.0.0/24.
install -D -m 0644 "${HERE}/sysctl.d/99-tailscale-router.conf" \
	/etc/sysctl.d/99-tailscale-router.conf
sysctl -p /etc/sysctl.d/99-tailscale-router.conf

echo "pve-01 file config applied."
echo
echo "MANUAL one-time operations (side effects on live VM/tailnet — run by hand):"
echo "  # USB passthrough of the embedded hub ports into VM 925 (k3s-w-4):"
echo "  qm set 925 -usb0 host=3-1.1 -usb1 host=3-1.2 -usb2 host=3-1.3 \\"
echo "             -usb3 host=3-1.4.1 -usb4 host=3-1.4.2 -usb5 host=3-1.4.3"
echo "  # Advertise the LAN subnet over Tailscale (auto-approved by ACL):"
echo "  tailscale set --advertise-routes=10.168.0.0/24"
