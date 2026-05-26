# Concord OS — Yocto Build System

Custom TorizonOS image for the **CoreKinect MTIB** (Modular Test Interface Board) running on a Toradex Verdin iMX8M Mini.

## What this is

Concord OS turns a Verdin iMX8M Mini SoM into a node in the **Concord K3s cluster**. The MTIB hosts an MTIB gRPC server that drives validation and manufacturing fixtures over GPIO / I²C / UART / USB / SWD. Every device gets the same image and on first boot it joins the cluster automatically — **flash-and-forget**, no per-device setup.

```
┌──────────── Toradex BSP (scarthgap-7.x.y) ────────────┐
│  TorizonOS-docker (OSTree, read-only /usr)            │
│  + meta-virtualization (K3s, Docker)                  │
└───────────────────────────────────────────────────────┘
                          ↑ inherits
┌──────────── meta-corekinect (this repo) ──────────────┐
│  Image recipe: corekinect-mtib.bb                     │
│  + DTS overlays for MTIB hardware                     │
│  + Provisioning (CA certs, K3s creds, password)       │
│  + btop / iperf3 utilities                            │
└───────────────────────────────────────────────────────┘
                          ↓ produces
        TEZI image → Toradex Easy Installer → device
                          ↓ first boot
                  joins Concord K3s cluster
```

## References

