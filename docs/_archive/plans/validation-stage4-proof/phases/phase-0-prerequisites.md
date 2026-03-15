# Phase 0: Prerequisites

> **When:** Day 1-2
> **Effort:** ~8h active work + procurement lead time + firmware builds
> **Hardware state at start:** 2× Verdin + MTIB carriers online (REV 1.1 + REV 1.2),
>   V1 MTIB server deployed
> **Hardware state at end:** Device personalized, CoreCloud accessible, all firmware
>   assets built, parts ordered

---

## Engineering Protocol for Phase 0

Phase 0 touches live infrastructure — the K8s cluster, MTIB servers, and
CoreCloud. Before making changes:

1. **Verify the current state first.** Don't assume what's running. Use
   `kubectl`, `grpcurl`, and SSH to see what actually exists before
   modifying it.
2. **Read existing deploy code.** The infra scripts (`deploy/infra/v2/`)
   are idempotent and well-structured. Understand them before modifying.
3. **Check Confluence** for Torizon OS provisioning docs, K3s agent
   joining procedures, and MTIB hardware revision specs.
4. **Validate hardware revision.** When a new Verdin board arrives, probe
   the I2C bus to confirm the MTIB revision: `i2cdetect -y 3` — if
   address 0x38 (TCA9534A) responds, it's REV 1.2. If not, REV 1.1.
   Do not trust labels alone.
5. **Build firmware the way CI would.** Use the same `scripts/build.sh`
   and configs. Do not hand-craft west build commands unless the build
   script is broken — and if it is, fix the script.

---

## Parallelization Strategy

