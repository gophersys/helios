# CoreCloud Library Architecture

> Architecture analysis and restructuring proposal for the CoreCloud Python SDK
> (`libs/python/corekinect/core_cloud/`). This document captures the current state
> of the library, identifies v0.9 deadweight that can be removed, proposes a
> v1.0-only target structure, catalogs missing capabilities needed for the
> validation pipeline (FUOTA management, sessions, Ground Mode Config V2), and
> lists open questions for the CoreCloud backend team.
>
> **This is a documentation-only analysis. No code changes are proposed here.**

---

## 1. Current State

### 1.1 Module Inventory

```
libs/python/corekinect/core_cloud/
├── __init__.py              # Empty (__all__ = [])
├── READ_ME.md               # User guide with usage examples
├── .env.example             # Environment variable template (3 namespaces)
├── api_interface.py          # REST API client (auth, rate limiting, singleton)
├── db_interface.py           # Database connector (SQLAlchemy, SSH tunnel)
├── db_orm_v1_0.py            # v1.0 SQLAlchemy ORM models (PostgreSQL)
├── db_orm_v0_9.py            # v0.9 legacy ORM models (MySQL)
├── msg_def_v1_0.py           # v1.0 message classes + DB query helpers
└── msg_def_v0_9.py           # v0.9 legacy message classes (MySQL backend)
```

### 1.2 Dependency Graph

```
msg_def_v1_0.py ─────────────────────────────────────────────┐
  ├── db_interface.py                                         │
  │     └── sqlalchemy, sshtunnel, dotenv                     │
  ├── api_interface.py                                        │
  │     └── requests, dotenv                                  │
  ├── db_orm_v1_0.py                                          │
  │     └── sqlalchemy ORM (DeclarativeBase, Mapped, mapped_column)
  └── corekinect.utils (Serializable, EnvConfig, SingletonThreadSafeMeta)

msg_def_v0_9.py ──────────────────────────────────────────────┐
  ├── db_interface.py (shared with v1.0)                      │
  ├── db_orm_v0_9.py                                          │
  │     └── sqlalchemy ORM (declarative_base, Column) — legacy syntax
  └── corekinect.utils (shared)
```

### 1.3 Design Patterns

| Pattern | Implementation | Location |
|---------|---------------|----------|
| Singleton + Context Manager | `SingletonThreadSafeMeta` with `__enter__`/`__exit__`, `_depth` reentry guard, `atexit` cleanup | `api_interface.py`, `db_interface.py` |
| Frozen Dataclass + ORM Mapping | `@dataclass(frozen=True, slots=True)` with `orm_field_map` dict for column aliasing | All `msg_def_*.py` classes |
| API Payload Marshalling | Bidirectional `to_api_payload()`/`from_api_payload()` with `api_field_map` and `api_types` coercion | `ConfMsgBase` subclasses |
| Version-Parallel APIs | v0.9 and v1.0 expose identical class names and method signatures; internal ORM differs | `msg_def_v0_9.py` mirrors `msg_def_v1_0.py` |
| Namespace-Based Config | Env vars prefixed by namespace (`VAL_1_0_DB_HOST`, `DEV_1_0_API_KEY`, etc.) | All interface modules |

### 1.4 Environment Namespaces

| Namespace | Backend | Database | Purpose |
|-----------|---------|----------|---------|
| `VAL_1_0` | PostgreSQL | `validation.ad.corekinect.com:5432` | Validation environment (Stage 4 pipeline target) |
| `DEV_1_0` | PostgreSQL | via SSH tunnel through `dmz-pg02.dmz.corekinect.com` | Development/office environment |
| `DEV_0_9` | MySQL | `coreserver005.ad.corekinect.com:3306` | Legacy v0.9 (MySQL) |

### 1.5 Public API Surface

#### Message Query Interface (`MsgBase` classmethods)

```python
# Get the most recent message for a device
msg = SomeMsg.last(device_id, db_env="VAL_1_0")

# Messages within a server-time window
msgs = SomeMsg.since_server_time(device_id, start, end, db_env="VAL_1_0")

# Messages within a device-time window
msgs = SomeMsg.since_device_time(device_id, start, end, db_env="VAL_1_0")

# Messages within a record ID range
msgs = SomeMsg.since_record_id(device_id, start_id, end_id, db_env="VAL_1_0")
```

