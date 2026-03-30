# CoreCloud v1.0 Validation Integration

Research document for integrating the automated firmware validation pipeline (Stage 4) with CoreCloud v1.0. Covers device registration, message verification, FUOTA management, and test automation via the existing Python SDK.

**Scope**: CoreCloud v1.0 only. The legacy v0.9 system is out of scope for validation pipeline work.

---

## 1. CoreCloud v1.0 Architecture (Relevant Components)

CoreCloud v1.0 is a multi-service backend that manages device connectivity, configuration, firmware updates, and message storage. The validation pipeline interacts with four components:

| Component | Purpose | Validation Usage |
|-----------|---------|-----------------|
| REST Server | HTTP API for device management, config, FUOTA plans | Register devices, create FUOTA plans, query device state |
| Socket Server | Persistent device connections, message relay, FUOTA delivery | Devices connect here; FUOTA chunks sent on uplink |
| Time Server | UTC time provisioning for devices | Devices need accurate time for TLS cert validation |
| Singleton | Background jobs, scheduled tasks | FUOTA evaluation runs here (determines what updates to send) |

### How a device interacts with CoreCloud

1. Device boots, acquires LTE connection
2. Device connects to the **Time Server** to get UTC time (needed for TLS certificate validation)
3. Device opens a persistent socket to the **Socket Server**
4. Device sends uplink messages (boot, position, biometrics, etc.) via the socket
5. The **Singleton** evaluates FUOTA eligibility and queues firmware chunks
6. FUOTA chunks are delivered to the device on the next socket connection
7. The **REST Server** provides management APIs used by web dashboards and automation (including this validation pipeline)

---

## 2. Authentication

CoreCloud v1.0 uses a two-step authentication flow for REST API access:

### Auth Flow

```
API Key (header) + Basic Auth (username:password)
    │
    ▼
POST /authentication/tokens/request
    │
    ▼
Bearer Token (JWT, ~10 min TTL)
    │
    ▼
Use Bearer Token + API Key for all subsequent requests
```

### Request Headers (after auth)

```http
Authorization: Bearer <jwt_token>
X-API-KEY: <api_key>
Content-Type: application/json
Accept: application/json
```

### Token Lifecycle

- The SDK fetches a token on first request (or on context manager entry if `test_auth_on_enter=True`)
- Tokens expire after ~600 seconds (10 minutes) by default
- On HTTP 401, the SDK automatically invalidates the current token, fetches a new one, and retries once
- Token expiry is tracked internally with a 15-second safety margin

### SDK Auth Handling

The `CoreCloudRestInterface` in `api_interface.py` handles the full auth lifecycle:

```python
from corekinect.core_cloud.api_interface import CoreCloudRestInterface

with CoreCloudRestInterface(env_namespace="VAL_1_0") as api:
    # Token is automatically fetched on entry
    resp = api.request("GET", "/System/Devices/Status", params={"deviceId": "70B3D584C0201234"})
    resp.raise_for_status()
    # Token is automatically refreshed if a 401 is returned
```

### Environment Variables for VAL_1_0

From `.env.example` at `libs/python/corekinect/core_cloud/.env.example`:

```bash
# Auth
VAL_1_0_API_AUTH_SERVER_HOST_NAME=https://auth.office.corekinect.cloud:2013
VAL_1_0_API_AUTH_USERNAME=<service_account>@corekinect.com
VAL_1_0_API_AUTH_PASSWORD=<password>

# REST API
VAL_1_0_API_REST_SERVER_HOST_NAME=https://val.office.corekinect.cloud:2018/api
VAL_1_0_API_KEY=<base64_api_key>

# Database
VAL_1_0_DB_DRIVER=postgresql+psycopg2
VAL_1_0_DB_USER=<db_user>
VAL_1_0_DB_PASS=<db_password>
VAL_1_0_DB_HOST=validation.ad.corekinect.com
VAL_1_0_DB_PORT=5432
VAL_1_0_DB_NAME=<db_name>
```

---

## 3. CoreCloud Python SDK Current State

**Location**: `libs/python/corekinect/core_cloud/`

### Module Inventory

| Module | Capability | Status |
|--------|-----------|--------|
| `api_interface.py` | REST client with auth, rate limiting, token refresh, singleton pattern | Working -- but only GPS config endpoint implemented as a concrete wrapper |
| `msg_def_v1_0.py` | Message type dataclasses with ORM mapping, DB query helpers, REST send/search | Complete -- 11+ message types with full query API |
| `db_interface.py` | SQLAlchemy ORM session manager with optional SSH tunneling | Working -- supports `VAL_1_0`, `DEV_1_0`, `DEV_0_9` namespaces |
| `db_orm_v1_0.py` | 50+ SQLAlchemy ORM table definitions including all FUOTA tables | Complete |
| `__init__.py` | Package init | Minimal |
| `.env.example` | Reference environment variable configuration | Template for all three namespaces |

### Message Types Available for Verification

