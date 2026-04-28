---
name: validate
description: Run `corectl test validate` and walk through any errors with concrete fixes
user-invocable: true
---
<!-- generated-by: corectl/corekinect {{framework_version}} — do not hand-edit; run `corectl test update` to refresh -->

# Validate this test app

Run pre-flight validation and surface every issue with an actionable fix.

## When to invoke

- Before every commit.
- After editing `concord.yaml`, `fixtures/{{board}}/fixture.py`, or any test file.
- After `corectl test sync` (drift may have introduced inconsistencies).

## Steps

1. Run `corectl test validate` from the repo root.
2. For each ✗ error or ⚠ warning, identify the source file (the line is in the message) and the contract that was violated.
3. Map the message to the right rule in `.claude/rules/`:
   - "Test depth" / "two-level step contract" → `rules/reporter-conventions.md`.
   - "fixture validation" → `rules/fixture-conventions.md`.
   - "Schema:" → `concord.yaml` field shape; cross-check against `rules/test-conventions.md`.
   - "manifest drifted from backend" → `corectl test sync`.
   - "Framework artifacts" → `corectl test update`.
4. Apply the smallest change that fixes the issue. Don't restructure.
5. Re-run `corectl test validate`. Repeat until green.

## What you may NOT do

- Do not edit anything under `.claude/` or `.devcontainer/`. Validation will fail and the platform will reject uploads.
- Do not add new fields to `concord.yaml` outside the schema. Run `corectl --version` to confirm you're on the framework version this app was scaffolded with (`.claude/.framework-version`); upgrade if not.