#### Config Send Interface (`ConfMsgBase` methods)

```python
# Send configuration via REST
resp = cfg.send_via_rest(device_id=id, env_namespace="VAL_1_0")

# Search configurations via REST
resp = SomeConf.search_via_rest(criteria, env_namespace="VAL_1_0")
```

#### Context Managers

```python
# Database session (raw ORM access)
with CoreCloudDBInterface(db_env="VAL_1_0") as session:
    result = session.query(SomeTable).filter(...).all()

# REST API client (authenticated HTTP)
with CoreCloudRestInterface(env_namespace="VAL_1_0") as api:
    resp = api.request("GET", "/System/Devices/Status", params={...})
```

### 1.6 Message Types (v1.0)

| Class | UID | ORM Table | Key Fields |
|-------|-----|-----------|------------|
| `BootMsgV2` | 548 | `messagesboottbl` | `time_of_boot`, `flags` (MCU type, boot reason), `num_exceptions` |
| `PositionMsgV6` | 556 | `messagespositionv5tbl` | `latitude`, `longitude`, `gps_altitude`, `horizontal_accuracy`, `num_sat`, `fix_type` |
| `BiometricDataMsg` | 557 | `messagesbiometricdatatbl` | `heart_rate`, `spo2`, `skin_temperature`, `on_body` |
| `NetworkStatusMsgV4` | 512 | `messagesnetworkstatusv4tbl` | `did_lte_conn`, `did_sock_conn`, `send_success`, `rsrp` |
| `GPSConfMsg` | 524 | `configgpstbl` | `is_psm_enabled`, `gnss_update_freq`, `target_fix_accuracy` |
| `GroundModeConfigV2` | 538 | `configgroundhistorytbl` | GPS heartbeat period, motion thresholds |
| `AlphaHwFailureMsg` | 559 | `messagesalphahwfailtbl` | `xlr_fails`, `gps_fails`, `bms_fails`, `ppg_fails`, `imu_fails` |
| `CommsHwFailureMsg` | 549 | `messagescommshwfailtbl` | `sim_fails`, `sx1262_fails`, `ipc_fails`, `ext_flash_fails` |
| `Sigma5HwFailureMsg` | 552 | `messagessigma5hwfailtbl` | Sigma5 variant hardware failure counts |
| `DeviceMessageLog` | -- | `devicemessagestbl` | `record_id`, `is_uplink`, `message_uid`, `interface_type` |

---

## 2. v0.9 Deadweight Analysis

### 2.1 What v0.9 Contains

The v0.9 modules (`msg_def_v0_9.py` + `db_orm_v0_9.py`) provide a MySQL-backed
alternative that mirrors the v1.0 API surface. They were needed historically when
the codebase targeted both the legacy MySQL-based CoreCloud and the newer
PostgreSQL-based v1.0.

| Module | Lines | ORM Tables | Message Classes |
|--------|-------|------------|----------------|
| `db_orm_v0_9.py` | ~250 | 7 (MySQL, `declarative_base()` syntax) | -- |
| `msg_def_v0_9.py` | ~600 | -- | 7 (`BootMsgV2`, `PositionMsgV6`, `HipsDataMsg`, `BiometricDataMsg`, `NetworkStatusMsgV4`, `HardwareFailureV2Msg`, `GroundConfigV2`) |

### 2.2 Why v0.9 Is Deadweight for Validation

1. **Validation uses `VAL_1_0` exclusively.** The validation pipeline targets the
   v1.0 CoreCloud instance. There is no v0.9 validation environment.
2. **No new development on v0.9.** No new message types, FUOTA tables, or REST
   endpoints will be added to the MySQL backend.
3. **Maintenance burden.** Any API change to `MsgBase` must be replicated across
   both `msg_def_v1_0.py` and `msg_def_v0_9.py`. The v0.9 module imports from
   `db_orm_v0_9.py` using legacy MySQL table names (`JumpTrack1CMsgTbl`,
   `JumpTrackBootMessageTbl`, etc.) that predate the standardized naming.
4. **Import side effects.** Even if test code only uses v1.0 imports, having v0.9
   present means the MySQL ORM models are registered with SQLAlchemy metadata,
   adding startup cost and potential confusion.

### 2.3 Recommendation