Each message class in `msg_def_v1_0.py` inherits from `MsgBase` and provides:
- `.last(dut_id, db_env="VAL_1_0")` -- get the most recent message for a device
- `.since_server_time(dut_id, start, end, db_env="VAL_1_0")` -- messages in a server-time window
- `.since_device_time(dut_id, start, end, db_env="VAL_1_0")` -- messages in a device-time window
- `.since_record_id(dut_id, start_id, end_id, db_env="VAL_1_0")` -- messages by record ID range

| Message Class | UID | ORM Table | Key Fields |
|---------------|-----|-----------|------------|
| `BootMsgV2` | 548 | `messagesboottbl` | `time_of_boot`, `flags` (MCU type, boot reason), `num_exceptions` |
| `PositionMsgV6` | 556 | `messagespositionv5tbl` | `latitude`, `longitude`, `gps_altitude`, `horizontal_accuracy`, `num_sat`, `fix_type`, `batt_voltage`, `batt_percent` |
| `BiometricDataMsg` | 557 | `messagesbiometricdatatbl` | `heart_rate`, `spo2`, `skin_temperature`, `estimated_core_temperature`, `heat_strain_index`, `on_body` flag |
| `NetworkStatusMsgV4` | 512 | `messagesnetworkstatusv4tbl` | `did_lte_conn`, `did_sock_conn`, `send_success`, `rsrp`, `rsrq`, `band`, `bytes_sent`, `bytes_received` |
| `GPSConfMsg` | 524 | `configgpstbl` | `is_psm_enabled`, `is_aiding_enabled`, `gnss_update_freq`, `target_fix_accuracy`, `target_fix_pdop` |
| `GroundModeConfigV2` | 538 | `configgroundhistorytbl` | GPS heartbeat period, motion thresholds, motion timeouts |
| `BiometricConfig` | 558 | -- | Biometric sensor configuration |
| `DeviceMessageLog` | -- | `devicemessagestbl` | `record_id`, `is_uplink`, `message_uid`, `interface_type` -- generic message log entry |
| `AlphaHwFailureMsg` | 559 | `messagesalphahwfailtbl` | `xlr_fails`, `gps_fails`, `bms_fails`, `ppg_fails`, `imu_fails`, etc. |
| `CommsHwFailureMsg` | 549 | `messagescommshwfailtbl` | `sim_fails`, `sx1262_fails`, `ipc_fails`, `ext_flash_fails`, `sec_elem_fails` |
| `Sigma5HwFailureMsg` | 552 | `messagessigma5hwfailtbl` | Hardware failure counts for Sigma5 variant |

### BootMsgV2 Flag Decoding

The `BootMsgV2` class provides property-based flag decoding that is critical for validation:

```python
boot = BootMsgV2.last(device_id, db_env="VAL_1_0")

boot.boot_reason      # int: 0=normal, 1=exception, 2=FUOTA complete, 3=charger, ...
boot.boot_reason_str  # str: "Normal boot", "Reboot due to completing FUOTA", etc.
boot.flag_mcu         # int: 0=Comms Core, 1=App Core
boot.coprocessor_str  # str: "Comms Core" or "App Core"
boot.triggered_by     # bool: True if FW-triggered reset
```

Boot reason values relevant to validation:

| Value | Meaning | Validation Relevance |
|-------|---------|---------------------|
| 0 | Normal boot | Expected after power-on |
| 1 | Reboot due to exception | Failure indicator |
| 2 | Reboot due to completing FUOTA | Expected after firmware update |
| 3 | Reboot due to being placed on charger | Expected during charge tests |
| 6 | Reboot due to watchdog timer expiration | Failure indicator |

---

## 4. Database Access for Validation

### Direct ORM Access

The `CoreCloudDBInterface` provides a context-managed SQLAlchemy session with optional SSH tunneling:

```python
from corekinect.core_cloud.db_interface import CoreCloudDBInterface
from corekinect.core_cloud.db_orm_v1_0 import (
    Messagesboottbl,
    Fuotaprogresstbl,
    Fuotaplanstbl,
    Fuotasettingsperdevicetbl,
    Devicefirmwarecurrenttbl,
    Devicestbl,
)

# Connect to validation CoreCloud database
with CoreCloudDBInterface(db_env="VAL_1_0") as db:
    # Query device boot messages
    boot_msgs = db.query(Messagesboottbl) \
        .filter(Messagesboottbl.deviceid == 0x70B3D584C0201234) \
        .order_by(Messagesboottbl.recordid.desc()) \
        .limit(10) \
        .all()

    # Query current firmware versions for a device
    fw_versions = db.query(Devicefirmwarecurrenttbl) \
        .filter(Devicefirmwarecurrenttbl.deviceid == 0x70B3D584C0201234) \
        .all()

    # Query FUOTA progress
    progress = db.query(Fuotaprogresstbl) \
        .filter(Fuotaprogresstbl.deviceid == 0x70B3D584C0201234) \
        .all()
```

### Using the Message Wrapper Classes (Preferred)