Phase 0 and Phase 1 are designed to run in parallel across multiple Claude
instances and physical hardware setup. Here's how to split the work:

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Day 1 Kickoff                                                          │
│                                                                          │
│  Claude Instance 1              Claude Instance 2       Hardware status  │
│  ─────────────────              ─────────────────       ──────────────   │
│  Phase 1: MTIB server           Phase 0: prereqs        ✓ K8s: DONE     │
│  updates (M1 proto first,       ├── 0.1b Verify infra   ✓ Both Verdins  │
│  then M2-M8 peripheral          ├── 0.3 CoreCloud env     in cluster    │
│  by peripheral)                 ├── 0.5 Build ALL       ✓ Alphas wired  │
│                                 │   firmware assets        (mfg fixture) │
│  Constraint: M1 (proto) must    ├── TDD: flash + verify                 │
│  finish before M2-M8 start.     │   each hex on HW      Later:          │
│  Each M2-M8 unit is a self-     └── 0.4 Personalize     Stage 4 stimulus│
│  contained session.                  device              (relays, NFC,   │
│                                                          photodiode,     │
│                                 These are independent    Peltier) when   │
│                                 of MTIB server work.     parts arrive    │
└──────────────────────────────────────────────────────────────────────────┘
```

**Key parallelism:** Hardware setup is done — both nodes online with Alphas
connected. Claude Instance 1 works on MTIB server updates. Claude Instance 2
handles firmware builds with TDD (build, flash on real hardware, verify UART,
run POST), CoreCloud verification, and device personalization. Stage 4
stimulus wiring (relays, photodiode, etc.) happens later when parts arrive.

---

## 0.1 K8s Node Onboarding (2 new validation nodes)

### Current Cluster State

The K3s cluster currently has (verified 2026-03-01):
- **3 server nodes** (amd64): `concordserver01-03` at 10.4.45.11-13 — K3s v1.33.5
- **3 agent nodes** (amd64): `concordagent01-03` at 10.4.45.21-23 — K3s v1.33.5
- **2 validation edge nodes** (arm64 Verdin) — both joined, labeled, Ready:

| Node | IP | HW Revision | K3s | Labels |
|------|-----|------------|-----|--------|
| `verdin-imx8mm-15005665` | 10.4.45.33 | REV 1.2 | v1.28.7 | `role=edge`, `purpose=validation`, `mtib-revision=1.2` |
| `verdin-imx8mm-15702161` | 10.4.45.32 | REV 1.1 | v1.28.7 | `role=edge`, `purpose=validation`, `mtib-revision=1.1` |

- **0 manufacturing edge nodes** — all previously removed from cluster.

**K8s node onboarding: DONE.** Both nodes are in the cluster and labeled.
Remaining infra work: update `00-labels-taints.sh`, create per-revision
deployment manifests, assign K8s roles to edge nodes. See
`deploy/infra/v2/TODO.md` for tracked infra debt.

---

## 0.1a Hardware Already Connected

Both validation nodes have an Alpha B0 connected in the same configuration
as the manufacturing fixture. This means the full manufacturing test
capability is available immediately — no additional wiring needed for
basic validation.

### What's Wired and Available NOW

| Interface | Channels | What It Gives You |
|-----------|----------|------------------|
| **Power (DUT)** | Ch 0, INA219 @ 0x40, MCP4017 @ 0x2F | Battery sim (4.5V required), current measurement |
| **Power (CHG)** | Ch 1, INA219 @ 0x41 | 5V charge rail, charger current sense |
| **ADC** | Ch 0-3 via 2× ADS1015 (0x48, 0x49) | +3.3V, +BATT_SYS, +VBCKP, +SYS voltage rails |
| **UART** | 2 ports (nRF52840 app MCU + nRF9151 comms MCU) | Shell commands, POST, log capture |
| **SWD/J-Link** | 2 probes (one per MCU, muxed on REV 1.2) | Firmware flashing for both processors |
| **GPIO** | 9 pins (SODIMM 206/208/210/212 + I2S + PWM) | Level shifter control, general purpose |
| **Accelerometer** | Via UART `read_accel` command | IMU data (LSM6DSO, read by Alpha MCU internally) |

### What's Testable Immediately (TDD from Day 1)

With the MTIB V1 server deployed, we can:

1. **Flash firmware** — build a hex, stream it via J-Link, verify device boots
2. **Verify UART** — open shell, send commands, confirm bidirectional comms
3. **Run POST** — the full 10-step manufacturing POST exercises BMS, charger,
   GPS, modem, external flash, chip IDs, accelerometer
4. **Measure power** — verify boot current (>50mA), rail voltages via ADC
5. **Validate both MTIB revisions** — flash the same firmware on both nodes,
   confirm UART works on both (REV 1.1 with pin swap overlay, REV 1.2 default)

### Manufacturing Test Steps (proven, reusable as validation baseline)

These test steps are proven in production manufacturing
(`apps/manufacturing/alpha/src/tests/`):

| Test Suite | Steps | What It Validates | Key RPCs |
|-----------|-------|------------------|----------|
| **Electrical** | 5 steps | Power sequencing, voltage rails, current draw, load sharing | `DutPowerEnable`, `DutPowerRead`, `AdcRead` |
| **FW Flash** | 3 steps | Flash both MCUs via SWD, verify boot + UART | `FlashProgram`, `UartStream` |
| **POST** | 10 steps | BMS, charger, GPS, modem FW, IMEI/ICCID, ext flash, chip IDs, personalization | `UartStream` (shell commands) |

**Reference files:**
- `apps/manufacturing/alpha/src/tests/electrical/test.py`
- `apps/manufacturing/alpha/src/tests/fw_flash/test.py`
- `apps/manufacturing/alpha/src/tests/post/test.py`
- `apps/manufacturing/alpha/src/tests/shared/rpcs.py` — all MTIB RPC wrappers

### What's NOT Wired (Needs Stage 4 Fixture Hardware)

These are the physical stimulus channels that Stage 4 product tests need
beyond what manufacturing provides:

| Stimulus | Why Needed | Hardware Required |
|----------|-----------|------------------|
| Button press relay | Simulate user button press/hold | Relay module on GPIO |
| Charger insertion relay | Simulate USB charger connect/disconnect | Relay module on GPIO |
| Peltier TEC + thermistor | Temperature control for environmental tests | Peltier module + NTC 10K |
| Photodiode array (RGB) | Capture LED blink patterns for state verification | 3-channel photodiode on ADC |
| On-skin electrode pad | Simulate skin contact for biometric tests | Conductive pad on GPIO |
| NFC reader | NFC tap simulation | I2C NFC reader (NT3H2111 compatible) |
| Motion platform | 6-DOF shake for motion detection | Linear actuator (already exists as scaffold?) |

### TDD Strategy

Use what's wired to validate firmware builds incrementally as they're
created in Phase 0.5 (firmware asset generation):

```
Build hex → Flash via MTIB → Verify UART → Run POST → Record result
     │                                                      │
     └──── iterate if broken ◄──────────────────────────────┘