**Keep v0.9 modules but freeze them.** The v0.9 modules may still be used by
internal tools or ad-hoc scripts that query the legacy database. Rather than
deleting them:

- Mark `msg_def_v0_9.py` and `db_orm_v0_9.py` as frozen/deprecated (docstring +
  module-level comment)
- Do not add new message types to v0.9
- Do not extend the v0.9 `MsgBase` with new query methods
- New validation pipeline code imports exclusively from `msg_def_v1_0`
- The `DEV_0_9` namespace remains in `.env.example` for backward compatibility
  but is not used by the validation pipeline

---

## 3. Proposed v1.0 Target Structure

### 3.1 Current vs Proposed Layout

```
Current:                              Proposed:
core_cloud/                           core_cloud/
├── __init__.py                       ├── __init__.py          (typed re-exports)
├── api_interface.py                  ├── api_interface.py     (unchanged)
├── db_interface.py                   ├── db_interface.py      (unchanged)
├── db_orm_v1_0.py                    ├── db_orm_v1_0.py       (+ FUOTA message classes)
├── db_orm_v0_9.py         ◄ freeze   ├── db_orm_v0_9.py       (frozen, deprecated)
├── msg_def_v1_0.py                   ├── msg_def_v1_0.py      (+ new message types)
├── msg_def_v0_9.py        ◄ freeze   ├── msg_def_v0_9.py      (frozen, deprecated)
├── .env.example                      ├── fuota.py             (NEW: FUOTA plan management)
└── READ_ME.md                        ├── device_management.py (NEW: device registration/status)
                                      ├── .env.example
                                      └── READ_ME.md
```

### 3.2 New Module: `fuota.py`

A high-level FUOTA management module that wraps the existing ORM tables into a
validation-friendly API. This module is the primary new capability needed for
Stage 4.

**Proposed API surface:**

```python
class FuotaPlanBuilder:
    """Builds and persists FUOTA plans via direct DB ORM."""

    def create_plan(description, device_type_id, device_variant_id) -> int:
        """Create a FUOTA plan, return plan_id."""

    def add_stage(plan_id, stage_num, description, targets, skippable=False):
        """Add an ordered stage with firmware version targets."""

    def enroll_device(device_id, plan_id, max_stage, enable=True):
        """Set per-device FUOTA settings."""

    def disable_device(device_id):
        """Disable FUOTA for a device."""


class FuotaMonitor:
    """Polls FUOTA progress and firmware version state."""

    def get_progress(device_id, app_id) -> Optional[FuotaProgress]:
        """Current transfer progress (pages applied / total)."""

    def is_complete(device_id, app_id) -> bool:
        """True if pagesapplied == totalpages."""

    def wait_for_completion(device_id, app_id, timeout_s=600) -> bool:
        """Block until FUOTA transfer completes or timeout."""

    def get_current_firmware(device_id) -> Dict[int, FirmwareVersion]:
        """Current firmware version per app ID."""

    def verify_firmware_version(device_id, app_id, expected) -> bool:
        """Check if device reports expected firmware version."""
```

**Implementation path:** Direct DB ORM via `CoreCloudDBInterface` with
`VAL_1_0` namespace. The ORM tables (`Fuotaplanstbl`, `Fuotaplanstagestbl`,
`Fuotaplanstagetargetstbl`, `Fuotasettingsperdevicetbl`, `Fuotaprogresstbl`,
`Devicefirmwarecurrenttbl`) are already defined in `db_orm_v1_0.py`.

**Why DB ORM instead of REST:** No REST endpoints exist in the Python SDK for
FUOTA plan CRUD. The C# server may have endpoints, but they are undocumented.
Direct DB access works immediately and is acceptable in the isolated validation
environment. See Section 5.1 for the migration path to REST.

### 3.3 New Module: `device_management.py`

REST wrappers for device lifecycle operations that the C# server exposes but the
Python SDK does not wrap.

**Proposed API surface:**

```python
class DeviceManager:
    """Device registration and status via REST API."""

    def register_device(device_id, device_type_id, device_variant_id, account_id):
        """POST /System/Devices/Register"""

    def get_device_status(device_id) -> DeviceStatus:
        """GET /System/Devices/Status"""

    def get_device_firmware_versions(device_id) -> Dict[int, FirmwareVersion]:
        """Query devicefirmwarecurrenttbl via DB ORM."""
```

