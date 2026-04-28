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
[ ] concord.yaml package.version is the new semver
[ ] corectl test validate --strict passed
[ ] git working tree is clean (committed) — release SHA must match what shipped
[ ] corectl test upload --release returned 2xx
[ ] Released version visible in `corectl test versions`
[ ] (Optional) ProductStageConfig bindings updated in the platform UI
```

## Steps

1. **Resolve the new version.** Read `concord.yaml package.version`. If the argument is a bump kind, increment accordingly (e.g., current `1.2.3` + `minor` → `1.3.0`). If it's an explicit version, validate it parses as semver and is strictly greater than current.

2. **Edit `concord.yaml`.** Update `package.version` to the new version. Do not commit yet.

3. **Validate strictly.** Run `corectl test validate --strict`. ANY warning fails the release. Fix or justify, then re-run. Do not proceed past this gate with red.

4. **Commit the version bump.** `git add concord.yaml && git commit -m "chore: release v<new_version>"`. Push to your branch.

5. **Verify clean tree.** `git status --porcelain` returns empty.

6. **Upload + release in one step.** `corectl test upload --release`. Provide a short release message (the changelog line). The command:
   - Re-validates server-side.
   - Creates the DEVELOPMENT row.
   - Promotes immediately to RELEASED, stripping the `dev-` prefix.
   - Returns the released version string.

7. **Confirm.** Run `corectl test versions`. The new version should appear with status RELEASED.

8. **Surface the binding step.** Released packages do not auto-bind to ProductStageConfig. Tell the user to either:
   - Bind via the Concord UI (Product → Stages → Set released package), or
   - Use the platform admin's release flow (separate from this app's release).

## Failure modes

- **Validate fails strict** → fix warnings, do not loosen `--strict`.
- **Version conflict** → another release just landed; rebase, bump again.
- **Upload rejects with "missing artifacts"** → run `/sync-with-backend` then `corectl test update`. The framework artifacts must be present.
- **Backend mismatch** → `corectl test sync` reconciles; re-run from step 3.
