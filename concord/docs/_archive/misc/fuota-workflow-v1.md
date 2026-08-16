# Stage 4 FUOTA Workflow

Complete step-by-step workflow for setting up and executing FUOTA (Firmware Update Over The Air) testing in Stage 4 validation.

## Prerequisites

### Environment Variables

```bash
# CoreCloud VAL_1_0 API credentials (from K8s secret: corecloud-validation)
export VAL_1_0_API_KEY="<api-key>"
export VAL_1_0_API_AUTH_SERVER_HOST_NAME="https://auth.office.corekinect.cloud:2013"
export VAL_1_0_API_REST_SERVER_HOST_NAME="https://val.office.corekinect.cloud:2018/api"
export VAL_1_0_API_AUTH_USERNAME="<username>"
export VAL_1_0_API_AUTH_PASSWORD="<password>"
```

### PYTHONPATH

```bash
export PYTHONPATH=libs/python:libs/protocols:libs
cd /workspaces/concord
```

### Required Files

- CFW files in `apps/firmware/products/alpha/artifacts/cfw/`
- MFG firmware hex files (app + comms)
- Fixture profile (`apps/validation/alpha/fixtures/alpha_b0.json`)

## Workflow Steps

### Step 1: Flash MFG Firmware

Flash the base MFG firmware that will be the FUOTA source.

```python
from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.config import NetConfig

# Connect to MTIB
cfg = MtibV1Client.Config(net=NetConfig(addr="10.4.45.33", port=50053))
client = MtibV1Client(cfg)
client.connect()

# Flash nRF52840 (APP)
hex_path = "/path/to/alpha_b0_mfg_nrf52840.hex"
client.alpha_flash_nrf52840(hex_path)

# Flash nRF9151 (COMMS)
hex_path = "/path/to/alpha_b0_mfg_nrf9151.hex"
client.alpha_flash_nrf9151(hex_path)
```

### Step 2: Power Cycle + Boot Verification

```python
from corekinect.mtib_client.v1.client.types import PowerChannel

# Power off both channels
client.PowerDisable(channel=PowerChannel.DUT)
client.PowerDisable(channel=PowerChannel.CHARGER)
time.sleep(2)

# Configure GPIO 0+1 as output LOW (required for DUT boot)
from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig
client.GpioConfig(gpio=0, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
client.GpioConfig(gpio=1, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
client.GpioWrite(gpio=0, state=False)
client.GpioWrite(gpio=1, state=False)

# Power on both channels
client.PowerEnable(channel=PowerChannel.DUT, voltage_v=4.5)
client.PowerEnable(channel=PowerChannel.CHARGER, voltage_v=5.0)
time.sleep(5)

# Verify boot (check power draw)
result, err = client.DutPowerRead()
print(f"Current: {result.current_ma}mA")  # Should be >5mA
```

### Step 3: Personalize Device

**CRITICAL**: Open UART streams BEFORE power-on to capture boot output.

```python
from corekinect.test.device_personalizer import DevicePersonalizer

personalizer = DevicePersonalizer(
    mtib=client,
    coreops_url="http://coreops-proxy",  # or direct CoreOps URL
    device_snr="09J5",
    device_imei="355025931651952",  # Optional: skip modem read
    device_iccids=["89148000009808560116", "89457300000037581199"],  # Optional
)

# This will:
# 1. Power cycle device
# 2. Lock manufacturing shell (within 8s window)
# 3. Generate EC keypair on device
# 4. Upload public key to CoreCloud
# 5. Save SIM info to CoreOps
result = personalizer.personalize()
print(f"Device ID: {result.device_id}")
print(f"Public Key: {result.public_key_b64}")
```

### Step 4: Verify Device Registration in CoreCloud

```python
from corekinect.test.fuota_client import FuotaClient

fuota = FuotaClient(api_env="VAL_1_0")

# Ensure device is registered
newly_registered = fuota.ensure_device_registered(
    device_id="70B3D584C01E1DDD",
    device_type_id=2,   # Alpha
    device_variant_id=3  # B0
)
```

### Step 5: Upload CFW Files to CoreCloud

```python
# Upload target CFW files
fuota.upload_cfw("apps/firmware/products/alpha/artifacts/cfw/108.0.5.1-BMD.cfw")
fuota.upload_cfw("apps/firmware/products/alpha/artifacts/cfw/109.0.5.1-BMD.cfw")
# Returns immediately if already uploaded
```

### Step 6: Clean Up Existing FUOTA Plans

```python
# Check if device is already in a plan
resp = fuota._singleton_request(
    "GET", "firmwareupdates/settings/devices"  # Note: /devices suffix
)
devices = resp.json().get('devicesFound', [])

for d in devices:
    if d.get('deviceId') == "70B3D584C01E1DDD":
        old_plan = d.get('planId')
        print(f"Device in plan {old_plan} - disabling...")
        fuota.disable_device("70B3D584C01E1DDD", old_plan)
```

