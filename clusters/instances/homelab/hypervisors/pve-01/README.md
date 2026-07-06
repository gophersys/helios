# pve-01 (ThinkPad P1) hypervisor bootstrap

pve-01 is one of the three Proxmox hosts under the homelab cluster — a **laptop**,
so it needs non-default host config, and it hosts the USB-passthrough VM (925 =
k3s-w-4). These steps aren't managed by any reconciler; they live here as an
idempotent script (`docs/debt-register.md`, D3).

> The other two hypervisors (pve-00 MS-A2, pve-03 Yoga) run stock and need no
> such bootstrap, which is why only pve-01 has a directory here.

## Run
```sh
scp -r pve-01 root@<pve-01>:/tmp/ && ssh root@<pve-01> '/tmp/pve-01/bootstrap.sh'
```

## Applied automatically (idempotent, file-based)
1. **No-suspend** (`logind.conf.d/99-hypervisor-no-sleep.conf` + masked
   `sleep/suspend/hibernate/hybrid-sleep` targets): a laptop hypervisor must not
   suspend on lid-close — it would take its VMs (incl. a control-plane node) down.
2. **IP forwarding** (`sysctl.d/99-tailscale-router.conf`): pve-01 is the
   Tailscale subnet router advertising `10.168.0.0/24`, so off-tailnet clients
   (and this repo's operators) can reach cluster IPs.

## Manual one-time (side effects — the script prints, does not run these)
- **USB passthrough** into VM 925 by physical hub-port path (stable across
  reboots/replug, distinguishes identical boards):
  ```sh
  qm set 925 -usb0 host=3-1.1 -usb1 host=3-1.2 -usb2 host=3-1.3 \
             -usb3 host=3-1.4.1 -usb4 host=3-1.4.2 -usb5 host=3-1.4.3
  ```
- **Tailscale subnet router**:
  ```sh
  tailscale set --advertise-routes=10.168.0.0/24
  ```
  (The route is auto-approved by the tailnet ACL `autoApprovers`.)