```

**For each of the 9 firmware assets:**
1. Build hex (using `scripts/build.sh` with appropriate overlay)
2. Flash to the correct MTIB node (REV 1.1 or REV 1.2)
3. Verify UART bidirectional communication works
4. For manufacturing variants: run POST suite to confirm all peripherals respond
5. For debug variants: verify log output is visible on UART
6. For release variants: verify UART is silent (no log output)

This catches firmware build problems, DTS overlay errors, and UART pin
swap issues before any Stage 4 test code is written.

### Infrastructure Files to Update

| File | What Changes |
|------|-------------|
| `deploy/infra/v2/00-labels-taints.sh` | Add 2 new node hostnames to `EDGE_VALIDATION` array, add `mtib-revision` label |
| `deploy/edge/mtib-server/validation.yaml` | Split into per-revision manifests OR update replicas to 2 |

### Step 1: Flash Torizon OS on New Boards

Flash 2 Verdin iMX8M Mini boards with Torizon OS (same image as existing
edge nodes). Record hostnames — they follow the pattern
`verdin-imx8mm-<serial>`.

```bash
# After flashing, verify SSH access
ssh torizon@<NEW_NODE_IP_1>
ssh torizon@<NEW_NODE_IP_2>
```

### Step 2: Join K3s Cluster

Each new node joins the cluster as an agent:

```bash
# On each new Verdin board:
curl -sfL https://get.k3s.io | K3S_URL=https://concordserver01:6443 \
  K3S_TOKEN=<node-token> sh -s - agent \
  --node-label "corekinect.com/role=edge" \
  --node-label "corekinect.com/purpose=validation"
