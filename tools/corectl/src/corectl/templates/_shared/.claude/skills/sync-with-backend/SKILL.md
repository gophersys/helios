---
name: sync-with-backend
description: Reconcile this app's manifest with the backend's authoritative product / board / fixture info
user-invocable: true
---
<!-- generated-by: corectl/corekinect {{framework_version}} — do not hand-edit; run `corectl test update` to refresh -->

# Sync with the backend

The backend owns: product slug, board revision name, device IDs, fixture controller class path. Anything else in `concord.yaml` is dev-owned. This skill pulls authoritative fields from the backend and shows the diff.

## When to invoke

- After a `validate`/`run`/`upload` warning surfaces "manifest drifted from backend".
- After a known backend change (admin renamed a board, bumped device IDs, swapped fixture).
- Periodically — once a week is healthy hygiene for an active app.

## Steps

1. **Run `corectl test sync`** (no `--apply`). It prints the per-field diff: `path: current → desired`.

2. **Review every line.** Each diff is the backend telling you "the platform's source-of-truth has moved."
   - **`product.slug`** — should never change without a product rename. If you see this, ask the user before applying.
   - **`product.board`** — the board's `ckBoardsName` was changed in the platform. Apply.
   - **`product.device.{type_id,variant_id}`** — CoreCloud device identity. Apply.
   - **`fixture.module`** — class path moved. Apply only if the dotted module exists at that path on disk; otherwise the test app is broken and needs the fixture file moved/renamed first.

3. **If the diff looks safe**, run `corectl test sync --apply` to write the changes back to `concord.yaml`.

4. **Re-run `corectl test validate`.** Sync only changes manifest fields; tests/fixtures may need updates downstream (e.g., if `fixture.module` moved, you also moved the file). Confirm everything still validates.

5. **Commit the sync.** `git add concord.yaml && git commit -m "chore: sync manifest with backend"`. Push.

## What you may NOT do

- Do not auto-apply without reviewing the diff. Sync is one-way (backend → local) and silent application can mask a misconfigured backend.
- Do not edit `concord.yaml` to "fix" a sync warning. Either accept the backend's view or fix the backend's data — never desync further.
