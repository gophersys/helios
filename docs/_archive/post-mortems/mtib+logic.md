# Post-Mortem: Saleae Logic8 on MTIB (ARM64)

**Date:** 2026-02-12
**Device:** Saleae Logic8 (USB ID: 21a9:1004)
**Platform:** Verdin iMX8MM (ARM64, 2GB RAM, TorizonCore)
**Outcome:** Not viable for production use

---

## Executive Summary

We investigated running Saleae Logic 2 on the MTIB ARM64 edge device to capture UART traffic for automated testing. Two approaches were evaluated:

1. **Logic 2 via QEMU x86_64 emulation** - Works but impractical (resource constraints)
2. **sigrok-cli native ARM64** - Device not supported

Neither approach is viable for production deployment on the current hardware.

---

## Approach 1: Logic 2 + QEMU Emulation

### What We Tried

Run the official Saleae Logic 2 software (x86_64 Electron app) inside a Docker container using QEMU user-mode emulation on the ARM64 host.

### Findings

#### QEMU Version Matters

| QEMU Version | Source | Result |
|--------------|--------|--------|
| 10.0.4 | tonistiigi/binfmt:latest | **Broken** - argv corruption bug |
| 7.2.22 | Debian Bookworm | **Works** - arguments pass correctly |

**Critical Bug:** QEMU 10.x has a regression where command-line arguments are corrupted when passed through binfmt_misc. Commands like `ls /tmp` would ignore the `/tmp` argument entirely. This manifested as:
- `apt-get install -y wget` → "Invalid operation wget"
- `echo hello world` → no output
- Shell scripts treating arguments as filenames

**Root Cause:** The TorizonCore OS image shipped with `/usr/bin/qemu-x86_64-static` that was itself an **x86_64 binary** (should be ARM64). This caused a recursive execution loop.

#### Resource Constraints

Even with working QEMU 7.2, Logic 2 is impractical:

| Resource | Available | Logic 2 Requirement |
|----------|-----------|---------------------|
| RAM | 2GB total | ~1.2GB under QEMU |
| CPU | 4x Cortex-A53 | Electron + QEMU = high load |
| Startup time | - | ~30-60 seconds |

The device has only **1.9GB usable RAM**. Logic 2 (Electron app) consumed 1.2GB+ under QEMU emulation, leaving insufficient headroom for the MTIB server and other processes.

#### Container Stability

Containers running Logic 2 under QEMU frequently crashed:
- OOM kills when memory pressure increased
- Zombie processes from Electron's multi-process architecture
- Exit code 255 without clear error messages

### What Would Be Needed

To make Logic 2 work on ARM64 MTIB:
1. **More RAM** - Minimum 4GB recommended
2. **Correct QEMU binary** - ARM64-native QEMU 7.2.x (not 10.x)
3. **Persistent binfmt_misc** - OS must mount and register at boot
4. **Larger shm** - Electron needs adequate shared memory

---

## Approach 2: sigrok-cli (Native ARM64)

### What We Tried

Use sigrok-cli with fx2lafw firmware as a lightweight, native ARM64 alternative to Logic 2.

### Findings

**The Saleae Logic8 (21a9:1004) is not supported by sigrok.**

| Saleae Device | USB ID | sigrok Status |
|---------------|--------|---------------|
| Logic (original) | 21a9:1001 | Supported (fx2lafw) |
| Logic16 | 21a9:1002 | Supported |
| Logic Pro 8 | - | Experimental |
| **Logic8** | **21a9:1004** | **Planned (not implemented)** |

The Logic8 is a newer generation device that sigrok hasn't reverse-engineered yet. The sigrok wiki explicitly lists it as "planned" with no driver implementation.

### Why This Matters

sigrok uses open-source firmware (fx2lafw) that gets uploaded to the device's RAM on each use. Since there's no EEPROM, the original Saleae firmware isn't permanently replaced - you can switch between sigrok and Logic 2 freely.

However, without a driver for the Logic8's specific protocol, sigrok cannot communicate with the device at all.

---

## TorizonCore OS Issues Discovered

During this investigation, we found several issues with the TorizonCore OS image:

### 1. Wrong QEMU Architecture

```
/usr/bin/qemu-x86_64-static: ELF 64-bit LSB executable, x86-64
```

Should be:
```
/usr/bin/qemu-x86_64-static: ELF 64-bit LSB executable, ARM aarch64
```

### 2. Missing systemd-binfmt.service

The `qemu-binfmt-register.service` depends on `systemd-binfmt.service` which doesn't exist in TorizonCore, causing the service to fail.

### 3. binfmt_misc Not Mounted at Boot

The `/proc/sys/fs/binfmt_misc` filesystem is not mounted by default, requiring manual mounting before QEMU registration.

### Recommended OS Fixes

```ini
# /usr/lib/systemd/system/qemu-binfmt-register.service
[Unit]
Description=Register QEMU binfmt for x86_64 emulation
After=local-fs.target
Before=docker.service containerd.service
ConditionPathIsDirectory=/proc/sys/fs/binfmt_misc

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStartPre=/bin/mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc
ExecStart=/usr/lib/corekinect/qemu-binfmt-register.sh

[Install]
WantedBy=multi-user.target
```

And replace the QEMU binary with one from `debian:bookworm-slim` (ARM64):
```bash
# Correct: ARM64 binary, QEMU 7.2.x
apt-get install qemu-user-static  # from Debian Bookworm ARM64
```

---

## Alternatives Considered

| Alternative | Pros | Cons |
|-------------|------|------|
| Remote Logic 2 server | Full features, no emulation | Extra hardware, network latency |
| Different logic analyzer | sigrok-compatible | Hardware change, procurement |
| Saleae Logic (original) | sigrok supported | Older device, lower specs |
| Custom FPGA capture | Native ARM64, fast | Development effort |

---

## Conclusion

The Saleae Logic8 cannot be practically used on the MTIB ARM64 device:

1. **Logic 2 software** requires x86_64 emulation which is too resource-intensive for the 2GB RAM device
2. **sigrok** doesn't support the Logic8 hardware

### Recommendations

1. **Short-term:** Use a separate x86_64 machine to run Logic 2, with USB-over-IP or physical proximity to the MTIB
2. **Medium-term:** Consider replacing the Logic8 with a sigrok-compatible analyzer (e.g., original Saleae Logic, Logic16, or FX2-based clone)
3. **Long-term:** Wait for sigrok Logic8 support or Saleae to release ARM64-native software

---

## Appendix: Working QEMU Registration

For reference, this is the working QEMU setup discovered during testing:

```bash
# Get correct QEMU binary (ARM64-native, version 7.2.x)
docker run --platform linux/arm64 -d --name qemu-src debian:bookworm-slim sleep 60
docker exec qemu-src apt-get update
docker exec qemu-src apt-get install -y qemu-user-static
docker cp qemu-src:/usr/bin/qemu-x86_64-static /usr/bin/qemu-x86_64-static
docker rm -f qemu-src

# Mount binfmt_misc
mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc

# Register with F flag (fix-binary for container support)
echo ':qemu-x86_64:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x3e\x00:\xff\xff\xff\xff\xff\xfe\xfe\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/usr/bin/qemu-x86_64-static:F' > /proc/sys/fs/binfmt_misc/register

# Verify
docker run --rm --platform linux/amd64 ubuntu:22.04 echo "QEMU works"
```
