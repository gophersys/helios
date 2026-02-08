# Concord OS — Yocto Build System

Custom TorizonOS image for the **CoreKinect MTIB** (Modular Test Interface Board) running on a Toradex Verdin iMX8M Mini.

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

### 1. Open in Dev Container

Open this repository in VS Code and use **Reopen in Container** (or run the `.devcontainer/start.sh` script manually). The container initialises the Yocto environment, syncs repos, and accepts the Freescale EULA on first run.

### 2. Place Secrets (first time only)

Before building, place provisioning secrets in `meta-corekinect/secrets/`:

```
meta-corekinect/secrets/
├── corekinect-root-ca.crt      ← CoreKinect Root CA 2024
├── corekinect-sub-ca.crt       ← CoreKinect Sub CA 2024 (WINSRV01)
├── k3s-server-url              ← e.g. "https://10.4.45.10:6443"
└── k3s-token                   ← node join token from control plane
```

See [`meta-corekinect/secrets/README.md`](meta-corekinect/secrets/README.md) for details on obtaining each file. These are `.gitignore`d and must be provided manually.

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

## What Gets Baked In

The `corekinect-provisioning` recipe handles all node provisioning at build time, producing a **flash-and-forget** image:

| Feature | Details |
|---------|---------|
| **Password** | `torizon` / `corekinect` — no first-login change prompt |
| **CA Certificates** | CoreKinect Root + Sub CA installed and trusted system-wide |
| **Docker Registry** | `containers.ad.corekinect.com` trusted via CA bundle in `/etc/docker/certs.d/` |
| **K3s Agent** | Pre-configured with server URL, join token, and registry mirror |
| **K3s Logs** | Volatile log directories created via `tmpfiles.d` |

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
│       └── k3s_git.bbappend               ← K3s BIN_PREFIX fix for OSTree
├── recipes-images/
│   └── images/
│       ├── corekinect-base.inc
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
│           ├── k3s-registries.yaml
│           └── k3s-logs.conf
├── recipes-utils/
│   ├── btop/
│   │   └── btop_1.4.5.bb                  ← System monitor
│   └── iperf3/
│       └── iperf3_3.20.bb                  ← Network performance tool
└── secrets/                                ← .gitignored provisioning secrets
    └── README.md
```

## Device Tree Overlays

Custom overlays for the MTIB hardware:

| Overlay | Purpose |
|---------|---------|
| `ina219-overlay.dtbo` | INA219 current sensors + ADS1115 ADCs + LIS2DE12 accel on I2C4 |
| `mtib-v2-overlay.dtbo` | BME280 + TCA9534A GPIO expander + AT24C02C EEPROM (Rev 1.2) |
| `no-i2s.dtbo` | Disables SAI2 to free pins for GPIO |
| `no-i2c.dtbo` | Disables I2C4 to free pins for GPIO |
| `usb.dtbo` | USB1/USB2 full-speed configuration |

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
| btop    | 1.4.5   |
| iperf3  | 3.20    |
| K3s     | latest from meta-virtualization |

## Dev Container Environment

Configuration lives in `.devcontainer/`:

| File | Purpose |
|------|---------|
| `Dockerfile` | Build environment based on `crops/poky:debian-11` |
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

## Verification After Flashing

1. SSH in with `torizon` / `corekinect` — no password change prompt
2. `docker pull containers.ad.corekinect.com/concord-devcontainer-mtib:latest` — no cert errors
3. `sudo k3s-agent` joins the cluster automatically
4. `btop --version` shows 1.4.5
5. `iperf3 --version` shows 3.20