### 3.4 `__init__.py` Improvements

The current `__init__.py` exports nothing (`__all__ = []`). The proposed version
adds typed re-exports for discoverability:

```python
from corekinect.core_cloud.api_interface import CoreCloudRestInterface
from corekinect.core_cloud.db_interface import CoreCloudDBInterface
from corekinect.core_cloud.msg_def_v1_0 import (
    BootMsgV2,
    PositionMsgV6,
    BiometricDataMsg,
    NetworkStatusMsgV4,
    GPSConfMsg,
    # ... etc
)

__all__ = [
    "CoreCloudRestInterface",
    "CoreCloudDBInterface",
    "BootMsgV2",
    "PositionMsgV6",
    # ... etc
]
```

---

## 4. Missing Capabilities for Validation

### 4.1 FUOTA Management (Critical — Stage 4 blocker)

**Current state:** The ORM tables exist in `db_orm_v1_0.py` (11 FUOTA-related
tables). There are no Python wrapper classes, no REST wrappers, and no
convenience methods.

**What's needed:**

| Capability | Method | Underlying Access |
|-----------|--------|------------------|
| Create FUOTA plan | `FuotaPlanBuilder.create_plan()` | DB ORM: `Fuotaplanstbl` |
| Add plan stages with targets | `FuotaPlanBuilder.add_stage()` | DB ORM: `Fuotaplanstagestbl` + `Fuotaplanstagetargetstbl` |
| Enroll device in plan | `FuotaPlanBuilder.enroll_device()` | DB ORM: `Fuotasettingsperdevicetbl` |
| Monitor transfer progress | `FuotaMonitor.get_progress()` | DB ORM: `Fuotaprogresstbl` |
| Wait for completion | `FuotaMonitor.wait_for_completion()` | DB ORM: `Fuotaprogresstbl` polling |
| Verify post-FUOTA firmware | `FuotaMonitor.verify_firmware_version()` | DB ORM: `Devicefirmwarecurrenttbl` |
| Query transfer history | `FuotaMonitor.get_history()` | DB ORM: `Fuotaprogresshistorytbl` |

**The 12-step FUOTA validation flow** (defined in
[stage4-fuota-validation-flow.md](../validation/stage4-fuota-flow.md)) requires
all of these capabilities to orchestrate the firmware transition sequence.

### 4.2 Session / Device State Tracking

**Current state:** No session concept exists. Each `MsgBase.last()` call opens a
new DB connection (via the singleton pattern, which caches the engine but not
query context).

**What's needed for validation:**

| Capability | Why |
|-----------|-----|
| Record ID bookmarking | Tests need "messages since I last checked" semantics — `since_record_id()` exists but requires the caller to track the bookmark |
| Server time anchoring | Tests need "messages since test started" — `since_server_time()` exists but requires the caller to snapshot `datetime.utcnow()` |
| Multi-message correlation | A FUOTA transition produces boot messages from both MCUs (App Core and Comms Core); validation must correlate them by `flag_mcu` field |

**Proposed approach:** A lightweight `ValidationSession` context that tracks
start time, last-seen record IDs per message type, and provides
`messages_since_start()` and `new_messages()` helpers. This is a convenience
layer, not a fundamental architectural change.

```python
class ValidationSession:
    """Tracks message state across a validation test run."""

    def __init__(self, device_id: int, db_env: str = "VAL_1_0"):
        self.device_id = device_id
        self.db_env = db_env
        self.start_time = datetime.utcnow()
        self._bookmarks: Dict[Type[MsgBase], int] = {}

    def messages_since_start(self, msg_class: Type[MsgBase]) -> List[MsgBase]:
        """All messages of this type since session started."""
        return msg_class.since_server_time(
            self.device_id, self.start_time, db_env=self.db_env
        )

    def new_messages(self, msg_class: Type[MsgBase]) -> List[MsgBase]:
        """Messages since last call to new_messages() for this type."""
        bookmark = self._bookmarks.get(msg_class)
        if bookmark:
            msgs = msg_class.since_record_id(
                self.device_id, bookmark, db_env=self.db_env
            )
        else:
            msgs = self.messages_since_start(msg_class)
        if msgs:
            self._bookmarks[msg_class] = max(m.device_message_id for m in msgs)
        return msgs
```