The `msg_def_v1_0` message classes provide a higher-level, type-safe interface:

```python
from corekinect.core_cloud.msg_def_v1_0 import BootMsgV2, PositionMsgV6, NetworkStatusMsgV4
from datetime import datetime, timedelta

device_id = 0x70B3D584C0201234

# Get last boot message
boot = BootMsgV2.last(device_id, db_env="VAL_1_0")
print(f"Boot reason: {boot.boot_reason_str}, MCU: {boot.coprocessor_str}")

# Get position messages from last 10 minutes
start = datetime.utcnow() - timedelta(minutes=10)
positions = PositionMsgV6.since_server_time(device_id, start, db_env="VAL_1_0")

# Get network status messages since a specific record ID
net_msgs = NetworkStatusMsgV4.since_record_id(device_id, start_record_id=1000, db_env="VAL_1_0")
```

### SSH Tunneling (for remote DB access)

The DEV_1_0 namespace requires SSH tunneling (see `.env.example`). The VAL_1_0 namespace connects directly to `validation.ad.corekinect.com:5432`. The DB interface handles SSH tunnel setup/teardown automatically based on whether `SSH_HOST` is set:

```python
# If VAL_1_0_SSH_HOST is set in .env, tunneling happens automatically
# If not set, direct connection to VAL_1_0_DB_HOST:VAL_1_0_DB_PORT
with CoreCloudDBInterface(db_env="VAL_1_0") as db:
    # tunnel (if configured) is active for the duration of this block
    result = db.execute(text("SELECT 1"))
```

### FUOTA-Related Tables

| Table | Primary Key | Purpose | Key Columns |
|-------|------------|---------|-------------|
| `fuotaplanstbl` | `planid` | FUOTA plan definitions | `plandesc`, `devicetypeid`, `devicevariantid`, `timecreated` |
| `fuotaplanstagestbl` | `planid, updatestage` | Ordered stages within a plan | `stagedesc`, `skippable` |
| `fuotaplanstagetargetstbl` | `planid, updatestage, appid` | Target FW version per stage per app | `majorversion`, `minorversion`, `revision`, `releasetrack`, `ismfg`, `updateorder` |
| `fuotaprogresstbl` | `deviceid, appid` | Current FUOTA progress per device per app | `majorversion`, `minorversion`, `revision`, `pagesapplied`, `totalpages`, `timestarted`, `lastupdated` |
| `fuotaprogresshistorytbl` | `recordid` | Historical FUOTA progress (indexed by deviceid) | Same as progress + `timefinished` |
| `fuotasettingsperdevicetbl` | `deviceid` | Per-device FUOTA configuration | `planid`, `enablefuota`, `maxstage` |
| `fuotasettingsperdevicetypetbl` | `devicetypeid, devicevariantid, accountid` | Per-device-type FUOTA defaults | `planid`, `enablefuota`, `maxstage` |

### Firmware Version Tables

| Table | Primary Key | Purpose |
|-------|------------|---------|
| `devicefirmwarecurrenttbl` | `deviceid, appid` | Current firmware version per app per device |
| `devicefirmwarehistorytbl` | `recordid` | Historical firmware version changes |
| `devicefirmwareappidstbl` | `devicetypeid, devicevariantid, appid` | Maps app IDs to device types |

---

## 5. Validation CoreCloud Environment

### Namespace: `VAL_1_0`

A dedicated CoreCloud v1.0 instance for automated validation testing, isolated from manufacturing (`DEV_1_0`) and production systems.

| Property | Value |
|----------|-------|
| Namespace | `VAL_1_0` |
| Auth Server | `https://auth.office.corekinect.cloud:2013` |
| REST Server | `https://val.office.corekinect.cloud:2018/api` |
| DB Host | `validation.ad.corekinect.com:5432` |
| DB Driver | `postgresql+psycopg2` |
| Purpose | Automated test execution without interference with mfg/production |

### Isolation Guarantees

- Devices registered in `VAL_1_0` do not appear in `DEV_1_0` or production
- FUOTA plans created in `VAL_1_0` are scoped to the validation database
- Messages sent by DUTs connected to the validation Socket Server are stored in the validation database only
- The validation instance can be reset/wiped between test runs without affecting other environments

### Environment Variable Prefixing

The SDK uses namespace prefixes to resolve the correct environment:

```
VAL_1_0_DB_HOST       → DB_HOST       (when db_env="VAL_1_0")
VAL_1_0_API_KEY       → API_KEY       (when env_namespace="VAL_1_0")
VAL_1_0_SSH_HOST      → SSH_HOST      (when db_env="VAL_1_0")
```

This prefixing system, implemented in `_apply_namespace_env()` in both `api_interface.py` and `db_interface.py`, copies namespaced env vars to the unprefixed keys that `AuthConfig`, `ApiConfig`, `DBConfig`, and `SSHConfig` read.

---

## 6. Message Verification Pattern for Stage 4