```

Verify from the control plane:

```bash
kubectl get nodes -l corekinect.com/purpose=validation
# Should show 3 nodes (1 existing + 2 new)
```

### Step 3: Apply Labels and Taints

Update `deploy/infra/v2/00-labels-taints.sh` to include the new nodes:

```bash
# Update the EDGE_VALIDATION array (replace stale entries):
EDGE_VALIDATION=(
  "verdin-imx8mm-15005665"    # REV 1.2 — 10.4.45.33 — joined + labeled ✓
  "verdin-imx8mm-15702161"    # REV 1.1 — 10.4.45.32 — joined + labeled ✓
)
# Remove all 5 stale manufacturing nodes from EDGE_MANUFACTURING (cluster was cleaned)
EDGE_MANUFACTURING=()
```

Add a new MTIB revision label to the labeling function so deployments can
target specific hardware revisions:

```bash
# Both done:
# kubectl label node verdin-imx8mm-15005665 corekinect.com/role=edge \
#   corekinect.com/purpose=validation corekinect.com/mtib-revision=1.2 --overwrite
# kubectl label node verdin-imx8mm-15702161 corekinect.com/role=edge \
#   corekinect.com/purpose=validation corekinect.com/mtib-revision=1.1 --overwrite
```

Then run the updated script:

```bash
bash deploy/infra/v2/00-labels-taints.sh --with-taints
```

### Step 4: Deploy MTIB V1 Server

**Problem:** The current `validation.yaml` uses a single Deployment with
`HARDWARE_VERSION=REV1.1` hardcoded. With 2 nodes at different revisions,
we need per-revision configuration.

**Solution:** Split into two manifests — one per revision. After Phase 1
adds auto-detection (TCA9534A probe at 0x38), this can be consolidated
back into a single Deployment.

```
deploy/edge/mtib-server/
├── manufacturing.yaml           # 4 replicas, all REV 1.1 (unchanged)
├── validation-rev11.yaml        # 1 replica, pinned to REV 1.1 node
└── validation-rev12.yaml        # 1 replica, pinned to REV 1.2 node
```

Each manifest uses `nodeAffinity` to target the specific MTIB revision:

```yaml
# validation-rev11.yaml — key differences from current validation.yaml
spec:
  replicas: 1
  template:
    spec:
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
            - matchExpressions:
              - key: "corekinect.com/role"
                operator: In
                values: ["edge"]
              - key: "corekinect.com/purpose"
                operator: In
                values: ["validation"]
              - key: "corekinect.com/mtib-revision"
                operator: In
                values: ["1.1"]
      containers:
      - name: mtib-server-validation-rev11
        env:
        - name: HARDWARE_VERSION
          value: "REV1.1"
        - name: MOTION_ENABLED
          value: "true"        # Motion scaffold attached — same for both nodes

# validation-rev12.yaml — same structure, different revision
        - name: HARDWARE_VERSION
          value: "REV1.2"
        - name: MOTION_ENABLED
          value: "true"        # Motion scaffold attached — same for both nodes
```

**Note on MOTION_ENABLED:** This flag controls whether the server exposes
motion RPCs. It is about whether a **motion scaffold is physically
attached** to the node, NOT about the hardware revision. Both validation
nodes have scaffolds, so both get `MOTION_ENABLED=true`. The REV 1.2
motor power MOSFET (TCA9534A P2 / VMM_EN) is a safety feature that
keeps the motor off at startup — it does not determine motion capability.
REV 1.1 has no such MOSFET, so the motor is powered whenever the system
is powered. Both revisions can drive motion.

Deploy:

```bash
kubectl apply -f deploy/edge/mtib-server/validation-rev11.yaml
kubectl apply -f deploy/edge/mtib-server/validation-rev12.yaml

# Remove old single validation.yaml if still deployed
kubectl delete deployment mtib-server-validation 2>/dev/null || true
```

### Step 5: Verify Both Nodes

```bash
# Check pods are running on correct nodes
kubectl get pods -l app=mtib-server-validation-rev11 -o wide
kubectl get pods -l app=mtib-server-validation-rev12 -o wide