### 4.3 Ground Mode Config V2

**Current state:** `GroundModeConfigV2` exists in `msg_def_v1_0.py` as a
message class mapped to `configgroundhistorytbl`. It supports DB reads.

**What's missing:** REST send capability. Stage 4 tests need to configure
ground mode parameters (GPS heartbeat period, motion detection thresholds,
motion timeouts) before running timing-sensitive product tests. The
`ConfMsgBase.send_via_rest()` infrastructure exists and works for `GPSConfMsg`
but has not been wired up for `GroundModeConfigV2`.

**What's needed:**

| Capability | Current | Needed |
|-----------|---------|--------|
| Read ground config from DB | Yes (`since_server_time`, `last`) | No change |
| Send ground config via REST | No | Add `api_endpoint`, `api_field_map`, `api_types` to `GroundModeConfigV2` |
| Search ground configs via REST | No | Add `search_endpoint`, `search_field_map` |

**Implementation:** Extend `GroundModeConfigV2` to inherit from `ConfMsgBase`
instead of `MsgBase`, then add the REST endpoint path and field maps following
the same pattern as `GPSConfMsg`. Requires knowing the C# REST endpoint path
for ground configuration.

### 4.4 New Message Types Needed

The validation pipeline exercises device behaviors that produce message types
not yet wrapped in `msg_def_v1_0.py`:

| Message | UID | Need | Priority |
|---------|-----|------|----------|
| Firmware V3 | 544 | Post-FUOTA firmware version confirmation | High — FUOTA verification |
| Boot V2 | 548 | Already implemented (`BootMsgV2`) | -- |
| Firmware Update Response V2 | 546 | Track individual chunk acknowledgments | Medium — progress diagnostics |
| Biometric Config | 558 | Configure biometric sensor parameters | Medium — biometric tests |
| Device Session | -- | Device connection/disconnection tracking | Low — nice to have |

### 4.5 REST Endpoint Discovery

The `CoreCloudRestInterface` provides a generic `request(method, path, ...)`
method that can call any C# REST endpoint. The following endpoints are known or
suspected to exist on the C# server but have no Python wrapper:

| Endpoint (suspected) | Method | Purpose | SDK Status |
|---------------------|--------|---------|------------|
| `/System/Devices/Register` | POST | Register new device | No wrapper |
| `/System/Devices/Status` | GET | Device connection status | No wrapper |
| `/System/Devices/Configurations/Gps` | POST/GET | GPS configuration | `GPSConfMsg` wraps this |
| `/System/Devices/Configurations/Ground` | POST/GET | Ground mode config | No wrapper |
| `/System/FUOTA/Plans` | ??? | FUOTA plan CRUD | Unknown if exists |
| `/System/FUOTA/Settings` | ??? | Per-device FUOTA settings | Unknown if exists |
| `/System/Devices/Firmware` | GET | Current firmware versions | No wrapper |

**Action required:** The C# server team needs to document available REST
endpoints, or we need to discover them through the C# source code / Swagger
documentation.

---

## 5. Access Strategy: DB ORM vs REST

### 5.1 Decision Matrix

| Operation | Recommended Access | Rationale |
|-----------|-------------------|-----------|
| **Read device messages** | DB ORM via `msg_def_v1_0` classes | Already implemented, type-safe, battle-tested |
| **Read FUOTA progress** | DB ORM via `Fuotaprogresstbl` | Already implemented, polling-friendly |
| **Read firmware versions** | DB ORM via `Devicefirmwarecurrenttbl` | Already implemented |
| **Create FUOTA plans** | DB ORM (fallback) | No REST endpoint known; validation env is isolated |
| **Set device FUOTA settings** | DB ORM (fallback) | No REST endpoint known; validation env is isolated |
| **Send GPS config** | REST via `GPSConfMsg.send_via_rest()` | Already implemented |
| **Send ground config** | REST (needs wrapper) | Follow `GPSConfMsg` pattern |
| **Register devices** | REST (needs wrapper) | C# endpoint exists |
| **Query device status** | REST (needs wrapper) | C# endpoint likely exists |

### 5.2 DB ORM Write Risks

Using DB ORM for writes (FUOTA plan creation, device enrollment) bypasses the
C# server's business logic:

