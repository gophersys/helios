# CoreCloud Interface Library

A thin, stable Python API for interacting with CoreCloud in automated validation and test workflows.
It wraps device messages and selected tables into strongly-typed “message” classes so your test logic stays
decoupled from backend details.

## Versioned APIs
### CoreCloud v1.0

Use `msg_def_v1_0` for current systems. Each message type exposes classmethods for common queries
(e.g., latest record, ranges by time or record ID).

Example – fetch last Position message and print key fields

```python
from corekinect.core_cloud.msg_def_v1_0 import PositionMsgV6

last_pos = PositionMsgV6.last(0x70B3D584C02002FE, env="DEV_1_0")
print(
    f"lat,lon: {last_pos.latitude},{last_pos.longitude}; "
    f"Alt: pressure={last_pos.pressure_altitude_feet} ft, gps={last_pos.gps_altitude_feet} ft"
)
```

Example – send a GPS configuration via REST

```python
from corekinect.core_cloud.msg_def_v1_0 import GPSConfMsg

cfg = GPSConfMsg(
    is_psm_enabled=False,
    is_aiding_enabled=False,
    gnss_update_freq=0,
    target_fix_accuracy=10,
    target_fix_pdop=30,
)
resp = cfg.send(device_id=0x70B3D584C020038F, env_namespace="VAL_1_0", raise_for_status=True)

```

### CoreCloud v0.9 (legacy)

`msg_def_v0_9` mirrors the v1.0 surface so test code can remain the same. Internally, the library performs the extra
mapping required to align legacy schemas with the v1.0 conventions.


## What you import (typical)

Most users only need the message wrappers:
- `corekinect.core_cloud.msg_def_v1_0` (current)
- `corekinect.core_cloud.msg_def_v0_9` (legacy)

Advanced helpers (DB/REST interfaces, utilities) are available if you have special cases, but aren’t required for common test flows.

## Configuration (.env)

Copy `.env.example` to `.env` and fill in your credentials and endpoints (user names, passwords, URIs, ports).
These values are read at runtime by the DB and REST clients.
