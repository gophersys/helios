# Prisma enums — knowledge

Every enum defined in `prisma/schema.prisma`, where it's used, and what its
values mean. Reference this when adding a new state, debugging a value
mismatch, or wiring the frontend `models.ts` after a schema change.

Refresh this file when: an enum value is added/removed/renamed; a new enum
is introduced; an enum's casing convention changes (SHOUTY_CAPS vs
lowercase).

## Coordination checklist for any enum change

A new enum value lives in **three** places that must stay in lockstep:

1. **`prisma/schema.prisma`** — declare the value.
2. **Backend Python code** — import via `from database import enums` and
   reference `enums.<Name>.<VALUE>`. Never use raw strings.
3. **Frontend `apps/frontend/app/src/lib/types/models.ts`** — add the
   string literal (matching the schema's exact casing) to the union
   type. No code-gen does this — it's a discipline.

The pre-commit knowledge-freshness hook catches `prisma/schema.prisma`
edits and forces an update here. It does **not** catch missing frontend
updates — review `models.ts` by hand.

## Casing rules

- **SHOUTY_CAPS** — default. Operational states, types, lifecycle stages.
- **lowercase** — used for a handful of enums declared early in the
  schema's history: `FirmwareVariant`, `ReleaseTrack`,
  `FirmwareSetStatus`, `RecipeStatus`, `AccessLevel`. Frontend must use
  exact-case literals — they are case-sensitive at the wire.

## Master enum table

### Hardware & nodes

| Enum | Values | Used on | Notes |
|---|---|---|---|
| `NodeType` | `MANUFACTURING`, `VALIDATION` | `Node.type`, `Fixture.type`, `TestBedDesign.type` | The fundamental hardware-purpose discriminator. |
| `FixturePurpose` | `DEV`, `RELEASE` | `Fixture.purpose` | DEV rigs accept only DEVELOPMENT TestPackages; RELEASE fixtures accept only RELEASED. |

### Lifecycle

| Enum | Values | Used on | Notes |
|---|---|---|---|
| `LifecycleStatus` | `DRAFT`, `ACTIVE`, `DEPRECATED`, `EOL` | `BoardRevision.status` | Generic hardware lifecycle. |
| `ProductStatus` | `ACTIVE`, `ARCHIVED` | `Product.status` | Only two states today; archived products hide from default list views. |
| `FirmwareSetStatus` (lowercase) | `active`, `deprecated`, `recalled` | `FirmwareSet.status` | Independent of `LifecycleStatus` — firmware can be recalled without affecting the parent product. |
| `RecipeStatus` (lowercase) | `draft`, `published` | `RecipeVersion.status` | Only published recipes are used by builds; draft is editor scratch space. |

### Validation & manufacturing

| Enum | Values | Used on | Notes |
|---|---|---|---|
| `StageType` | `VALIDATION`, `MANUFACTURING` | `ProductStageConfig.type`, `AssetSet.stageType` | Disambiguates the `stage` integer (both V and M use 1-N independently). |
| `TestRunType` | `VALIDATION`, `MANUFACTURING` | `TestRun.type` | Parent-shape discriminator (BuildRun parent vs ManufacturingSession parent). |
| `TestRunStatus` | `PENDING`, `ACTIVE`, `COMPLETED`, `FAILED`, `CANCELLED` | `TestRun.status` | Run-level aggregate. |
| `TargetStatus` | `PENDING`, `RUNNING`, `PASSED`, `FAILED`, `ERROR` | `RunTarget.status` | Per-DUT pass/fail. ERROR ≠ FAILED — ERROR means infrastructure (MTIB lost, runner crash), FAILED means the DUT failed a test. |
| `ExecutionStatus` | `PENDING`, `RUNNING`, `PASSED`, `FAILED`, `SKIPPED`, `ERROR` | `TestExecution.status`, `TestStep.status` | Adds SKIPPED relative to TargetStatus (pytest's `@skipif`). |
| `ManufacturingSessionStatus` | `ACTIVE`, `COMPLETED`, `CANCELLED`, `ARCHIVED` | `ManufacturingSession.status` | ARCHIVED is for post-COMPLETED archival; live sessions hold a fixture's IN_USE lock state derivation. |
| `TestPackageStatus` | `UPLOADING`, `DEVELOPMENT`, `RELEASED` | `TestPackage.status`, `TestBedDesign.status` (denormalized mirror of owner) | UPLOADING is the two-phase commit placeholder before the MinIO PUT completes. |
| `TestPackageType` | `VALIDATION`, `MANUFACTURING` | `TestPackage.type` | Selects which runner consumes the package. |

### Builds & artifacts

| Enum | Values | Used on | Notes |
|---|---|---|---|
| `BuildRunStatus` | `PENDING`, `BUILDING`, `BUILD_FAILED`, `VALIDATING`, `SUCCESS`, `FAILED`, `CANCELLED` | `BuildRun.status` | Distinct BUILD_FAILED (a child build failed) vs FAILED (validation failed). |
| `BuildJobStatus` | `QUEUED`, `BLOCKED`, `CLONING`, `BUILDING`, `SUCCESS`, `FAILED`, `CANCELLED`, `CACHED` | `BuildJob.status` | BLOCKED = waiting on a base build (version-bump chain). CACHED = reused via `reusedFromId`. |
| `AssetSetSource` | `BUILD_SERVICE`, `MANUAL_UPLOAD`, `EXTERNAL_CI` | `AssetSet.source` | How the assets entered the system. |
| `AssetSetStatus` | `PENDING`, `COMPLETE`, `VALIDATED`, `FAILED` | `AssetSet.status` | VALIDATED = a validation run has signed off this asset set. |
| `QueueEntryStatus` | `QUEUED`, `ASSIGNED`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED` | `ValidationQueueEntry.status` | Validation queue lifecycle. |
| `FirmwareVariant` (lowercase) | `smoke`, `debug`, `release`, `mfg` | `FirmwareSet.variant` | Compiler/optimization profile. |
| `ReleaseTrack` (lowercase) | `bench`, `engineering`, `production` | `FirmwareSet.releaseTrack` | Promotion lane. |

### Users & access

| Enum | Values | Used on | Notes |
|---|---|---|---|
| `Role` | `ADMIN`, `MAINTAINER`, `DEVELOPER`, `OPERATOR` | `User.role` | Organizational role. ADMIN/MAINTAINER bypass `ProductAccess` checks. |
| `AccessLevel` (lowercase) | `view`, `operate`, `develop`, `admin` | `ProductAccess.level` | Per-product granular access. |
| `AuthSessionStatus` | `PENDING`, `APPROVED`, `EXPIRED`, `DENIED` | `AuthSession.status` | RFC 8628 device-code flow for CLI logins. |

### Edge devices (ICLE)

| Enum | Values | Used on | Notes |
|---|---|---|---|
| `IcleDeviceStatus` | `ONLINE`, `OFFLINE`, `LOGGING`, `CONFIG`, `BOOT`, `OTA` | `IcleDevice.status` | ESP32 power-monitor lifecycle state. |

### Releases, errors, notifications

| Enum | Values | Used on | Notes |
|---|---|---|---|
| `ReleaseStatus` | `DRAFT`, `STAGED`, `RELEASED`, `ROLLED_BACK` | `Release.status` | Platform release lifecycle. |
| `ErrorReportStatus` | `OPEN`, `ACKNOWLEDGED`, `RESOLVED`, `DISMISSED` | `ErrorReport.status` | Admin triage state. RESOLVED can link to a `Release.id` via `resolvedInReleaseId`. |
| `NotificationType` | (see below) | `Notification.type`, `NotificationPreference.type` | Grouped by domain. New types require frontend display logic. |

#### NotificationType value list

```
PLATFORM_RELEASE_PUBLISHED        — Platform release went live
PLATFORM_DEPLOYMENT_COMPLETE      — Helm deployment succeeded
PLATFORM_DEPLOYMENT_FAILED        — Helm deployment failed

VALIDATION_RUN_COMPLETE           — Validation run finished (any outcome)
VALIDATION_RUN_FAILED             — Validation run failed

MANUFACTURING_SESSION_COMPLETE    — Mfg session ended cleanly
MANUFACTURING_SESSION_FAILED      — Mfg session errored

BUILD_COMPLETE                    — Firmware build succeeded
BUILD_FAILED                      — Firmware build failed

BUG_ACKNOWLEDGED                  — ErrorReport moved to ACKNOWLEDGED
BUG_RESOLVED                      — ErrorReport moved to RESOLVED
BUG_DISMISSED                     — ErrorReport moved to DISMISSED

SYSTEM_ANNOUNCEMENT               — Admin announcement to all users
SYSTEM_MAINTENANCE                — Scheduled maintenance notice

RELEASE_PUBLISHED                 — Legacy alias; do not use in new code
```

## Status pairs that look similar but differ

- **`TestRunStatus`** has `ACTIVE`; **`ManufacturingSessionStatus`** also has `ACTIVE`. Both mean "running now," but they live on different parents. Don't reuse handler code blindly.
- **`TargetStatus`** has 5 values; **`ExecutionStatus`** adds `SKIPPED`. A skipped pytest function is `ExecutionStatus.SKIPPED` and contributes to its target's `passedCount` as "neither pass nor fail."
- **`BuildRunStatus`** has both `BUILD_FAILED` and `FAILED`. The former means a child compilation failed; the latter means a subsequent validation step failed. Both surface as red in the UI but tell different stories.
- **`ErrorReportStatus.RESOLVED`** vs **`ReleaseStatus.RELEASED`** — close in spelling, opposite meaning. RESOLVED = the bug is fixed; RELEASED = the platform release is live.

## How to add a new enum value

1. Edit `prisma/schema.prisma` and add the value at the bottom of the
   enum (Postgres keeps order, and ordering can show up in UI sorts).
2. Create + apply a migration (`prisma migrate dev --name add_foo_state`).
   Prisma generates `ALTER TYPE … ADD VALUE` automatically.
3. `nx run database:generate-client` to refresh
   `libs/python/database/enums.py`.
4. Update any handler that does an exhaustive `match`/`if` over the enum —
   the linter won't catch a missing arm.
5. Update `apps/frontend/app/src/lib/types/models.ts` to add the new
   literal to the union.
6. Update any UI status-color / display-label table (commonly in
   `apps/frontend/app/src/lib/components/StatusBadge.svelte` or similar).
7. Update this file's table.
8. If a user-facing notification trigger maps to it, also update
   `NotificationType` if a new category is required.

## How to remove or rename an enum value

Renames in Postgres are non-trivial. The pattern is:

1. Add the new value first (additive migration, ships to prod).
2. Migrate data — any rows on the old value get rewritten to the new one.
3. Drop the old value in a follow-up migration.
4. Each phase must be deployed independently, since rolling deploys can
   have old + new code talking to the same DB simultaneously.

For values that already exist in production data, see
[`migrations.md`](migrations.md) for the multi-deploy pattern.

## Common failure modes

- **`InvalidEnumValue` raised by the Python client.** A handler is
  passing a raw string (or a value from a stale frontend) that isn't
  declared in the schema. Always use `enums.<Name>.<VALUE>`.
- **Frontend shows enum value verbatim in a label column.** `models.ts`
  has the value but no display mapping was added — find the
  display-label table for that enum and add the human string.
- **Backend test passes but the API returns 500 in staging.** A
  newly-added enum value works in the local dev client (regenerated) but
  the staging image was built before the schema change. Rebuild the
  image and redeploy. See
  [`../deploy/`](../deploy/) for the deploy flow.
- **`P3018: migration failed` on `ALTER TYPE … ADD VALUE` with `CONCURRENTLY`.**
  Postgres does not allow `ADD VALUE` inside a transaction in older
  versions. Prisma now emits these correctly, but if you're hand-editing
  a migration to split it apart, the `ADD VALUE` step must be in its own
  `migration.sql` (or use the prisma-generated form). See
  [`migrations.md`](migrations.md).
- **Lowercase enum confused with uppercase variant.** `FirmwareVariant.release`
  is lowercase. Searching the codebase for `RELEASE` won't find it.
  Search the schema or this file before assuming an enum is uppercase.

## Related knowledge

- [`schema-overview.md`](schema-overview.md) — model-by-model context.
- [`migrations.md`](migrations.md) — how enum changes flow through
  migrations and the init container.
- [`../conventions.md`](../conventions.md) — backend-frontend type
  mirroring contract.
- [`../glossary.md`](../glossary.md) — domain definitions for the terms
  these values describe.
