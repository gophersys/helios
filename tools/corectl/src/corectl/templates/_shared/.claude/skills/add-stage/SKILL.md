---
name: add-stage
description: Add a new stage to this test app — updates concord.yaml, scaffolds tests/<stage>/, registers the marker
user-invocable: true
argument-hint: "<stage_name> [timeout_s]"
---
<!-- generated-by: corectl/corekinect {{framework_version}} — do not hand-edit; run `corectl test update` to refresh -->

# Add a new stage

A stage is one test phase, scoped to a directory under `tests/`. Adding one touches three places.

Arguments: $ARGUMENTS — first arg is the stage name (lowercase snake_case), second optional arg is `timeout_s` (default 600).

## Steps

1. **Validate stage name.** Lowercase, snake_case, matches `^[a-z][a-z0-9_-]*$`. Reject if it conflicts with an existing stage in `concord.yaml`.

2. **Update `concord.yaml`.** Add a new entry under `stages:` with `directory: tests/<stage>` and `timeout_s: <provided or 600>`. Preserve existing stage order; add new stages at the end. For validation packages add `hardware: [mtib]` if other validation stages have it. For manufacturing, add `module: <module_name>` if the existing manufacturing stages use the per-stage-module pattern.

3. **Create the test directory.** `mkdir -p tests/<stage>`. Add an `__init__.py` and a `conftest.py` (one-line: `"""<Stage> stage fixtures."""`).

4. **Add a placeholder test.** `tests/<stage>/test_placeholder.py`:

   ```python
   """{{stage}} — replace this with the real first test for this stage."""

   import pytest
   from corekinect.test.assertions import assert_and_record


   @pytest.mark.<stage_name>
   @pytest.mark.timeout(<timeout_s>)
   def test_placeholder(slot, report):
       with report.step("placeholder") as step:
           assert_and_record(step, "scaffold", 1.0, "bool", lambda v: v == 1.0)
   ```

5. **Register the marker.** Append to `pyproject.toml` `[tool.pytest.ini_options].markers`:

   ```
   "<stage_name>: <one-line description of what tests in this stage prove>",
   ```

6. **Run `corectl test validate`.** Confirm the new stage shows up as `✓ tests/<stage>/ (1 test files)` and pytest collection succeeds.

## What you may NOT do

- Do not skip `corectl test validate` after adding the stage. The stage directory must exist and the marker must be registered, otherwise the platform rejects the upload.
- Do not add `hardware:` values that aren't real hardware identifiers. Stick to `mtib`, `fixture` (or whatever the framework version supports).