# Verify gRPC health on each
grpcurl -plaintext 10.4.45.33:50053 grpc.health.v1.Health/Check   # REV 1.2
grpcurl -plaintext 10.4.45.32:50053 grpc.health.v1.Health/Check   # REV 1.1
```

### Phase 1 Consolidation Note

After Phase 1 M9 adds hardware revision auto-detection (TCA9534A probe),
the two validation manifests can optionally be consolidated back into a
single `validation.yaml` with `replicas: 2`. The server will detect its
own revision at startup and branch accordingly. The `HARDWARE_VERSION`
env var becomes an optional override rather than a requirement.

---

## 0.1b Verify Existing Infrastructure

### Container Registry

```bash
docker login containers.ad.corekinect.com
```

### K3s Cluster (full view)

```bash
kubectl get nodes -L corekinect.com/role,corekinect.com/purpose,corekinect.com/mtib-revision
```

---

## 0.2 Procure Hardware

Order on Day 1 — longest lead times:

| Item | Est. Cost | Lead Time | Source |
|------|-----------|-----------|--------|
| Alpha B0 board (1 unit) | $200-400 | Check inventory first | Internal |
| NFC reader (I2C, NT3H2111 compatible) | ~$30 | 1-2 weeks | Adafruit/Mouser |
| Linear actuator (check existing scaffold) | ~$200-1,000 | 0-2 weeks | Amazon/Actuonix |
| Relay modules (2× charger + button) | ~$10 | 1 week | Amazon |
| 3-channel photodiode breakout (RGB) | ~$50 | 1 week | Adafruit |
| Peltier module (TEC1-12706 or similar) | ~$100-500 | 1 week | Amazon/Mouser |
| NTC 10K thermistor | ~$5 | 1 week | Mouser |
| Conductive electrode pad | ~$20 | 1 week | Specialty |

---

## 0.3 Verify CoreCloud VAL_1_0 Environment

**Status:** URL not yet known. Obtain from team.

**Can run in parallel with MTIB server work (Claude Instance 2).**

When available:
```bash
export VAL_1_0_AUTH_SERVER_HOST_NAME=https://auth.corekinect.com
export VAL_1_0_AUTH_USERNAME=<from-vault>
export VAL_1_0_AUTH_PASSWORD=<from-vault>
export VAL_1_0_API_REST_SERVER_HOST_NAME=<TBD>
export VAL_1_0_API_KEY=<from-vault>

python3 -c "
from corekinect.core_cloud.db_interface import CoreCloudDBInterface
with CoreCloudDBInterface(db_env='VAL_1_0') as db:
    print('DB connected')
"
```

---

## 0.4 Device Personalization & LTE Verification

The Alpha B0 nRF9151 requires personalization (certs, keys, socket server
URL) before it can connect to CoreCloud via LTE. This is a prerequisite for
all Stage 4 work.

1. Flash `comm_coproc_mfg` firmware to nRF9151 via SWD (direct nrfjprog,
   no MTIB server needed yet — use direct J-Link connection)
2. Provision device credentials using `default_personalization.conf` +
   encryption keys from vault
3. Record `DEVICE_ID` — needed by CloudClient in all Stage 4 tests
4. Verify LTE connectivity: device boots, attaches to network, sends
   `BootMsgV2` to CoreCloud
5. Verify cloud path: `BootMsgV2` visible in CoreCloud VAL_1_0 environment

```bash
# After flashing and personalization:
python3 -c "
from corekinect.core_cloud.msg_def_v1_0 import BootMsgV2
msg = BootMsgV2.last(DEVICE_ID, db_env='VAL_1_0')
print(f'Boot msg received: {msg is not None}')
if msg:
    print(f'  boot_reason: {msg.boot_reason}')
    print(f'  fw_version: {msg.fw_version}')
