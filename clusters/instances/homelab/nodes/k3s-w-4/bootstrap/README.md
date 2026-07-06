# k3s-w-4 host bootstrap

k3s-w-4 is the embedded/USB node: microcontrollers are QEMU-passed into this VM
from pve-01, and pods flash them. These host-level steps make that work and are
**not** managed by any in-cluster reconciler, so they live here as an idempotent
script (see `docs/debt-register.md`, D3).

## Run
```sh
scp -r bootstrap ubuntu@<k3s-w-4>:/tmp/ && ssh ubuntu@<k3s-w-4> 'sudo /tmp/bootstrap/bootstrap.sh'
```

## What it does (all idempotent)
1. Installs `linux-generic` + `linux-modules-extra-$(uname -r)` so USB-serial
   drivers (`cp210x`, `cdc_acm`, `ch341`, `ftdi_sio`) exist and survive kernel
   upgrades, then loads them.
2. Installs + enables `qemu-guest-agent`.
3. Installs `99-mcu-slots.rules` and reloads udev — stable `/dev/mcu-slot-N`
   symlinks keyed to the physical hub slot (slot N == guest USB port N).

## Depends on (done on the hypervisor, see ../../hypervisors/pve-01/)
The USB devices only appear in this VM after pve-01 passes them through
(`qm set 925 -usbN host=3-1.x`). Without that, the symlinks have nothing to
bind to.