### Step 7: Create FUOTA Plan

```python
from datetime import datetime

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

stages = [
    {
        "targets": ["108.0.5.1-BMD", "109.0.5.1-BMD"],
        "description": "Stage 1: MFG v0.5.0 → v0.5.1",
        "isSkippable": False
    }
]

plan_id = fuota.create_plan(
    stages=stages,
    description=f"Stage4 FUOTA Test {timestamp}",
    device_type_id=2,
    device_variant_id=3
)
print(f"Created plan: {plan_id}")
```

### Step 8: Assign Device to Plan

```python
result = fuota.assign_device(
    plan_id=plan_id,
    device_ids=["70B3D584C01E1DDD"],
    max_stage=0,  # 0-indexed
    enable=True
)
print(f"Assigned: {result}")
# Should show: {'numDevicesUpdated': 1, ...}
```

### Step 9: Verify Assignment

```python
# Query the correct endpoint (with /devices suffix)
resp = fuota._singleton_request("GET", "firmwareupdates/settings/devices")
devices = resp.json().get('devicesFound', [])

for d in devices:
    if d.get('deviceId') == "70B3D584C01E1DDD":
        print(f"Plan: {d.get('planId')}")
        print(f"Enabled: {d.get('enableFuota')}")
        print(f"Max Stage: {d.get('maxStage')}")
```

### Step 10: Monitor FUOTA Progress

Device will check in on LTE-M PSM wake cycle (15-60 minutes).

```bash
# Using monitor script
python apps/validation/alpha/scripts/monitor_fuota.py \
    --mtib 10.4.45.33 \
    --device 70B3D584C01E1DDD \
    --poll 30
```

Or manually:

```python
# Check progress
resp = fuota._singleton_request(
    "GET", f"firmwareupdates/progress?deviceId=70B3D584C01E1DDD"
)
if resp.status_code == 200:
    prog = resp.json()
    print(f"State: {prog.get('state')}")
    print(f"Progress: {prog.get('percentComplete')}%")
elif resp.status_code == 404:
    print("No active transfer")
```

## API Endpoint Reference

### FUOTA Endpoints (NO /api prefix)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/singleton/firmwareimages` | POST | Upload CFW file |
| `/singleton/firmwareupdates/plans` | GET | List all plans |
| `/singleton/firmwareupdates/plans` | POST | Create plan |
| `/singleton/firmwareupdates/settings/devices` | GET | **List device FUOTA settings** |
| `/singleton/firmwareupdates/settings/devices` | POST | Assign device to plan |
| `/singleton/firmwareupdates/progress?deviceId=X` | GET | Get transfer progress |

**IMPORTANT**: Use `/settings/devices` (not `/settings`) to query device assignments.

### Device Registration Endpoints (/api prefix)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/System/Devices/Register` | POST | Register device |
| `/api/System/Devices/Search` | GET | Search devices |
| `/api/System/Devices/Status` | GET | Get device status |

## CFW Naming Convention

Format: `{appId}.{major}.{minor}.{build}-{track}.cfw`

- **appId**: 108 (nRF9151 comms) or 109 (nRF52840 app)
- **track**: B=Bench, E=Engineering, P=Production
- **suffix**: M=Manufacturing, D=Debug

Examples:
- `108.0.5.0-BM` - Comms MFG v0.5.0 (Bench + Mfg)
- `109.0.5.1-BMD` - App MFG v0.5.1 (Bench + Mfg + Debug)
- `108.0.8.0-P` - Comms Production v0.8.0

## Troubleshooting

### Device not found in settings

Use `/singleton/firmwareupdates/settings/devices` (with `/devices` suffix), not `/settings` alone.

### Assignment returns success but device not in settings

Check that:
1. Device is registered in CoreCloud first (`ensure_device_registered()`)
2. Plan ID is valid and exists
3. Query the correct endpoint (`/settings/devices`)

### FUOTA not progressing

1. Device must wake from PSM (15-60 min)
2. Device must have valid LTE-M connection
3. Device must be personalized with keys uploaded
4. Check device is enabled in plan (`enableFuota: true`)

### Plan shows 0 stages in list

The plans list endpoint doesn't return stage details. Stages are returned in the create response and stored server-side. This is a display issue, not a data issue.

## Test Devices

| SNR | Device ID | MTIB Address | Notes |
|-----|-----------|--------------|-------|
| 09J5 | 70B3D584C01E1DDD | 10.4.45.33 | Primary test device |
| 0964 | 70B3D584C01E1FCC | 10.4.45.33 | Secondary |
| 097D | 70B3D584C01E20A2 | 10.4.45.32 | REV 1.1 MTIB |

## Complete Script

See `apps/validation/alpha/scripts/fuota_setup.py` for a complete automated setup script.