Stage 4 tests verify device behavior by checking messages received at CoreCloud after physical actions (power-on, FUOTA, button press, sensor stimulus, etc.).

### General Polling Pattern

```python
import time
from datetime import datetime

def wait_for_message(msg_class, device_id, predicate, timeout_s=120, poll_interval_s=5, db_env="VAL_1_0"):
    """
    Poll CoreCloud for a message matching a predicate.

    Args:
        msg_class: Message class (e.g., BootMsgV2, PositionMsgV6)
        device_id: Device ID as integer (e.g., 0x70B3D584C0201234)
        predicate: Callable that takes a message instance and returns bool
        timeout_s: Maximum time to wait in seconds
        poll_interval_s: Time between polls in seconds
        db_env: CoreCloud namespace

    Returns:
        The first message matching the predicate

    Raises:
        TimeoutError: If no matching message arrives within timeout
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        msg = msg_class.last(device_id, db_env=db_env)
        if msg and predicate(msg):
            return msg
        time.sleep(poll_interval_s)
    raise TimeoutError(
        f"No {msg_class.__name__} matching predicate for device "
        f"{device_id:#X} within {timeout_s}s"
    )
```

### Boot Verification (Post-FUOTA)

```python
from corekinect.core_cloud.msg_def_v1_0 import BootMsgV2

def verify_boot_after_fuota(device_id, expected_boot_reason=2, timeout_s=120):
    """
    Wait for a BootMsgV2 with boot_reason=2 (FUOTA complete) after firmware update.

    Args:
        device_id: Integer device ID
        expected_boot_reason: 2 = "Reboot due to completing FUOTA"
        timeout_s: Maximum wait time

    Returns:
        BootMsgV2 instance
    """
    return wait_for_message(
        BootMsgV2,
        device_id,
        predicate=lambda b: b.boot_reason == expected_boot_reason,
        timeout_s=timeout_s,
    )
```

### Position Verification (Post-GPS Test)

```python
from corekinect.core_cloud.msg_def_v1_0 import PositionMsgV6
from datetime import datetime

def verify_valid_gps_fix(device_id, min_satellites=4, max_accuracy_m=50, timeout_s=300):
    """
    Wait for a PositionMsgV6 with a valid GPS fix.
    GPS acquisition can take several minutes, so default timeout is 300s.
    """
    return wait_for_message(
        PositionMsgV6,
        device_id,
        predicate=lambda p: (
            p.gnss_fix_ok
            and p.num_sat >= min_satellites
            and p.horizontal_accuracy <= max_accuracy_m
            and p.latitude is not None
            and p.longitude is not None
        ),
        timeout_s=timeout_s,
        poll_interval_s=10,
    )
```

### Biometric Verification (Post-On-Skin Test)

```python
from corekinect.core_cloud.msg_def_v1_0 import BiometricDataMsg

def verify_biometric_data(device_id, min_hr=40, max_hr=200, timeout_s=120):
    """
    Wait for a BiometricDataMsg with valid heart rate and SpO2.
    """
    return wait_for_message(
        BiometricDataMsg,
        device_id,
        predicate=lambda b: (
            b.on_body
            and b.heart_rate is not None
            and min_hr <= b.heart_rate <= max_hr
            and b.spo2 is not None
            and 70 <= b.spo2 <= 100
        ),
        timeout_s=timeout_s,
    )
```

### Network Connectivity Verification

```python
from corekinect.core_cloud.msg_def_v1_0 import NetworkStatusMsgV4

def verify_network_connection(device_id, timeout_s=120):
    """
    Wait for a NetworkStatusMsgV4 confirming successful LTE + socket connection.
    """
    return wait_for_message(
        NetworkStatusMsgV4,
        device_id,
        predicate=lambda n: n.did_lte_conn and n.did_sock_conn and n.send_success,
        timeout_s=timeout_s,
    )
```

### Hardware Failure Check

```python
from corekinect.core_cloud.msg_def_v1_0 import AlphaHwFailureMsg

def check_no_hw_failures(device_id, since_time):
    """
    Verify no hardware failure messages since a given time.
    Returns list of failure messages (empty = pass).
    """
    failures = AlphaHwFailureMsg.since_server_time(device_id, since_time, db_env="VAL_1_0")
    return failures  # caller checks len(failures) == 0
```

### Key Verification Patterns Summary

| Verification | Message Class | Predicate Focus | Typical Timeout |
|-------------|---------------|----------------|-----------------|
| Boot after power-on | `BootMsgV2` | `boot_reason == 0`, MCU type | 60s |
| Boot after FUOTA | `BootMsgV2` | `boot_reason == 2` | 120s |
| GPS fix | `PositionMsgV6` | `gnss_fix_ok`, `num_sat`, accuracy | 300s |
| Biometrics on-body | `BiometricDataMsg` | `on_body`, HR range, SpO2 range | 120s |
| Network uplink | `NetworkStatusMsgV4` | `did_lte_conn`, `send_success` | 120s |
| No HW failures | `AlphaHwFailureMsg` | No messages since test start | N/A (query) |
| Config confirmed | `GPSConfMsg` (DB query) | `lastconfirmed` is not None | 120s |