| Risk | Impact | Mitigation |
|------|--------|------------|
| No server-side validation | Invalid plan structures could break the Singleton FUOTA evaluator | Validate locally before insert; test on isolated VAL_1_0 instance |
| No audit trail | Server normally logs plan changes to history tables | Manually insert history records, or accept no audit for validation |
| Race conditions | Server and validation pipeline could modify settings concurrently | VAL_1_0 is dedicated to automation; no concurrent human/server modifications expected |
| Schema drift | DB ORM may diverge from server expectations | Pin ORM to known-good schema version; re-validate after CoreCloud upgrades |

### 5.3 Migration Path

```
Phase 1 (now):    DB ORM for reads + writes
                  REST for GPS config (existing)
                  ↓
Phase 2 (short):  Discover C# REST endpoints for FUOTA
                  Add Python wrappers for known endpoints
                  ↓
Phase 3 (target): REST for all writes (plan CRUD, device enrollment)
                  DB ORM for reads only (messages, progress, versions)
```

---

## 6. Integration with Validation Pipeline

### 6.1 Architecture Diagram

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
│  │ MTIB V2       │    │ VAL_1_0          │                  │
│  │ Client        │    │ Interfaces       │                  │
│  │ (gRPC)        │    │ (REST + DB)      │                  │
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

### 6.2 Integration Points

| Integration | Protocol | SDK Module | Direction |
|------------|----------|-----------|-----------|
| Test Runner → MTIB | gRPC | `corekinect.mtib_client` | Command (power, UART, GPIO) |
| Test Runner → CoreCloud REST | HTTPS | `core_cloud.api_interface` | Config, device management |
| Test Runner → CoreCloud DB | PostgreSQL | `core_cloud.db_interface` | Message queries, FUOTA management |
| DUT → CoreCloud | TLS Socket | N/A (device firmware) | Uplink messages, FUOTA delivery |

### 6.3 Pytest Fixture Pattern

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

### 6.4 Message Verification Pattern

All Stage 4 tests verify device behavior by polling CoreCloud for messages after
physical actions (power-on, FUOTA, button press, sensor stimulus):

```python
def wait_for_message(msg_class, device_id, predicate, timeout_s=120,
                     poll_interval_s=5, db_env="VAL_1_0"):
    """Poll CoreCloud for a message matching a predicate."""
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

| Verification | Message Class | Predicate Focus | Typical Timeout |
|-------------|---------------|----------------|-----------------|
| Boot after power-on | `BootMsgV2` | `boot_reason == 0`, MCU type | 60s |
| Boot after FUOTA | `BootMsgV2` | `boot_reason == 2` | 120s |
| GPS fix | `PositionMsgV6` | `gnss_fix_ok`, `num_sat`, accuracy | 300s |
| Biometrics on-body | `BiometricDataMsg` | `on_body`, HR range, SpO2 range | 120s |
| Network uplink | `NetworkStatusMsgV4` | `did_lte_conn`, `send_success` | 120s |
| No HW failures | `AlphaHwFailureMsg` | No messages since test start | N/A (query) |
| Config confirmed | `GPSConfMsg` | `lastconfirmed is not None` | 120s |

---

## 7. FUOTA via DB ORM — Detailed Design

### 7.1 FUOTA Data Model

```
fuotaplanstbl (Plan)
  PK: planid (auto-increment)
  Fields: plandesc, devicetypeid, devicevariantid, timecreated, lastmodified
  │
  ├── fuotaplanstagestbl (Stages)
  │     PK: (planid, updatestage)
  │     Fields: stagedesc, skippable, timecreated, lastmodified
  │
  ├── fuotaplanstagetargetstbl (Stage Targets)
  │     PK: (planid, updatestage, appid)
  │     Fields: releasetrack, ismfg, majorversion, minorversion, revision, updateorder
  │
  ├── fuotasettingsperdevicetbl (Per-Device Settings)
  │     PK: deviceid
  │     FK: planid → fuotaplanstbl
  │     Fields: enablefuota, maxstage, timecreated
  │
  └── fuotasettingsperdevicetypetbl (Per-Type Defaults)
        PK: (devicetypeid, devicevariantid, accountid)
        Fields: planid, enablefuota, maxstage

