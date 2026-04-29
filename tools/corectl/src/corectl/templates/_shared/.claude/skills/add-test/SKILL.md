---
name: add-test
description: Add a new test_*.py file to an existing stage with the right shape (timeout, slot/report, step structure)
user-invocable: true
argument-hint: "<stage_name> <test_name>"
---
<!-- generated-by: corectl/corekinect {{framework_version}} — do not hand-edit; run `corectl test update` to refresh -->

# Add a new test

Create a properly-shaped test file inside an existing stage.

Arguments: $ARGUMENTS — first is the stage name, second is the test name (without `test_` prefix or `.py` suffix).

## Steps

1. **Verify the stage exists.** `tests/<stage>/` must be a directory referenced by `concord.yaml stages:`. If not, run `/add-stage` first.

2. **Check for naming conflict.** `tests/<stage>/test_<test_name>.py` must not already exist.

3. **Decide the test purpose.** Ask: what behavior does this test prove? Write that as the docstring's first sentence. The reporter renders it as the test card title.

4. **Pick a timeout.** Default 60s. Add 30-60s if the test waits on hardware (boot, flash, modem registration). Cap at 600s for any single test — break larger work into separate tests.

5. **Write the file** at `tests/<stage>/test_<test_name>.py`:

   ```python
   """<one-sentence purpose, will be the test card title>."""

   import pytest
   from corekinect.test.assertions import assert_and_record


   @pytest.mark.<stage_name>
   @pytest.mark.timeout(<chosen_timeout_s>)
   def test_<test_name>(slot, report):
       """<longer docstring with context, optional>."""
       with report.step("<step description>") as step:
           # >>> INSERT YOUR CODE HERE
           # Use slot.fixture, slot.adc, slot.uart, slot.jlink, slot.power.
           # Record measurements with assert_and_record(step, key, value, unit, predicate).
           assert_and_record(step, "<measurement_key>", <value>, "<unit>",
                             lambda v: <predicate>)
   ```

6. **Open ONE step at a time.** If the test needs multiple steps, exit one `with report.step(...)` block before opening the next:

   ```python
   def test_thing(slot, report):
       with report.step("a") as step:
           ...
       with report.step("b") as step:
           ...
   ```

7. **Helpers do not open steps.** If you extract logic into a helper, the helper takes work as args and returns values — not the reporter or a step.

8. **Run `corectl test validate`.** The test-depth checker confirms the two-level contract; the contracts checker confirms the timeout marker is present.

## Common patterns

- **Reading an ADC:** `slot.adc.read("<key>")` — returns a float in volts.
- **Toggling a GPIO:** `slot.fixture.gpios["<key>"].config(direction="output").set_low()`.
- **UART exchange:** `slot.uart.send("<key>", b"command\n")`; `slot.uart.expect("<key>", b"OK", timeout_s=2)`.
- **J-Link flash:** `slot.jlink.flash("<key>", path_to_hex)` — the SDK handles signing and AP-protect.
- **Power cycle:** `slot.fixture.power_off(); time.sleep(0.5); slot.fixture.power_on()`.