---

## 7. FUOTA Management Gap Analysis

### What We CAN Do Today

| Capability | Method | Notes |
|-----------|--------|-------|
| Query device messages | `msg_def_v1_0` classes (`.last()`, `.since_*()`) | Full query API available |
| Query FUOTA progress | DB ORM: `Fuotaprogresstbl` | `pagesapplied` / `totalpages` for completion tracking |
| Read FUOTA plans/stages/targets | DB ORM: `Fuotaplanstbl` + relationships | Full plan structure readable |
| Read current firmware versions | DB ORM: `Devicefirmwarecurrenttbl` | Version per app ID |
| Send GPS config via REST | `GPSConfMsg.send_via_rest()` | Only config endpoint implemented in SDK |
| Authenticate to REST API | `CoreCloudRestInterface` | Full auth flow with token refresh |
| Make arbitrary REST calls | `CoreCloudRestInterface.request(method, path, ...)` | Generic method available |

### What We CANNOT Do Today (SDK Gaps)

| Capability | Gap Type | Notes |
|-----------|----------|-------|
| Register devices via REST | SDK gap -- endpoint exists in C# server (`POST /System/Devices/Register`) but no Python wrapper | Need to add wrapper to `api_interface.py` or `msg_def_v1_0.py` |
| Create FUOTA plans via REST | Unknown -- may need new C# endpoint | Could use DB ORM as fallback but bypasses server validation |
| Set device FUOTA settings via REST | Unknown -- may need new C# endpoint | Same concern re: bypassing validation |
| Trigger immediate FUOTA evaluation | Unknown -- Singleton runs on schedule | May need new C# endpoint or direct DB flag |
| Query device status via REST | SDK gap -- endpoint likely exists | Need to add wrapper |
| Create/modify device type variants via REST | Unknown | Likely needed for test setup |

### Proposed Solutions (Priority Order)

**Option 1: Extend the Python SDK REST wrappers (preferred)**

Add methods to `CoreCloudRestInterface` or create new message classes that call existing C# REST Server endpoints:

```python
# Proposed additions to api_interface.py or a new device_management.py module

class CoreCloudRestInterface:
    # ... existing code ...

    def register_device(self, device_id: str, device_type_id: int,
                       device_variant_id: int, account_id: int) -> Response:
        """Register a device with CoreCloud."""
        return self.request("POST", "/System/Devices/Register", json={
            "deviceId": device_id,
            "deviceTypeId": device_type_id,
            "deviceVariantId": device_variant_id,
            "accountId": account_id,
        })

    def get_device_status(self, device_id: str) -> Response:
        """Get current device status."""
        return self.request("GET", "/System/Devices/Status",
                          params={"deviceId": device_id})
```

**Option 2: Direct DB access via ORM (fallback)**

Use SQLAlchemy ORM to insert/update records directly. This works but bypasses server-side business logic:

```python
with CoreCloudDBInterface(db_env="VAL_1_0") as db:
    # Create FUOTA plan directly in DB
    plan = Fuotaplanstbl(
        plandesc="Validation FUOTA Plan",
        devicetypeid=1,
        devicevariantid=1,
        timecreated=datetime.utcnow(),
        lastmodified=datetime.utcnow(),
    )
    db.add(plan)
    db.commit()
```

**Option 3: Request new C# endpoints**

If REST endpoints do not exist for FUOTA plan management, coordinate with the CoreCloud backend team to add them.

### Recommendation