"
```

**Note:** This step requires the Alpha B0 board (H-01) and CoreCloud access
(0.3). Can be done before fixture wiring — just needs direct SWD access.

---

## 0.5 Firmware Asset Generation

### The Problem

Stage 4 testing needs firmware assets for **both MTIB hardware revisions**.
REV 1.1 had the UART TX/RX lines physically swapped on the carrier board,
so the nRF firmware needed a DTS overlay to flip the pins. REV 1.2 fixed
this in hardware — firmware uses default pins.

This means every firmware variant needs two builds: one for each MTIB
revision. Without this, UART communication fails on one revision or the
other.

### MTIB Revision Impact on Firmware

| MTIB Rev | UART Hardware | nRF Firmware Needs | DTS Overlay |
|----------|-------------|-------------------|-------------|
| REV 1.1 | TX/RX swapped on carrier | Pin swap in DTS | `boards/alpha_b0_nrf52840_mtib11.overlay` |
| REV 1.2 | Fixed in hardware | Default pins | None (or empty overlay) |

The pin swap overlay lives at the app level under
`apps/firmware/products/alpha/alpha_mfg_fw/` (and equivalents for other
firmware variants). It swaps the UART TX/RX pin assignments in the
devicetree so the firmware compensates for the crossed wires on the REV 1.1
carrier board.

### Firmware Asset Naming Convention

To keep track of which hex goes with which MTIB, the naming convention
encodes the MTIB revision:

```
<product>_<variant>_<mcu>_<mtib_rev>.hex
```

| Field | Values | Example |
|-------|--------|---------|
| `product` | `alpha` | `alpha` |
| `variant` | `mfg`, `debug`, `release` | `mfg` |
| `mcu` | `nrf52840`, `nrf9151` | `nrf52840` |
| `mtib_rev` | `mtib11`, `mtib12` | `mtib11` |

**Examples:**
```
alpha_mfg_nrf52840_mtib11.hex       # Manufacturing, app MCU, for REV 1.1 bench
alpha_mfg_nrf52840_mtib12.hex       # Manufacturing, app MCU, for REV 1.2 bench
alpha_mfg_nrf9151.hex               # Manufacturing, comms MCU (same for both)
alpha_debug_nrf52840_mtib11.hex     # Prod debug, app MCU, for REV 1.1 bench
alpha_debug_nrf52840_mtib12.hex     # Prod debug, app MCU, for REV 1.2 bench
alpha_debug_nrf9151.hex             # Prod debug, comms MCU (same for both)
alpha_release_nrf52840_mtib11.hex   # Prod release, app MCU, for REV 1.1 bench
alpha_release_nrf52840_mtib12.hex   # Prod release, app MCU, for REV 1.2 bench
alpha_release_nrf9151.hex           # Prod release, comms MCU (same for both)
```

**Note on nRF9151 comms firmware:** The comms coprocessor (`comm_coproc_mfg`)
uses a different UART bus and its pin assignment may not be affected by the
MTIB revision. If the comms UART is also swapped on REV 1.1, add `_mtib11`
/ `_mtib12` suffixes to comms hexes too. Verify during asset generation.

### Full Asset Matrix

| # | Asset | Variant | MCU | MTIB Rev | DTS Overlay | Tests It Supports |
|---|-------|---------|-----|----------|-------------|------------------|
| 1 | `alpha_mfg_nrf52840_mtib11.hex` | Manufacturing | nRF52840 | 1.1 | Pin swap | Flash, UART, POST on REV 1.1 |
| 2 | `alpha_mfg_nrf52840_mtib12.hex` | Manufacturing | nRF52840 | 1.2 | None | Flash, UART, POST on REV 1.2 |
| 3 | `alpha_mfg_nrf9151.hex` | Manufacturing | nRF9151 | Both | — | Comms for both benches |
| 4 | `alpha_debug_nrf52840_mtib11.hex` | Prod Debug | nRF52840 | 1.1 | Pin swap | Stage 4 debug tests on REV 1.1 |
| 5 | `alpha_debug_nrf52840_mtib12.hex` | Prod Debug | nRF52840 | 1.2 | None | Stage 4 debug tests on REV 1.2 |
| 6 | `alpha_debug_nrf9151.hex` | Prod Debug | nRF9151 | Both | — | Comms for both benches |
| 7 | `alpha_release_nrf52840_mtib11.hex` | Prod Release | nRF52840 | 1.1 | Pin swap | Stage 4 release tests on REV 1.1 |
| 8 | `alpha_release_nrf52840_mtib12.hex` | Prod Release | nRF52840 | 1.2 | None | Stage 4 release tests on REV 1.2 |
| 9 | `alpha_release_nrf9151.hex` | Prod Release | nRF9151 | Both | — | Comms for both benches |

**Total: 9 hex files** (6 nRF52840 + 3 nRF9151, or 12 if nRF9151 also needs
per-revision builds).

### Build Steps

Build all firmware assets using the existing build system. Each variant ×
MTIB revision is a separate `west build` invocation with the appropriate
overlay.

```bash
cd ~/work/firmware/alpha_fw