fuotaprogresstbl (Active Transfers)
  PK: (deviceid, appid)
  Fields: majorversion, minorversion, revision, releasetrack, ismfg,
          pagesapplied, totalpages, timestarted, lastupdated

fuotaprogresshistorytbl (Completed Transfers)
  PK: recordid
  Indexed: deviceid
  Fields: (same as progress) + timefinished

devicefirmwarecurrenttbl (Current FW Versions)
  PK: (deviceid, appid)
  Fields: majorversion, minorversion, revision, releasetrack, ismfg, lastupdated
```

### 7.2 Plan Creation Example

```python
from datetime import datetime
from corekinect.core_cloud.db_interface import CoreCloudDBInterface
from corekinect.core_cloud.db_orm_v1_0 import (
    Fuotaplanstbl, Fuotaplanstagestbl, Fuotaplanstagetargetstbl,
    Fuotasettingsperdevicetbl,
)

ALPHA_DEVICE_TYPE_ID = 2
ALPHA_B0_VARIANT_ID = 3
APP_CORE_APP_ID = 109    # nRF52840
COMMS_CORE_APP_ID = 108  # nRF9151

with CoreCloudDBInterface(db_env="VAL_1_0") as db:
    now = datetime.utcnow()

    # 1. Create plan
    plan = Fuotaplanstbl(
        plandesc="Validation: Alpha B0 Mfg → Prod Debug",
        devicetypeid=ALPHA_DEVICE_TYPE_ID,
        devicevariantid=ALPHA_B0_VARIANT_ID,
        timecreated=now,
        lastmodified=now,
    )
    db.add(plan)
    db.flush()  # get planid

    # 2. Create stage
    stage = Fuotaplanstagestbl(
        planid=plan.planid,
        updatestage=1,
        stagedesc="Mfg → Prod Debug v2.1.0",
        timecreated=now,
        lastmodified=now,
        skippable=False,
    )
    db.add(stage)

    # 3. Add stage target (app core)
    target = Fuotaplanstagetargetstbl(
        planid=plan.planid,
        updatestage=1,
        appid=APP_CORE_APP_ID,
        releasetrack=2,  # Production
        ismfg=False,
        majorversion=2,
        minorversion=1,
        revision=0,
        updateorder=0,
    )
    db.add(target)

    # 4. Enroll device
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

### 7.3 Progress Monitoring

```python
def wait_for_fuota_completion(session, device_id, app_id, timeout_s=600):
    """Poll FUOTA progress until complete or timeout."""
    from corekinect.core_cloud.db_orm_v1_0 import Fuotaprogresstbl
    import time

    start = time.time()
    while time.time() - start < timeout_s:
        progress = session.query(Fuotaprogresstbl).filter(
            Fuotaprogresstbl.deviceid == device_id,
            Fuotaprogresstbl.appid == app_id,
        ).first()

        if progress and progress.pagesapplied == progress.totalpages:
            return True  # Transfer complete, device will reboot

        time.sleep(10)  # Poll every 10 seconds
    return False  # Timeout
```

### 7.4 FUOTA Rules and Constraints

| Rule | Description | Validation Impact |
|------|-------------|------------------|
| Version ordering | Firmware versions may only increase (major.minor.build) | Plans must target higher versions than currently installed |
| Mfg-to-prod exception | Manufacturing FW can be replaced by production FW of same or higher version | First FUOTA transition in the 12-step flow uses this exception |
| No release track switching | Bench, Engineering, Production are separate tracks | Validation plans must stay on one track |
| 5-minute cooldown | Server enforces 5-min wait between FUOTA completions | Pipeline must sleep between transitions; 12-step flow has ~30 min cooldown total |
| Dual-processor sync | Both App ID 108 (comms) and 109 (app) must reach stage target before advancing | Plans must include targets for both processors |
| `updateorder` | Controls which processor updates first within a stage | Must be set correctly for dual-MCU devices |

---

## 8. Open Questions

### 8.1 For the CoreCloud Backend Team