Use **Option 1** for device registration and status queries (the C# endpoints exist, we just need Python wrappers). Use **Option 2** as a pragmatic fallback for FUOTA plan setup in the validation environment, where bypassing business logic is acceptable because the validation instance is isolated. Pursue **Option 3** for production-path FUOTA management in parallel.

---

## 8. Validation Pipeline CoreCloud Integration Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ Validation Pipeline (K8s Pod)                                │
│                                                              │
│  ┌───────────────┐    ┌──────────────────┐                  │
│  │ Test Runner    │    │ CoreCloud Client  │                  │
│  │ (pytest)       │◄──►│ (Python SDK)      │                  │
│  └───────┬───────┘    └────────┬─────────┘                  │
│          │                     │                             │
│          │  MTIB gRPC          │  REST API + DB ORM          │
│          ▼                     ▼                             │
│  ┌───────────────┐    ┌──────────────────┐                  │
│  │ MTIB V2       │    │ Validation       │                  │
│  │ Client        │    │ CoreCloud Client │                  │
│  │ (gRPC)        │    │ (VAL_1_0)        │                  │
│  └───────┬───────┘    └────────┬─────────┘                  │
│          │                     │                             │
└──────────┼─────────────────────┼─────────────────────────────┘
           │                     │
           ▼                     ▼
    ┌──────────────┐    ┌────────────────────────┐
    │ MTIB V2      │    │ CoreCloud v1.0 Server  │
    │ Server       │    │ (validation instance)  │
    │ (edge node)  │    │                        │
    └──────┬───────┘    │  ┌─────────────────┐   │
           │            │  │ REST Server     │   │
           ▼            │  │ Socket Server   │   │
    ┌──────────────┐    │  │ Time Server     │   │
    │ Alpha DUT    │    │  │ Singleton       │   │
    │ (product     │◄──►│  │ PostgreSQL DB   │   │
    │  board)      │    │  └─────────────────┘   │
    └──────────────┘    └────────────────────────┘
```

### Data Flow for a Typical Stage 4 Test

1. **Test Runner** instructs **MTIB V2 Client** to power on the DUT
2. **MTIB V2 Client** sends gRPC command to **MTIB V2 Server** on the edge node
3. **MTIB V2 Server** enables power rails (4.5V battery sim, 5V USB/charge)
4. **Alpha DUT** boots, connects to **CoreCloud Socket Server** via LTE
5. **Alpha DUT** sends `BootMsgV2` uplink
6. **Test Runner** polls **CoreCloud** (via `BootMsgV2.last()`) to verify boot
7. **Test Runner** may trigger FUOTA (via REST or DB) and wait for completion
8. **Test Runner** verifies post-FUOTA boot message with `boot_reason == 2`

### Integration Points

| Integration | Protocol | SDK Module | Direction |
|------------|----------|-----------|-----------|
| Test Runner -> MTIB | gRPC | `corekinect.mtib_client` | Command (power, UART, GPIO) |
| Test Runner -> CoreCloud REST | HTTPS | `corekinect.core_cloud.api_interface` | Config, device mgmt |
| Test Runner -> CoreCloud DB | PostgreSQL (SQLAlchemy) | `corekinect.core_cloud.db_interface` | Message queries, FUOTA queries |
| DUT -> CoreCloud | TLS Socket | N/A (device firmware) | Uplink messages, FUOTA delivery |

---

## 9. Required CoreCloud Client Methods for Stage 4

The following table lists the methods needed in the validation pipeline's CoreCloud client layer, mapped to their implementation path:

### Device Management

| Method | Purpose | Implementation |
|--------|---------|---------------|
| `register_device(device_id, device_type_id, device_variant_id, account_id)` | Register DUT with validation CoreCloud | REST: `POST /System/Devices/Register` (needs SDK wrapper) |
| `get_device_status(device_id)` | Query device connection state, last seen | REST: `GET /System/Devices/Status` (needs SDK wrapper) |
| `get_device_firmware_versions(device_id)` | Current FW versions from DB | DB ORM: `Devicefirmwarecurrenttbl` query |

### FUOTA Management

| Method | Purpose | Implementation |
|--------|---------|---------------|
| `create_fuota_plan(description, device_type_id, device_variant_id, stages)` | Create FUOTA plan for validation | DB ORM: Insert into `fuotaplanstbl` + `fuotaplanstagestbl` + `fuotaplanstagetargetstbl` |
| `set_device_fuota_settings(device_id, plan_id, enable, max_stage)` | Configure device FUOTA enrollment | DB ORM: Insert/update `fuotasettingsperdevicetbl` |
| `get_fuota_progress(device_id)` | Check FUOTA page delivery progress | DB ORM: `Fuotaprogresstbl` query |
| `is_fuota_complete(device_id, app_id)` | Check if `pagesapplied == totalpages` | DB ORM: `Fuotaprogresstbl` query |

### Message Verification

| Method | Purpose | Implementation |
|--------|---------|---------------|
| `wait_for_boot(device_id, predicate, timeout)` | Wait for device boot message matching criteria | `BootMsgV2.last()` polling loop |
| `wait_for_position(device_id, predicate, timeout)` | Wait for valid GPS fix | `PositionMsgV6.last()` polling loop |
| `wait_for_biometric(device_id, predicate, timeout)` | Wait for biometric data | `BiometricDataMsg.last()` polling loop |
| `wait_for_network(device_id, predicate, timeout)` | Wait for successful network connection | `NetworkStatusMsgV4.last()` polling loop |
| `query_messages(device_id, msg_class, since_time)` | Get all messages of a type since a time | `msg_class.since_server_time()` |
| `check_hw_failures(device_id, since_time)` | Get hardware failure messages | `AlphaHwFailureMsg.since_server_time()` |

### Configuration

| Method | Purpose | Implementation |
|--------|---------|---------------|
| `send_gps_config(device_id, config)` | Send GPS configuration | `GPSConfMsg.send_via_rest()` (already implemented) |
| `send_ground_config(device_id, config)` | Send ground mode configuration | Needs SDK wrapper for REST endpoint |

---

## 10. FUOTA Workflow for Validation

### FUOTA Delivery Sequence

```
Validation Pipeline                 CoreCloud v1.0              DUT (Alpha)
       │                                  │                         │
       │  1. Create FUOTA plan (DB)       │                         │
       │─────────────────────────────────►│                         │
       │                                  │                         │
       │  2. Set device FUOTA settings    │                         │
       │─────────────────────────────────►│                         │
       │                                  │                         │
       │                                  │  3. Singleton evaluates │
       │                                  │     FUOTA eligibility   │
       │                                  │────────────┐            │
       │                                  │◄───────────┘            │
       │                                  │                         │
       │                                  │  4. FW chunks queued    │
       │                                  │                         │
       │                                  │  5. DUT connects via    │
       │                                  │     socket              │
       │                                  │◄────────────────────────│
       │                                  │                         │
       │                                  │  6. FW chunks delivered │
       │                                  │────────────────────────►│
       │                                  │                         │
       │                                  │  7. DUT applies FW,    │
       │                                  │     reboots             │
       │                                  │                         │────┐
       │                                  │                         │◄───┘
       │                                  │                         │
       │                                  │  8. BootMsgV2           │
       │                                  │     (boot_reason=2)     │
       │                                  │◄────────────────────────│
       │                                  │                         │
       │  9. Poll for boot message        │                         │
       │─────────────────────────────────►│                         │
       │  10. Verify FW version           │                         │
       │◄─────────────────────────────────│                         │
```

### FUOTA Progress Tracking

The `fuotaprogresstbl` tracks page-level delivery progress:

```python
with CoreCloudDBInterface(db_env="VAL_1_0") as db:
    progress = db.query(Fuotaprogresstbl).filter(
        Fuotaprogresstbl.deviceid == device_id,
        Fuotaprogresstbl.appid == app_id,
    ).first()

    if progress:
        percent = (progress.pagesapplied / progress.totalpages) * 100
        print(f"FUOTA progress: {progress.pagesapplied}/{progress.totalpages} "
              f"({percent:.1f}%) - started {progress.timestarted}")

        if progress.pagesapplied == progress.totalpages:
            print("FUOTA delivery complete, waiting for reboot...")
```

### FUOTA Plan Structure

A FUOTA plan consists of:

1. **Plan** (`fuotaplanstbl`): Top-level definition scoped to a device type/variant
2. **Stages** (`fuotaplanstagestbl`): Ordered update stages (e.g., Stage 1: bootloader, Stage 2: app FW)
3. **Stage Targets** (`fuotaplanstagetargetstbl`): Target FW version per app ID per stage
4. **Device Settings** (`fuotasettingsperdevicetbl`): Per-device enrollment with plan ID, enable flag, and max stage

```python
# Example: Creating a validation FUOTA plan via DB ORM
from datetime import datetime
from corekinect.core_cloud.db_orm_v1_0 import (
    Fuotaplanstbl, Fuotaplanstagestbl, Fuotaplanstagetargetstbl,
    Fuotasettingsperdevicetbl,
)

with CoreCloudDBInterface(db_env="VAL_1_0") as db:
    now = datetime.utcnow()

    # Create plan
    plan = Fuotaplanstbl(
        plandesc="Validation: Alpha B0 -> v2.1.0",
        devicetypeid=ALPHA_DEVICE_TYPE_ID,
        devicevariantid=ALPHA_B0_VARIANT_ID,
        timecreated=now,
        lastmodified=now,
    )
    db.add(plan)
    db.flush()  # get planid

    # Create stage
    stage = Fuotaplanstagestbl(
        planid=plan.planid,
        updatestage=1,
        stagedesc="App FW update to v2.1.0",
        timecreated=now,
        lastmodified=now,
        skippable=False,
    )
    db.add(stage)

    # Create stage target
    target = Fuotaplanstagetargetstbl(
        planid=plan.planid,
        updatestage=1,
        appid=APP_CORE_APP_ID,
        releasetrack=0,
        ismfg=False,
        majorversion=2,
        minorversion=1,
        revision=0,
        updateorder=0,
    )
    db.add(target)

    # Enroll device
    settings = Fuotasettingsperdevicetbl(
        deviceid=DEVICE_ID,
        planid=plan.planid,
        enablefuota=True,
        maxstage=1,
        timecreated=now,
    )
    db.add(settings)
    db.commit()
```

---

## 11. Pytest Integration Pattern

### Fixture Structure

```python
# conftest.py for Stage 4 tests
import pytest
from corekinect.core_cloud.api_interface import CoreCloudRestInterface
from corekinect.core_cloud.db_interface import CoreCloudDBInterface

CC_NAMESPACE = "VAL_1_0"


@pytest.fixture(scope="session")
def cc_rest():
    """Session-scoped CoreCloud REST client."""
    with CoreCloudRestInterface(env_namespace=CC_NAMESPACE) as api:
        yield api


@pytest.fixture(scope="session")
def cc_db():
    """Session-scoped CoreCloud DB session."""
    with CoreCloudDBInterface(db_env=CC_NAMESPACE) as db:
        yield db


@pytest.fixture
def device_id(request):
    """Device ID for the current DUT under test."""
    return request.config.getoption("--device-id")
```

### Test Example

```python
# test_stage4_boot.py
from corekinect.core_cloud.msg_def_v1_0 import BootMsgV2, NetworkStatusMsgV4


def test_device_boots_and_connects(device_id, mtib_client):
    """Verify DUT boots and establishes CoreCloud connection."""

    # Power on DUT via MTIB
    mtib_client.power_enable(channel=0, voltage_v=4.5)
    mtib_client.power_enable(channel=1)

    # Wait for boot message at CoreCloud
    boot = wait_for_message(
        BootMsgV2, device_id,
        predicate=lambda b: b.boot_reason == 0,  # normal boot
        timeout_s=60,
    )
    assert boot is not None, "DUT did not send boot message"
    assert boot.boot_reason == 0, f"Unexpected boot reason: {boot.boot_reason_str}"
    assert boot.num_exceptions == 0, f"Device reported {boot.num_exceptions} exceptions"

    # Wait for network status confirming socket connection
    net = wait_for_message(
        NetworkStatusMsgV4, device_id,
        predicate=lambda n: n.did_sock_conn and n.send_success,
        timeout_s=120,
    )
    assert net.did_lte_conn, "LTE connection failed"
    assert net.did_sock_conn, "Socket connection failed"
    assert net.send_success, "Message send failed"
```

---

## 12. Open Questions

| # | Question | Impact | Owner |
|---|----------|--------|-------|
| 1 | What are the validation CoreCloud server URLs for Socket Server and Time Server? | DUT firmware must be configured to connect to validation instance, not production | Firmware / CoreCloud team |
| 2 | Is SSH tunneling required for DB access from K8s pods, or is direct PostgreSQL connectivity available? | Determines whether `VAL_1_0_SSH_*` env vars are needed in the K8s deployment | DevOps / CoreCloud team |
| 3 | What API key and service account credentials will the validation pipeline use? | Needs to be provisioned and stored as K8s secrets | CoreCloud team |
| 4 | Are there rate limits on REST API calls that could affect test throughput? | The SDK supports `API_RATE_LIMIT_QPS` throttling but needs correct values | CoreCloud team |
| 5 | Can a "test account" be created in validation CoreCloud for automated testing? | Device registration requires an `accountid` | CoreCloud team |
| 6 | Does the Socket Server support multiple simultaneous device connections for parallel testing? | Affects whether we can test multiple DUTs concurrently against the same CoreCloud instance | CoreCloud team |
| 7 | What `devicetypeid` and `devicevariantid` values correspond to Alpha B0? | Needed for FUOTA plan creation and device registration | CoreCloud team / DB query |
| 8 | What `appid` values are assigned to the Alpha's App Core and Comms Core? | Needed for FUOTA stage target configuration and firmware version tracking | CoreCloud team / `devicefirmwareappidstbl` query |
| 9 | Does the Singleton FUOTA evaluator run on a fixed schedule, and can it be triggered on demand? | Determines latency between FUOTA plan setup and actual delivery start | CoreCloud team |
| 10 | What DUT firmware configuration is needed to point at the validation CoreCloud instance? | Socket server URL, time server URL, and TLS certificates must match validation env | Firmware team |

---

## Appendix A: ORM Table Quick Reference

### Core Device Tables

```
accountstbl ─── 1:N ──► devicestbl ─── 1:N ──► devicemessagestbl
                            │                        │
                            │                   ┌────┴────┐
                            │                   │ extends  │
                            ▼                   ▼         ▼
                 devicefirmwarecurrenttbl   messagesboottbl
                                           messagespositionv5tbl
                                           messagesbiometricdatatbl
                                           messagesnetworkstatusv4tbl
                                           messagesalphahwfailtbl
                                           messagescommshwfailtbl
                                           ... (15+ message tables)
```

### FUOTA Tables

```
fuotaplanstbl ─── 1:N ──► fuotaplanstagestbl
      │
      ├── 1:N ──► fuotaplanstagetargetstbl
      │
      ├── 1:N ──► fuotasettingsperdevicetbl ──► devicestbl
      │
      └── 1:N ──► fuotasettingsperdevicetypetbl ──► devicetypevarianttbl
```

### Progress Tracking

```
fuotaprogresstbl ──── (deviceid, appid) ──── current delivery state
fuotaprogresshistorytbl ──── historical delivery records (indexed by deviceid)
```

---

## Appendix B: SDK Source File Locations

| File | Absolute Path |
|------|--------------|
| REST Interface | `libs/python/corekinect/core_cloud/api_interface.py` |
| DB Interface | `libs/python/corekinect/core_cloud/db_interface.py` |
| Message Definitions (v1.0) | `libs/python/corekinect/core_cloud/msg_def_v1_0.py` |
| ORM Definitions (v1.0) | `libs/python/corekinect/core_cloud/db_orm_v1_0.py` |
| Environment Template | `libs/python/corekinect/core_cloud/.env.example` |
| SDK README | `libs/python/corekinect/core_cloud/READ_ME.md` |
