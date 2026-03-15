# Phase 0: Prerequisites

> **When:** Day 1
> **Effort:** ~4h active work + procurement lead time
> **Hardware state at start:** Bare — Verdin + MTIB carrier, K3s node online

---

## 0.1 Procure Hardware

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

## 0.2 Verify Infrastructure

```bash
# K3s cluster
kubectl get nodes
kubectl get node verdin-imx8mm-15702160 --show-labels

# Container registry
docker login containers.ad.corekinect.com

# CoreCloud (when URL is known)
# Test REST + DB access with existing SDK
```

---

## 0.3 Verify Repository Access

```bash
# Concord (Bitbucket)
cd ~/work/concord/concord
git checkout v2/init
git pull

# Alpha firmware (Bitbucket)
cd ~/work/firmware/alpha_fw
git checkout feat/concord_integration_pod
git pull

# concord_harness (GitHub — create if needed)
git clone https://github.com/MateoSegura/concord_harness ~/work/concord_harness
# If repo doesn't exist yet, create it on GitHub first
```

---

## 0.4 Verify CoreCloud VAL_1_0 Environment

**Status:** URL not yet known. Obtain from team.

When available:
```bash
export VAL_1_0_AUTH_SERVER_HOST_NAME=https://auth.corekinect.com
export VAL_1_0_AUTH_USERNAME=<from-vault>
export VAL_1_0_AUTH_PASSWORD=<from-vault>
export VAL_1_0_API_REST_SERVER_HOST_NAME=<TBD>
export VAL_1_0_API_KEY=<from-vault>

python -c "
from corekinect.core_cloud.db_interface import CoreCloudDBInterface
with CoreCloudDBInterface(db_env='VAL_1_0') as db:
    print('DB connected')
"
```

---

---

## 0.5 Device Personalization & LTE Verification

The Alpha B0 nRF9151 requires personalization (certs, keys, socket server
URL) before it can connect to CoreCloud via LTE. This is a prerequisite for
all Stage 4 work.

1. Flash `comm_coproc_mfg` firmware to nRF9151 via SWD (direct nrfjprog,
   no MTIB server needed yet)
2. Provision device credentials using `default_personalization.conf` +
   encryption keys from vault
3. Record `DEVICE_ID` — needed by CloudClient in all Stage 4 tests
4. Verify LTE connectivity: device boots, attaches to network, sends
   `BootMsgV2` to CoreCloud
5. Verify cloud path: `BootMsgV2` visible in CoreCloud VAL_1_0 environment

```bash
# After flashing and personalization:
python -c "
from corekinect.core_cloud.msg_def_v1_0 import BootMsgV2
msg = BootMsgV2.last(DEVICE_ID, db_env='VAL_1_0')
print(f'Boot msg received: {msg is not None}')
"
```

**Note:** This step requires the Alpha B0 board (H-01) and CoreCloud access
(0.4). Can be done before MTIB is set up — just needs direct SWD access to
the board.

---

## Phase 0 Checkpoint

| Check | Status |
|-------|--------|
| Alpha B0 sourced or ordered | |
| Scaffold confirmed (existing or ordered) | |
| K3s node reachable | |
| Container registry accessible | |
| Repos cloned, correct branches | |
| CoreCloud URL obtained | |
| Device personalized (nRF9151 flashed, certs provisioned) | |
| DEVICE_ID recorded | |
| LTE connectivity verified (BootMsgV2 at CoreCloud) | |
| Parts ordered | |
