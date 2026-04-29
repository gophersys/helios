<!-- generated-by: corectl/corekinect {{framework_version}} — do not hand-edit; run `corectl test update` to refresh -->

# Test Conventions

How to write a test in this repo. Enforced by `corectl test validate`.

## Shape of a test

```python
import pytest
from corekinect.test.assertions import assert_and_record


@pytest.mark.smoke
@pytest.mark.timeout(120)
def test_some_behavior(slot, report):
    """One-sentence purpose. The reporter renders this as the test card title."""
    with report.step("Apply 4.5 V to VBAT") as step:
        slot.fixture.power_on()
        assert_and_record(step, "vbat_v", slot.adc.read("battery_sys"), "V",
                          lambda v: 4.4 <= v <= 4.6)
```

## Required pieces

- **`@pytest.mark.timeout(N)`** — every test. The slot-parallel runner cannot enforce timeouts otherwise.
- **`slot` fixture** — declares which DUT slot the test runs against. Auto-injected by `corekinect.test.autoconf` for both validation (single slot) and manufacturing (N slots).
- **`report` fixture** — the reporter that streams events to the platform UI.
- **One stage marker** — `@pytest.mark.<stage_name>` matching the directory the test lives in (e.g., `@pytest.mark.smoke` for `tests/smoke/`). Lets operators filter `pytest -m smoke`.

## Two-level depth contract

Tests open at most one `with report.step(...)` at a time. Helper functions never open their own step. Violating this corrupts the step index in slot-parallel mode and mis-renders the UI tree.

```python
# OK
def test_foo(slot, report):
    with report.step("step a") as step:
        helper_that_does_not_open_a_step()

# NOT OK — helper opens a nested step
def test_foo(slot, report):
    with report.step("outer") as step:
        helper_that_opens_a_step(report)  # <-- breaks the contract
```

The `corectl test validate` test-depth checker (`test_depth.py`) catches this at upload time.

## Step descriptions

`with report.step("...")` takes a single string. Use static literals — they are extracted at upload time so the platform UI can render the test tree before the test runs. Dynamic descriptions (f-strings, variable refs) are accepted today but lose the static-tree rendering.

## Markers register, then decorate

Stage markers live in `pytest.ini` under `markers = [...]`. Add new markers there before using them on a test, otherwise pytest emits "PytestUnknownMarkWarning". The autoconf plugin also auto-registers any marker referenced by a stage in `concord.yaml stages.<stage>.markers`, so manifest-declared markers don't need a duplicate `pytest.ini` entry.

## Validation layout: one directory per stage

Validation apps ship each stage as its own directory under `tests/`:

```
tests/
├── smoke/
│   ├── conftest.py
│   └── test_*.py
├── driver/
└── ...
```

Each validation stage's `concord.yaml` entry points at its own directory:

```yaml
stages:
  smoke:
    directory: tests/smoke
    timeout_s: 300
```

## Manufacturing layout: one shared `tests/manufacturing/` dir, one file per step

Manufacturing apps run as a SINGLE physical stage on the platform (`stage=manufacturing`). The runner hardcodes the test directory to `tests/manufacturing/` based on the stage name — that path is not configurable.

What varies between manufacturing apps is the *steps* inside that directory. Each step is one `test_NN_<step>.py` file with multiple `test_*` functions that execute in alphabetical order:

```
tests/
└── manufacturing/
    ├── __init__.py
    ├── conftest.py            # optional, scoped to manufacturing tests
    ├── test_01_electrical.py  # rail checks, UVP, charger
    ├── test_02_fw_flash.py    # flash app + comms processors via J-Link
    └── test_03_post.py        # chip IDs, sensors, BLE, personalize, AP-protect
```

Each test function inside a step file carries the matching marker and timeout:

```python
@pytest.mark.electrical
@pytest.mark.timeout(30)
def test_01_uvlo(slot, report):
    ...

@pytest.mark.electrical
@pytest.mark.timeout(30)
def test_02_nominal(slot, report):
    ...
```

The `concord.yaml` `stages` block is logical — every manufacturing stage entry points at the same physical directory but uses `module:` to identify the step file the platform tracks for UI grouping and per-step timeouts:

```yaml
stages:
  electrical:
    directory: tests/manufacturing
    module: test_01_electrical
    timeout_s: 120
    hardware: [mtib, fixture]
  fw_flash:
    directory: tests/manufacturing
    module: test_02_fw_flash
    timeout_s: 300
    hardware: [mtib, fixture, jlink]
  post:
    directory: tests/manufacturing
    module: test_03_post
    timeout_s: 900
    hardware: [mtib, fixture, jlink]
```

Do NOT split manufacturing into per-step directories (`tests/electrical/`, `tests/fw_flash/`, etc). The runner won't find them — it ignores per-step `directory:` overrides for manufacturing and always runs `tests/manufacturing/`.

## Reading data — `assert_and_record`

Use `assert_and_record(step, key, value, unit, predicate)` instead of plain `assert`. The reporter persists `(key, value, unit, pass/fail)` per step so the UI can render measurements alongside pass/fail status.
