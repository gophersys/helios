# pve-01 (ThinkPad P1) hypervisor bootstrap

pve-01 is 1 of the 3 Proxmox hosts under the homelab cluster. It is a **laptop**,
so it needs a host configuration that is not the default. It also hosts the VM
with the USB passthrough (925 = k3s-w-4). No reconciler manages these steps, so
they live here as an idempotent script (`docs/debt-register.md`, D3).

> The other 2 hypervisors (pve-00 MS-A2 and pve-03 Yoga) run the standard
> configuration and need no such bootstrap. That is why only pve-01 has a
> directory here.

## Run
```sh
scp -r pve-01 root@<pve-01>:/tmp/ && ssh root@<pve-01> '/tmp/pve-01/bootstrap.sh'
```

## Applied automatically, idempotent, based on files
1. **No suspend** (`logind.conf.d/99-hypervisor-no-sleep.conf` plus the masked
   `sleep`, `suspend`, `hibernate` and `hybrid-sleep` targets). A hypervisor on a
   laptop must not suspend when somebody closes the lid, because that would stop
   its VMs, and one of them is a control-plane node.
2. **IP forwarding** (`sysctl.d/99-tailscale-router.conf`). pve-01 is the
   Tailscale subnet router, and it advertises `10.168.0.0/24`. A client outside
   the tailnet, and an operator of this repo, can then reach a cluster IP.

## One-time manual steps — the script prints these; it does not run them
- **USB passthrough** into VM 925, by the physical path of the hub port. That
  path is stable across a reboot and a replug, and it separates 2 identical
  boards:
  ```sh
  qm set 925 -usb0 host=3-1.1 -usb1 host=3-1.2 -usb2 host=3-1.3 \
             -usb3 host=3-1.4.1 -usb4 host=3-1.4.2 -usb5 host=3-1.4.3
  ```
- **Tailscale subnet router**:
  ```sh
  tailscale set --advertise-routes=10.168.0.0/24
  ```
  The `autoApprovers` block of the tailnet ACL approves the route automatically.
