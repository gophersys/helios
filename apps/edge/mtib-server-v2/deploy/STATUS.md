# MTIB Server V2 + Logic 2 Sidecar - Deployment Status

## 🚨 ACTION REQUIRED: OS Team Must Add QEMU Support

**Current Blocker:** TorizonCore does not have persistent QEMU user-mode emulation support.

**Impact:** Logic 2 sidecar (x86_64) cannot run on ARM64 node without manual QEMU registration, which keeps getting cleared by the system.

**Solution:** See "OS Designer Prompt" section in README.md to add permanent QEMU support to TorizonCore base image.

**Workaround:** See QEMU Workaround section below (must be re-run after every system event that clears binfmt_misc).

---

## ⚠️ DEPLOYMENT READY - BLOCKED BY OS LIMITATION

**Pod:** `mtib-verdin-imx8mm-15702160-s0-7f994c55cb-fr2b7`
**Node:** `verdin-imx8mm-15702160` (10.4.45.33)
**Status:** 1/2 (logic2-sidecar crashing due to missing QEMU)

### Blocker: TorizonCore QEMU Not Persistent

The QEMU binfmt registration keeps being cleared by the system. This is a **TorizonCore OS limitation** that requires fixing at the OS level.

### Container Status:
```
logic2-sidecar    ✅ Running (started 2026-02-11T00:35:06Z)
mtib-server       ✅ Running (started 2026-02-11T00:35:04Z)
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Pod: mtib-verdin-imx8mm-15702160-s0           │
│                                                  │
│  ┌──────────────────────┐  ┌─────────────────┐ │
│  │  mtib-server         │  │  logic2-sidecar │ │
│  │  (ARM64 native)      │  │  (x86_64+QEMU)  │ │
│  │                      │  │                 │ │
│  │  Port: 50052    ─────┼──┼─>Port: 10430    │ │
│  └──────────────────────┘  └─────────────────┘ │
│           localhost communication                │
└──────────────────────────────────────────────────┘
```

## Images Deployed

- **MTIB Server:** `containers.ad.corekinect.com/concord-mtib-server-v2:latest` (ARM64)
- **Logic 2 Sidecar:** `containers.ad.corekinect.com/logic2-sidecar:latest` (x86_64)
  - Digest: `sha256:6f2271fd22479cc344e4aacf9e7371f295af1b0a4e7515bce65c50c97c91a536`

## Hardware Connected

- **Saleae Logic8** (USB: `Bus 001 Device 015: ID 21a9:1004 Saleae, Inc. Logic8`)
- **Channels 0-3:** Connected to Verdin UART signals
  - Channel 0-1: UART1 (nRF9151 comms processor)
  - Channel 2-3: UART2 (nRF52840 app processor)

## QEMU Emulation Setup

**CRITICAL:** QEMU user-mode emulation must be enabled on the node for x86_64 containers to work.

**Current Status:** ✅ Registered (see workaround below)

### QEMU Workaround (Until OS Updated)

**Required after every node reboot:**

```bash
# SSH to node
ssh torizon@10.4.45.33  # password: corekinect

# Extract QEMU binary
docker create --name qemu-extract tonistiigi/binfmt:latest
docker cp qemu-extract:/usr/bin/qemu-x86_64 /home/torizon/qemu-x86_64-static
docker rm qemu-extract
chmod +x /home/torizon/qemu-x86_64-static

# Register with F flag (makes it available in containers)
echo 'corekinect' | sudo -S sh -c 'echo ":qemu-x86_64:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x3e\x00:\xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/home/torizon/qemu-x86_64-static:F" > /proc/sys/fs/binfmt_misc/register'

# Verify
cat /proc/sys/fs/binfmt_misc/qemu-x86_64
# Should show: flags: F
```

**Permanent Solution:** See OS designer prompt in README.md to add QEMU to base TorizonCore image.

## Next Steps - Testing

### 1. Verify Logic 2 Automation API

Connect to MTIB server and check if it can reach Logic 2:

```python
# From Python client
from corekinect.mtib_client.v2 import MtibV2Client

client = MtibV2Client.connect("10.4.45.33", 50052)
providers = client.analyzer_list_providers()
print(providers)  # Should show ['saleae', 'simulation']
```

### 2. Test Saleae Detection

```python
# Start a capture to verify Saleae hardware detection
response = client.analyzer_capture_start(
    channels=[0, 1, 2, 3],
    sample_rate_hz=1_000_000,
    duration_seconds=5.0,
    prefer_provider='saleae'
)
```

### 3. Monitor UART Traffic

With the DUT powered on and UART active, verify Logic 2 captures the signals on channels 0-3.

## Troubleshooting

### Pod Not Starting

1. **Check QEMU registration:**
   ```bash
   ssh torizon@10.4.45.33 'cat /proc/sys/fs/binfmt_misc/qemu-x86_64'
   ```
   - If missing, run workaround above

2. **Check container logs:**
   ```bash
   kubectl logs mtib-verdin-imx8mm-15702160-s0-<pod-id> -c logic2-sidecar
   kubectl logs mtib-verdin-imx8mm-15702160-s0-<pod-id> -c mtib-server
   ```

3. **Verify USB device:**
   ```bash
   ssh torizon@10.4.45.33 'lsusb | grep Saleae'
   ```

### Saleae Not Detected

1. Check Logic 2 is running:
   ```bash
   kubectl exec mtib-verdin-imx8mm-15702160-s0-<pod-id> -c mtib-server -- wget -O- http://localhost:10430
   ```

2. Check USB passthrough in pod spec (should have `/dev/bus/usb` volume)

## Build Commands

```bash
# Build both containers
nx run mtib-server-v2:build-all -c production

# Push to registry
nx run mtib-server-v2:push-all

# Restart pod to pull new images
kubectl delete pod -l app=mtib-verdin-imx8mm-15702160-s0
```

## Files

- **Main Dockerfile:** `apps/edge/mtib-server-v2/deploy/Dockerfile` (ARM64)
- **Logic 2 Sidecar:** `apps/edge/mtib-server-v2/deploy/Dockerfile.logic2` (x86_64)
- **Docker Compose:** `apps/edge/mtib-server-v2/deploy/docker-compose.yaml`
- **K8s Deployment:** Managed by Concord (auto-deployed)

---

**Last Updated:** 2026-02-11
**Pod Started:** 2026-02-11 00:35 UTC
**Status:** ✅ Both containers healthy and running