- [Build TorizonCore from source with Yocto/OE](https://developer.toradex.com/torizon/in-depth/build-torizoncore-from-source-with-yocto-projectopenembedded/#manifest-file)
- [Custom meta-layers, recipes and images](https://developer.toradex.com/linux-bsp/os-development/build-yocto/custom-meta-layers-recipes-and-images-in-yocto-project-hello-world-examples/#create-a-meta-layer)
- [Custom username and password on TorizonOS](https://community.toradex.com/t/build-torizon-os-with-custom-username-and-password/20745)

## Machine Requirements

| Resource | Minimum |
|----------|---------|
| Memory   | 24 GB   |
| Disk     | 100 GB  |
| CPU      | 8 cores |

## Quick Start

### 1. Place Secrets (first time only)

`start.sh` hard-fails on missing secrets, so drop these in `meta-corekinect/secrets/` **before** opening the dev container:

```
meta-corekinect/secrets/
├── corekinect-root-ca.crt      ← CoreKinect Root CA 2024
├── corekinect-sub-ca.crt       ← CoreKinect Sub CA 2024 (WINSRV01)
├── k3s-server-url              ← e.g. "https://10.4.45.10:6443"
└── k3s-token                   ← node join token from control plane
```

See [`meta-corekinect/secrets/README.md`](meta-corekinect/secrets/README.md) for how to obtain each file. They are `.gitignore`d and must be provided manually. If any of the four are missing or empty, container startup aborts with a list of what's missing.

### 2. Open in Dev Container

Open this repository in VS Code and use **Reopen in Container** (or run the `.devcontainer/start.sh` script manually). The container initialises the Yocto environment, syncs repos, accepts the Freescale EULA, and registers `meta-corekinect` with bitbake.

#### Working from the umbrella `corekinect/work` repo

This repo is consumed as a git submodule of the umbrella workspace (`work/concord/concord-os-yocto`). When that's the case, the submodule's `.git` is a pointer file (`gitdir: ../../.git/modules/concord/concord-os-yocto`) whose target lives **outside** the workspace bind mount. On top of that, the gitdir's own `config` carries a relative `core.worktree` (`../../../../concord/concord-os-yocto`) that was computed against the umbrella's directory layout. To make both relative paths resolve identically inside the container, the devcontainer mirrors that layout:

| Host (umbrella)                                  | Container                                              |
|--------------------------------------------------|--------------------------------------------------------|
| `<umbrella>/concord/concord-os-yocto/`           | `/workspaces/concord/concord-os-yocto/` (workspace)    |
| `<umbrella>/.git/modules/concord/concord-os-yocto/` | `/workspaces/.git/modules/concord/concord-os-yocto/` (bind-mounted gitdir) |

Both are set in `.devcontainer/devcontainer.json` (`workspaceMount` + a second bind mount). With this in place, every git invocation inside the container — including the ones bitbake fetchers run for AUTOREV recipes (`u-boot-toradex`, `linux-toradex-upstream`) — finds the gitdir and the worktree exactly as it would on the host. No env vars or wrappers are required.

A standalone clone of this repo (no umbrella) has a real `.git` directory and never consults the umbrella mount — the second bind mount just lands as an empty directory inside the container and is otherwise inert.

### 3. Build the Image

```bash
# Inside the dev container:
bitbake corekinect-mtib
```

Output TEZI image lands in:
```
torizon/build/tmp/deploy/images/verdin-imx8mm/
```

### 4. Force Rebuild

```bash
bitbake -C do_image corekinect-mtib
```

## How the build works

1. `repo init` (run by `start.sh`) syncs the Toradex manifest at `BRANCH=scarthgap-7.x.y` — this pulls `poky`, `meta-openembedded`, `meta-toradex-*`, `meta-virtualization`, and overlays `meta-corekinect` from this repo.
2. `bitbake corekinect-mtib` walks the recipe graph, cross-compiles every package for `verdin-imx8mm`, assembles an OSTree commit, and bundles a TEZI installer.
3. The output is `CoreKinect-MTIB-Tezi-*.tar` under `torizon/build/tmp/deploy/images/verdin-imx8mm/`. Flash it via Toradex Easy Installer (USB recovery mode or the Easy Installer web UI on a unit already running TorizonOS).

A cold build takes about an hour on 8 cores / 24 GB RAM. Incremental builds reuse the `sstate-cache` and complete in minutes.

## Editing the image — what to change for what

| Goal | Edit |
|------|------|
| Add a Linux package to the image | `IMAGE_INSTALL:append` in `recipes-images/images/corekinect-mtib.bb` |
| Add a kernel config option | new `.cfg` fragment under `recipes-kernel/linux/linux-toradex/`, listed in `KERNEL_CONFIG_FRAGMENTS` of the bbappend |
| Auto-load a kernel module at boot | `KERNEL_MODULE_AUTOLOAD` in `linux-toradex_%.bbappend` |
| Add a device-tree overlay | drop a `.dts` in `recipes-kernel/linux/device-tree-overlays/`, then add it to **both** lists in `device-tree-overlays_%.bbappend` (`CUSTOM_OVERLAYS_SOURCE` and `CUSTOM_OVERLAYS_BINARY`) plus the `SRC_URI` |
| Bake a config / script onto the rootfs | drop the file under `recipes-security/corekinect-provisioning/files/`, install it from `corekinect-provisioning.bb` |
| Package your own binary | new recipe at `recipes-utils/<name>/<name>_<version>.bb` (use `btop_1.4.6.bb` as a template) |
| Tune Docker daemon | `recipes-containers/docker/docker-moby_%.bbappend` |
| Tune K3s agent | `recipes-containers/k3s/k3s_git.bbappend` and/or files in `corekinect-provisioning/files/` |

## What Gets Baked In

The `corekinect-provisioning` recipe handles all node provisioning at build time, producing a **flash-and-forget** image:

| Feature | Details |
|---------|---------|
| **Password** | `torizon` / `corekinect` — no first-login change prompt |
| **CA Certificates** | CoreKinect Root + Sub CA installed and trusted system-wide |
| **Docker Registry** | `containers.ad.corekinect.com` trusted via CA bundle in `/etc/docker/certs.d/` |
| **K3s Agent** | Pre-configured with server URL, join token, and registry mirror |
| **K3s Logs** | Volatile log directories created via `tmpfiles.d` |

## First-boot lifecycle

What happens between flashing and the node appearing in `kubectl get nodes`:

1. systemd boots from the OSTree commit (rootfs is read-only).
2. `corekinect-password.service` runs once → sets the `torizon` user password to `corekinect`.
3. CA trust is already populated (certs appended to `/etc/ssl/certs/ca-certificates.crt` and hashed into `/etc/ssl/certs/` at build time) — no runtime cert install.
4. Docker registry `containers.ad.corekinect.com` is trusted via `/etc/docker/certs.d/`.
5. `k3s-agent.service` reads the baked-in server URL + join token, registers with the control plane, pulls workloads.
6. Node visible in `kubectl get nodes` typically within ~30 s.

Everything above is set at **build time** from `meta-corekinect/secrets/`. There is no runtime configuration step on the device.

## Custom Layer Structure

```
meta-corekinect/
├── classes/
│   └── image-preload-container.bbclass
├── conf/
│   ├── layer.conf
│   └── machine/
│       └── verdin-imx8mm-extra.conf
├── recipes-containers/
│   ├── docker/
│   │   └── docker-moby_%.bbappend          ← Docker daemon config (logging)
│   └── k3s/
│       └── k3s_git.bbappend                ← K3s BIN_PREFIX fix for OSTree
├── recipes-images/
│   └── images/
│       └── corekinect-mtib.bb              ← Main image recipe
├── recipes-kernel/
│   └── linux/
│       ├── device-tree-overlays/           ← Custom DTS overlays
│       ├── device-tree-overlays_%.bbappend
│       ├── linux-toradex/
│       │   └── iio.cfg                     ← IIO kernel config fragment
│       └── linux-toradex_%.bbappend
├── recipes-security/
│   └── corekinect-provisioning/
│       ├── corekinect-provisioning.bb      ← Provisioning recipe
│       └── files/
│           ├── corekinect-password.service ← Firstboot password unit
│           ├── corekinect-set-password.sh  ← Sets torizon password
│           ├── k3s-registries.yaml
│           └── k3s-logs.conf
├── recipes-utils/
│   ├── btop/
│   │   └── btop_1.4.6.bb                  ← System monitor
│   └── iperf3/
│       └── iperf3_3.21.bb                  ← Network performance tool
└── secrets/                                ← .gitignored provisioning secrets
    └── README.md
```

## Device Tree Overlays

Custom overlays for the MTIB hardware:

| Overlay | Purpose |
|---------|---------|
| `ina219-overlay.dtbo` | INA219 current sensors + ADS1115 ADCs + LIS2DE12 accel on I²C4 |
| `mtib-v2-overlay.dtbo` | BME280 + TCA9534A GPIO expander + AT24C02C EEPROM (Rev 1.2) |
| `no-i2s.dtbo` | Disables SAI2 to free pins for GPIO |
| `no-i2c.dtbo` | Disables I²C4 to free pins for GPIO |
| `usb.dtbo` | Forces USB1/USB2 to full-speed (USB 1.1, 12 Mbps) — no high-speed/USB 2.0 support |

## Finding Device Tree Sources

After a build, the kernel DTS/DTSI files can be found at:

```bash
find torizon/build/tmp/work-shared/verdin-imx8mm/kernel-source -name "imx8mm-verdin*.dts"
find torizon/build/tmp/work-shared/verdin-imx8mm/kernel-source -name "imx8mm-verdin*.dtsi"
```

Key files:
- `imx8mm-verdin.dtsi` — Base SoM configuration
- `imx8mm-verdin-wifi.dtsi` — WiFi-specific configuration
- `imx8mm-verdin-mallow.dtsi` — Carrier board (Mallow) configuration

## Package Versions

| Package | Version |
|---------|---------|
| btop    | 1.4.6   |
| iperf3  | 3.21    |
| K3s     | latest from meta-virtualization |

## Dev Container Environment

Configuration lives in `.devcontainer/`:

| File | Purpose |
|------|---------|
| `Dockerfile` | Build environment based on `crops/poky:debian-12` |
| `devcontainer.json` | VS Code dev container config |
| `start.sh` | Repo init, env setup, EULA acceptance |
| `.env` | Machine, distro, branch variables |
| `.env.example` | Template for `.env` |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MACHINE` | `verdin-imx8mm` | Target hardware |
| `IMAGE` | `torizon-docker` | Base image |
| `BRANCH` | `scarthgap-7.x.y` | Toradex manifest branch |
| `DISTRO` | `torizon` | Distribution |
| `BDDIR` | `build` | Build directory name |

## Iteration loop

| Change | Fastest rebuild |
|--------|-----------------|
| Edit `IMAGE_INSTALL` / image recipe | `bitbake corekinect-mtib` |
| Edit a single package recipe (e.g. `btop`) | `bitbake -c cleansstate btop && bitbake corekinect-mtib` |
| Edit a DTS overlay | `bitbake -c cleansstate device-tree-overlays && bitbake corekinect-mtib`, **or** `./ctl.sh compile && ./ctl.sh deploy` to hot-swap on a running device (currently wired for `ina219-overlay` only) |
| Edit a kernel `.cfg` fragment | `bitbake -c cleansstate virtual/kernel && bitbake corekinect-mtib` |
| Edit provisioning files (CA, K3s configs) | `bitbake -c cleansstate corekinect-provisioning && bitbake corekinect-mtib` |
| Force a fresh image bundle | `bitbake -C do_image corekinect-mtib` |

## Verification After Flashing

1. SSH in with `torizon` / `corekinect` — no password change prompt
2. `docker pull containers.ad.corekinect.com/concord-devcontainer-mtib:latest` — no cert errors
3. `sudo k3s-agent` joins the cluster automatically
4. `btop --version` shows 1.4.6
5. `iperf3 --version` shows 3.21

## Troubleshooting

- **`ACCEPT_FSL_EULA` not set** — re-run `.devcontainer/start.sh`. The EULA prompt fires only if `torizon/build/conf/local.conf` doesn't already have the accept line.
- **`repo sync` hangs or fails partway** — `cd torizon && repo sync -j1` drops parallelism and surfaces the failing fetch.
- **`bitbake: command not found`** — the build env isn't sourced for this shell. `cd torizon && source setup-environment build`.
- **K3s agent not joining the cluster** — on the device: `journalctl -u k3s-agent`. Most common cause: the `k3s-server-url` or `k3s-token` files were missing or stale at **build time**. Fix the secrets, rebuild, reflash.
- **"No space left on device" during build** — the build dir needs ~80 GB free; check `df -h "$WORKDIR"` (the `WORKDIR` env var resolves to the active build root inside the container).
- **Verify a DTS overlay without a full kernel rebuild** — preprocess and compile by hand: see `ctl.sh compile` for the canonical `cpp` + `dtc` invocation.