# --- Manufacturing firmware ---
# REV 1.2 (default pins)
bash scripts/build.sh mfg -b alpha_b0
cp artifacts/alpha_mfg_fw/alpha_b0/app_nrf52840.hex \
   assets/alpha_mfg_nrf52840_mtib12.hex
cp artifacts/alpha_mfg_fw/alpha_b0/comms_nrf9151.hex \
   assets/alpha_mfg_nrf9151.hex

# REV 1.1 (pin swap overlay)
bash scripts/build.sh mfg -b alpha_b0 --overlay boards/alpha_b0_nrf52840_mtib11.overlay
cp artifacts/alpha_mfg_fw/alpha_b0/app_nrf52840.hex \
   assets/alpha_mfg_nrf52840_mtib11.hex

# --- Production Debug ---
# REV 1.2
bash scripts/build.sh app -b alpha_b0 --config boards/alpha_b0_debug.conf
cp artifacts/alpha_fw/alpha_b0/app_nrf52840.hex \
   assets/alpha_debug_nrf52840_mtib12.hex
cp artifacts/alpha_fw/alpha_b0/comms_nrf9151.hex \
   assets/alpha_debug_nrf9151.hex

# REV 1.1
bash scripts/build.sh app -b alpha_b0 --config boards/alpha_b0_debug.conf \
   --overlay boards/alpha_b0_nrf52840_mtib11.overlay
cp artifacts/alpha_fw/alpha_b0/app_nrf52840.hex \
   assets/alpha_debug_nrf52840_mtib11.hex

# --- Production Release ---
# REV 1.2
bash scripts/build.sh app -b alpha_b0 --config boards/alpha_b0_release.conf
cp artifacts/alpha_fw/alpha_b0/app_nrf52840.hex \
   assets/alpha_release_nrf52840_mtib12.hex
cp artifacts/alpha_fw/alpha_b0/comms_nrf9151.hex \
   assets/alpha_release_nrf9151.hex

# REV 1.1
bash scripts/build.sh app -b alpha_b0 --config boards/alpha_b0_release.conf \
   --overlay boards/alpha_b0_nrf52840_mtib11.overlay
cp artifacts/alpha_fw/alpha_b0/app_nrf52840.hex \
   assets/alpha_release_nrf52840_mtib11.hex
```

**Note:** The exact `--overlay` flag syntax depends on the build script.
If `build.sh` doesn't support `--overlay`, the DTS overlay must be applied
via west build args: `-- -DDTC_OVERLAY_FILE=boards/alpha_b0_nrf52840_mtib11.overlay`

### Asset Storage Location

All built assets go into a central location in the concord repo:

```
libs/corekinect/test/validation/assets/firmware/
├── alpha_mfg_nrf52840_mtib11.hex
├── alpha_mfg_nrf52840_mtib12.hex
├── alpha_mfg_nrf9151.hex
├── alpha_debug_nrf52840_mtib11.hex
├── alpha_debug_nrf52840_mtib12.hex
├── alpha_debug_nrf9151.hex
├── alpha_release_nrf52840_mtib11.hex
├── alpha_release_nrf52840_mtib12.hex
├── alpha_release_nrf9151.hex
└── manifest.json           # Maps asset names to versions, build hashes
```

**`manifest.json`:**
```json
{
  "product": "alpha",
  "board": "alpha_b0",
  "fw_version": "0.8.0",
  "build_date": "2026-03-01",
  "assets": {
    "alpha_mfg_nrf52840_mtib11": {
      "file": "alpha_mfg_nrf52840_mtib11.hex",
      "variant": "manufacturing",
      "mcu": "nrf52840",
      "mtib_rev": "1.1",
      "overlay": "alpha_b0_nrf52840_mtib11.overlay",
      "sha256": "<hash>"
    }
  }
}
```

### DTS Overlay to Create

The REV 1.1 pin swap overlay needs to be created (or verified if it already
exists). It swaps the UART TX/RX pin assignments for the nRF52840:

**File:** `boards/alpha_b0_nrf52840_mtib11.overlay`

```dts
/* MTIB REV 1.1 UART pin swap compensation.
 * REV 1.1 carrier board has TX/RX crossed at the connector.
 * This overlay swaps the nRF52840 UART0 pins to compensate.
 * Not needed on REV 1.2 (fixed in hardware).
 */
