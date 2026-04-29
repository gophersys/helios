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

## Reading data — `assert_and_record`

Use `assert_and_record(step, key, value, unit, predicate)` instead of plain `assert`. The reporter persists `(key, value, unit, pass/fail)` per step so the UI can render measurements alongside pass/fail status.
