# k3s-w-4 host bootstrap

k3s-w-4 is the embedded and USB node. QEMU passes the microcontrollers into this
VM from pve-01, and the pods flash them. The host-level steps below make that
work. No in-cluster reconciler manages them, so they live here as an idempotent
script. See `docs/debt-register.md`, D3.

## Run
```sh
scp -r bootstrap ubuntu@<k3s-w-4>:/tmp/ && ssh ubuntu@<k3s-w-4> 'sudo /tmp/bootstrap/bootstrap.sh'
```

## What it does — every step is idempotent
1. It installs `linux-generic` and `linux-modules-extra-$(uname -r)`, so that the
   USB-serial drivers (`cp210x`, `cdc_acm`, `ch341` and `ftdi_sio`) exist and
   survive a kernel upgrade. It then loads them.
2. It installs `qemu-guest-agent` and enables it.
3. It installs `99-mcu-slots.rules` and reloads udev. That gives stable
   `/dev/mcu-slot-N` symlinks, keyed to the physical slot of the hub, where slot
   N is guest USB port N.

## What it depends on — done on the hypervisor; see ../../hypervisors/pve-01/
The USB devices appear in this VM only after pve-01 passes them through with
`qm set 925 -usbN host=3-1.x`. Without that step the symlinks have no device to
point at.
