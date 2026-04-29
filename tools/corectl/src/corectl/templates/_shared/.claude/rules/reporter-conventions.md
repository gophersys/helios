<!-- generated-by: corectl/corekinect {{framework_version}} — do not hand-edit; run `corectl test update` to refresh -->

# Reporter Conventions

The reporter streams test/step events to the platform UI in real time. How to use it correctly.

## The contract

```python
def test_voltage_rails(slot, report):
    with report.step("Power on") as step:
        slot.fixture.power_on()
        assert_and_record(step, "boot_current_ma", slot.fixture.read_total_current_ma(),
                          "mA", lambda v: v > 5.0)

    with report.step("Read 3V3 rail") as step:
        v = slot.adc.read("rail_3v3")
        assert_and_record(step, "rail_3v3_v", v, "V", lambda v: 3.2 <= v <= 3.4)
```

Each `with report.step(...)` block becomes a row in the UI under the test card. `assert_and_record` calls become measurement rows under the step.

## What you get from each fixture

- **`report`** — pytest fixture. The reporter for the current test. Use `report.step("...")` to open a new step.
- **`step`** — yielded by `report.step(...)`. Use `assert_and_record(step, ...)` to record measurements scoped to this step.

## Step descriptions

A single string argument. Static literals work best — they get AST-extracted at upload time so the platform renders the full test/step tree BEFORE the run starts. Operators see the panel layout with all expected steps and measurements.

f-strings and computed descriptions still work, but the platform falls back to runtime-only rendering for those steps (the tree is partially built when the run begins; step rows appear as events arrive).

## What `assert_and_record` does

```python
assert_and_record(step, key, value, unit, predicate)
```

- Asserts `predicate(value)` is true (failed → test fails, step marked red).
- Records `(key, value, unit, pass)` to the reporter.
- The platform persists this for the run, surfaces it in the UI under the step.

Prefer `assert_and_record` over plain `assert` everywhere — bare asserts give the operator no measurement context when a test fails.

## Don't open steps in helpers

Helper functions never call `report.step(...)`. The two-level depth contract (one step deep per test) is enforced by `corectl test validate`. Helpers do work; the test wraps the helper in a step.

## Step.fail() for soft failures

Sometimes a step has multiple checks and you want all of them to record before failing the test:

```python
with report.step("Read all rails") as step:
    for rail in ("rail_3v3", "battery_sys", "vbackup"):
        v = slot.adc.read(rail)
        if not (3.2 <= v <= 3.4):
            step.fail(f"{rail} out of spec: {v}")
        else:
            step.record(rail, v, "V", passed=True)
```

`step.fail(msg)` marks the step failed but continues execution. The test fails at the end of the `with` block.
