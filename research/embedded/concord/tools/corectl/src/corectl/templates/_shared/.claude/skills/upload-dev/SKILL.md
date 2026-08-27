---
name: upload-dev
description: Upload this test app as a development version — auto-versioned, immediately available on DEV-purpose fixtures
user-invocable: true
---
<!-- generated-by: corectl/corekinect {{framework_version}} — do not hand-edit; run `corectl test update` to refresh -->

# Upload a development version

Push the current state of this app to the platform as an immutable development version.

## When to invoke

- After local validation passes and you want to test on a real fixture.
- For iterating quickly — every upload writes a fresh `dev-<sha>-<epoch>` version, no version-bump dance.

## Steps

1. **Pre-flight:** run `corectl test validate --strict`. Refuse to upload if validate fails.

2. **Check git is clean** (or close to it). Run `git status`. If there are uncommitted changes, ask the user whether to upload anyway — uncommitted state means the version's git SHA doesn't reflect what's actually packaged. Default to yes (dev versions are throwaway), but surface the warning.

3. **Run `corectl test upload`.** It will:
   - Re-validate (server-side enforcement).
   - Tag the package as `dev-<8-char-sha>-<epoch_seconds>` automatically.
   - Prompt for an upload message — keep it short, one phrase explaining what changed.
   - POST the tarball to the backend, which extracts stage metadata and creates DB rows.

4. **Confirm landing.** The command prints `Uploaded: <slug>@<version>` with the package ID. Copy the version string for any downstream use (running a session against this dev version).

## What gets sent

- The full repo content, minus: `__pycache__`, `.pytest_cache`, `.mypy_cache`, `logs/`, `dist/`, `.git/`, `.env`, `node_modules`, IDE caches.
- The `.claude/` and `.devcontainer/` framework artifacts MUST be present (backend rejects packages missing them).

## What you may NOT do

- Do not edit the version string by hand. Dev versions must be unique per upload — corectl handles the suffix.
- Do not run `corectl test upload --release` for a routine dev push. Use `/release` (the dedicated skill) for promotions.