| # | Question | Impact | Priority |
|---|----------|--------|----------|
| 1 | What REST endpoints exist for FUOTA plan CRUD? | Determines whether we use DB ORM (fallback) or REST (preferred) for plan management | High |
| 2 | What REST endpoint exists for per-device FUOTA settings? | Same as above — affects how we enroll devices | High |
| 3 | How are `.cfw` firmware artifacts associated with FUOTA plan stage targets? | Pipeline must upload `.cfw` files and link them to plan targets | High |
| 4 | What is the `.cfw` upload mechanism? | REST endpoint, S3 bucket, manual upload? | High |
| 5 | Can the Singleton FUOTA evaluator be triggered on demand? | Determines latency between plan setup and FUOTA delivery start | Medium |
| 6 | What is the default device uplink interval? | Determines minimum wait time before FUOTA chunks start flowing | Medium |
| 7 | Can a device be forced to uplink immediately? | Could reduce pipeline execution time | Medium |
| 8 | What happens if FUOTA fails mid-transfer? | Need retry/reset behavior: automatic, manual, or stuck? | Medium |
| 9 | Does `POST /System/Devices/Register` exist? What fields does it require? | Needed for automated device setup in VAL_1_0 | Medium |
| 10 | What `devicetypeid` and `devicevariantid` values correspond to Alpha B0? | Needed for FUOTA plan creation (suspected: type=2, variant=3) | Medium |

### 8.2 For the Firmware Team

| # | Question | Impact | Priority |
|---|----------|--------|----------|
| 1 | What DUT firmware configuration points the device at the validation CoreCloud instance? | Socket server URL, time server URL, TLS certificates | High |
| 2 | Can the validation Socket Server URL be set via manufacturing shell or FUOTA, or is it baked into firmware? | Determines if we need a validation-specific firmware build or can reconfigure at runtime | High |
| 3 | Is there a way to force an uplink from the shell (manufacturing or debug firmware)? | Reduces FUOTA wait times during testing | Medium |

### 8.3 For the DevOps Team

| # | Question | Impact | Priority |
|---|----------|--------|----------|
| 1 | Is SSH tunneling required for DB access from K8s pods, or is direct PostgreSQL connectivity available? | Determines whether `VAL_1_0_SSH_*` env vars are needed | Medium |
| 2 | What service account credentials will the validation pipeline use? | Must be provisioned and stored as K8s secrets | Medium |
| 3 | Does the validation CoreCloud instance support concurrent device connections? | Affects parallel testing throughput | Low |

---

## 9. Implementation Priority

| Priority | Component | Effort | Dependency |
|----------|-----------|--------|------------|
| **P0** | `fuota.py` — FUOTA plan builder + monitor | 16-24h | Answer to Q1-4 in Section 8.1 (can start with DB ORM fallback) |
| **P0** | Extend `GroundModeConfigV2` with REST send | 4-8h | C# endpoint path for ground config |
| **P1** | `device_management.py` — register + status wrappers | 8-12h | Answer to Q9 in Section 8.1 |
| **P1** | `ValidationSession` context manager | 4-8h | None |
| **P1** | New message type: `FirmwareV3Msg` (UID 544) | 4-8h | ORM table mapping |
| **P2** | Migrate FUOTA writes from DB ORM to REST | 8-16h | C# REST endpoints documented |
| **P2** | `__init__.py` typed re-exports | 2h | None |
| **P3** | Deprecation markers on v0.9 modules | 1h | None |

---

## 10. References

| Resource | Path |
|----------|------|
| CoreCloud SDK (source) | `libs/python/corekinect/core_cloud/` |
| v1.0 ORM Models | `libs/python/corekinect/core_cloud/db_orm_v1_0.py` |
| v1.0 Message Definitions | `libs/python/corekinect/core_cloud/msg_def_v1_0.py` |
| REST API Interface | `libs/python/corekinect/core_cloud/api_interface.py` |
| DB Connection Interface | `libs/python/corekinect/core_cloud/db_interface.py` |
| SDK README | `libs/python/corekinect/core_cloud/READ_ME.md` |
| Environment Template | `libs/python/corekinect/core_cloud/.env.example` |
| FUOTA Research | `docs/validation/research/06-fuota-corecloud-v1.md` |
| CoreCloud Integration Research | `docs/validation/research/09-corecloud-validation-integration.md` |
| Stage 4 FUOTA Flow | `docs/validation/architecture/stage4-fuota-validation-flow.md` |
| Stage 4 Product Tests | `docs/validation/architecture/stage4-product-tests.md` |
| Stage 3 & 4 Overview | `docs/validation/plans/stage3-and-4/overview.md` |
