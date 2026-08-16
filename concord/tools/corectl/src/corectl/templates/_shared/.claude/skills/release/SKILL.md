---
name: release
description: Release this test app — bump version, validate, upload, promote to RELEASED, confirm binding
user-invocable: true
argument-hint: "[major|minor|patch] or explicit semver"
---
<!-- generated-by: corectl/corekinect {{framework_version}} — do not hand-edit; run `corectl test update` to refresh -->

# Release a versioned package

Promote this app from "ready to ship" to a permanent semver release. Released versions are immutable and the platform binds them as the active package for any RELEASE-purpose fixture.

Arguments: $ARGUMENTS — bump kind (`major` / `minor` / `patch`) OR an explicit version like `1.2.0`.

## Definition of done

```
[ ] git working tree is clean (committed) — release SHA must match what shipped
[ ] corectl test validate --strict passed
[ ] corectl test upload --release returned 2xx
[ ] Released version visible in `corectl test versions`
[ ] (Optional) ProductStageConfig bindings updated in the platform UI
```

## Steps

1. **Validate strictly.** Run `corectl test validate --strict`. ANY warning fails the release. Fix or justify, then re-run. Do not proceed past this gate with red.

2. **Verify clean tree.** `git status --porcelain` returns empty. Anything uncommitted means the released SHA won't match what's on disk — fix it first.

3. **Upload + release in one step.** `corectl test upload --release`. Provide a short release message (the changelog line). The command:
   - Re-validates server-side.
   - Creates the immutable upload row.
   - **Auto-assigns the released semver** based on the current released stream (the operator does NOT pre-edit `concord.yaml package.version`; the `version` field there is informational for dev iterations).
   - Promotes to RELEASED, stripping the `dev-` prefix.
   - Returns the released version string.

4. **Confirm.** Run `corectl test versions`. The new version should appear with status RELEASED.

5. **Surface the binding step.** Released packages do not auto-bind to ProductStageConfig. Tell the user to either:
   - Bind via the Concord UI (Product → Stages → Set released package), or
   - Use the platform admin's release flow (separate from this app's release).

## Failure modes

- **Validate fails strict** → fix warnings, do not loosen `--strict`.
- **Version conflict** → another release just landed; rebase and re-run.
- **Upload rejects with "missing artifacts"** → run `/sync-with-backend` then `corectl test update --apply`. The framework artifacts must be present and current.
- **Backend mismatch** → `corectl test sync` reconciles; re-run from step 1.