&uart0 {
    pinctrl-0 = <&uart0_mtib11_default>;
    pinctrl-1 = <&uart0_mtib11_sleep>;
};

&pinctrl {
    uart0_mtib11_default: uart0_mtib11_default {
        group1 {
            psels = <NRF_PSEL(UART_TX, 0, 25)>;  /* Swapped: was RX */
        };
        group2 {
            psels = <NRF_PSEL(UART_RX, 0, 23)>;  /* Swapped: was TX */
            bias-pull-up;
        };
    };
    uart0_mtib11_sleep: uart0_mtib11_sleep {
        group1 {
            psels = <NRF_PSEL(UART_TX, 0, 25)>,
                    <NRF_PSEL(UART_RX, 0, 23)>;
            low-power-enable;
        };
    };
};
```

**Important:** The exact pin numbers above are placeholders based on the
Alpha B0 pinctrl definitions. Verify against the actual
`alpha_b0_nrf52840-pinctrl.dtsi` before building. The swap is TX↔RX on the
same pins — the pin numbers just exchange between the TX and RX roles.

### Verification

After building all assets, verify each hex on its target MTIB revision:

| Test | MTIB | Asset | Pass Criteria |
|------|------|-------|--------------|
| Flash + boot | REV 1.1 | `alpha_mfg_nrf52840_mtib11.hex` | Device boots, UART output visible |
| Flash + boot | REV 1.2 | `alpha_mfg_nrf52840_mtib12.hex` | Device boots, UART output visible |
| UART bidirectional | REV 1.1 | mfg + mtib11 | Shell commands work over MTIB UART |
| UART bidirectional | REV 1.2 | mfg + mtib12 | Shell commands work over MTIB UART |
| POST | REV 1.1 | mfg + mtib11 | POST tests pass (chip IDs, BMS, modem) |
| POST | REV 1.2 | mfg + mtib12 | POST tests pass |
| Debug log capture | REV 1.1 | debug + mtib11 | UART logs visible |
| Debug log capture | REV 1.2 | debug + mtib12 | UART logs visible |
| Silent release | REV 1.1 | release + mtib11 | No UART output (expected) |
| Silent release | REV 1.2 | release + mtib12 | No UART output (expected) |

---

## Phase 0 Checkpoint

| Check | Status |
|-------|--------|
| 2 new Verdin boards flashed with Torizon OS | |
| Both new nodes joined K3s cluster | |
| Node labels applied (role, purpose, mtib-revision) | |
| `00-labels-taints.sh` updated with new hostnames | |
| `validation-rev11.yaml` + `validation-rev12.yaml` created | |
| MTIB V1 server operational on REV 1.1 node | |
| MTIB V1 server operational on REV 1.2 node | |
| Alpha B0 sourced or ordered | |
| Scaffold confirmed (existing or ordered) | |
| CoreCloud URL obtained | |
| Device personalized (nRF9151 flashed, certs provisioned) | |
| DEVICE_ID recorded | |
| LTE connectivity verified (BootMsgV2 at CoreCloud) | |
| REV 1.1 pin swap DTS overlay created and verified | |
| All 9 firmware assets built | |
| Manufacturing firmware verified on both MTIB revisions (UART works) | |
| Debug firmware verified on both MTIB revisions (logs visible) | |
| Release firmware verified on both MTIB revisions (silent) | |
| POST tests pass on both MTIB revisions | |
| Parts ordered | |
