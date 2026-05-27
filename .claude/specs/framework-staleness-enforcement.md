# Framework staleness enforcement — design spec

**Status**: Draft for review, 2026-05-26
**Author**: design captured by AI on behalf of Mateo
**Motivates**: closes the gap where test apps drift silently between concord releases. Today's Layer 5 (`/concord-release` Phase 11 sweep) only fires at concord release time; this spec adds **continuous** enforcement: every `corectl` invocation does a lightweight check, the platform tracks per-product app staleness, and users with product access get UI/SocketIO notifications.

---

## Problem statement

Test apps live in independent repos (sigma5_manufacturing, alpha_validation, etc.). Each has a `.framework-version` stamp and a `concord.yaml`'s `package.framework` PEP 440 constraint. Today's enforcement:

| Layer | When it fires | What it catches |
|---|---|---|
| 1-4 (Phase D) | At deploy / runner-startup time | Runtime version-skew |
| 5 (Phase D) | At `/concord-release` Phase 11 | Scaffold drift on registered apps, sweep-once |

What's missing — the continuous gaps:

1. A dev working entirely in a test app repo (not touching concord) has **no signal** that they're behind until they happen to run `corectl test validate`.
2. The platform has **no memory** of "what framework version was this upload built against" beyond the loose `framework: ">=X.Y.Z"` constraint.
3. The UI shows test packages but **no staleness signal** — operators can't see "this product's app is 2 minor versions behind".
4. There's no **notification path** to alert users-with-access that their product's app needs attention.

The 2026-05-26 incident: sigma5_validation was on corectl 0.11.0 scaffold while concord shipped 0.12.4. Layer 5 caught it during release. But a dev who'd opened that repo standalone last week would've been reading stale rules with no warning.

## Goals

1. **Tiered corectl enforcement** — every command does a pre-check; patch behind = silent info, minor behind = warn, breaking = block (with escape).
2. **Backend state of every test app** — one row per (product, type) tracking "uploaded against framework X.Y.Z, is it stale, when last refreshed".
3. **System notifications** routed via existing RBAC — users with access to a product see a notification when its app falls behind.
4. **UI surfaces** — staleness badge on product page, warning in session-create wizard, admin-wide health view.
5. **Manual breaking-change flag** at concord release time. No auto-detection from semver bumps alone.

## Non-goals

- Auto-upgrading the dev's local corectl install. (Stays manual via `corectl update`.)
- Auto-running `corectl test update --apply` on the dev's behalf. (Devs review the diff.)
- Email digests / Slack notifications. (Maybe later. MVP is in-app only.)
- Tracking individual developers' local corectl versions. (Per-product, not per-dev.)
- Cross-product blast-radius analysis. (Out of scope; the audit log already captures this if needed.)

## Conceptual model

Two new entities; everything else is read-side.

```
FrameworkRelease — one row per concord release version
   ├── version: text @id  (e.g. "0.12.4")
   ├── releasedAt: timestamp
   ├── breaking: bool      ← manual at release time
   ├── notes: text         ← release-notes summary, surfaced to devs
   └── createdById: text   ← who cut the release (audit)

TestAppState — one row per (productId, type)
   ├── id: text @id
   ├── productId: text → Product
   ├── type: TestPackageType (VALIDATION | MANUFACTURING)
   ├── latestUploadId: text? → TestPackage
   ├── uploadedFrameworkVersion: text?   ← read from concord.yaml's `package.framework` floor at upload time
   ├── uploadedScaffoldVersion: text?    ← read from .claude/.framework-version inside the uploaded tarball
   ├── uploadedAt: timestamp?
   ├── lastDriftCheckedAt: timestamp?
   ├── isStaleScaffold: bool             ← computed: uploadedScaffoldVersion < latest FrameworkRelease.version
   ├── isStaleConstraint: bool           ← computed: uploadedFrameworkVersion constraint floor < latest
   ├── breakingDriftSince: text?         ← lowest version of FrameworkRelease.breaking=true between upload and latest
   └── @@unique([productId, type])
```

Compute properties (`isStaleScaffold`, `isStaleConstraint`, `breakingDriftSince`) are denormalized at write time — recomputed when:
- A new FrameworkRelease row is written → batch-update all TestAppState rows.
- A new TestPackage is uploaded → update the matching TestAppState.

## API surface

All routes under `/v2/`, follow concord's standard contract (`@require_permissions`, `log_audit` on mutations).

```
POST   /v2/framework-releases                    # writes by /concord-release skill at release time
       body: { version, breaking, notes }
       permission: SYSTEM_MANAGE

GET    /v2/framework-releases/latest             # corectl polls this
       returns: { version, releasedAt, breaking, notes }

GET    /v2/framework-releases?since=<version>    # corectl uses to detect breaking-since-my-version
       returns: [{ version, breaking, notes }, ...]

GET    /v2/products/<id>/test-app-state          # UI badge / wizard warning queries
       returns: { validation: TestAppState, manufacturing: TestAppState }

GET    /v2/admin/test-app-health                 # admin overview
       permission: SYSTEM_VIEW
       returns: [{ product, validation: {...}, manufacturing: {...} }, ...]
```

The `POST /v2/products/.../test-packages` upload endpoint extends to extract `.framework-version` from the uploaded tarball and populate the matching TestAppState row in the same transaction.

## corectl client design

### Pre-check decorator

Every `corectl` command gets a click decorator (`@check_framework_version`) that runs **before** the command body. Lightweight:

```python
def _check_framework_version(command_name: str) -> None:
    """Pre-flight: compare local corectl version against the platform's latest FrameworkRelease.

    Tiered behavior:
      - patch behind (0.12.3 → 0.12.4): info line, no block
      - minor behind (0.11.x → 0.12.x): warn loudly, no block
      - any FrameworkRelease.breaking=True with version > local: BLOCK, exit 2,
        unless CONCORD_FORCE_STALE_LOCAL=1.

    Cache the platform response in ~/.config/corectl/version-cache.json for
    60 minutes so repeated commands don't hit the API.
    """
    cache = _load_cache()
    if cache.fresh_within(minutes=60):
        result = cache.result
    else:
        try:
            result = _api_get("/v2/framework-releases?since=" + local_version)
            _save_cache(result)
        except (ConnectionError, Timeout):
            return  # offline OK; never block on network failure
    _apply_tiered_policy(result, command_name)
```

### Tier rules

```
diff = parse(latest.version) - parse(local.version)
breaking_between = any(r.breaking for r in releases_since_local)

if breaking_between:
    log_block_banner(...)
    if not os.environ.get("CONCORD_FORCE_STALE_LOCAL"):
        sys.exit(2)
    log_force_warn_banner(...)
elif diff.minor > 0 or diff.major > 0:
    log_warn_one_liner(...)
elif diff.patch > 0:
    log_info_one_liner(...)
```

### Cache file format

`~/.config/corectl/version-cache.json`:
```json
{
  "checked_at": "2026-05-27T03:45:00Z",
  "local_version": "0.12.3",
  "latest_version": "0.12.4",
  "releases_since_local": [
    {"version": "0.12.4", "releasedAt": "...", "breaking": false, "notes": "Phase D Layer 5"}
  ]
}
```

### Escape hatches

- `CONCORD_FORCE_STALE_LOCAL=1` — bypass the breaking-change block (loud-warn banner).
- `--skip-version-check` flag on individual commands (also bypass, loud-warn).
- `CORECTL_NO_VERSION_CHECK=1` — fully disable the pre-check (e.g., for CI runs in environments without network). Logs an info line on every command.

## Frontend surfaces

Three components, all under `apps/frontend/app/src/lib/components/test-apps/`:

1. **`<TestAppStaleBadge product={p} type="MANUFACTURING">`** — pill-style badge:
   - green "up to date"
   - yellow "scaffold behind by 1 minor"
   - red "🚨 breaking change since last upload"
   - Tooltip with the exact version delta + "Refresh: `cd <repo> && corectl test update --apply && corectl test upload`".

2. **`<TestAppHealthBanner product={p}>`** — full banner at the top of the manufacturing/validation session-create wizard. Shows the same info as the badge but expanded with the remediation copy-pasteable.

3. **`/admin/test-app-health`** — admin-only route, table of every product × every type with their staleness state. Filters: `stale only`, `breaking only`. CSV export.

All three subscribe to the new SocketIO room `framework_release_updates` so the badge/banner refresh live when a new FrameworkRelease is written.

## Notifications (RBAC-scoped)

Concord has an existing `notifications` table (verify in the prisma schema-overview knowledge file before implementation). Reuse it. Algorithm at FrameworkRelease write time:

1. New release lands; recompute `isStaleScaffold` / `isStaleConstraint` / `breakingDriftSince` across all TestAppState rows.
2. For each TestAppState that flipped from "up to date" to "stale":
   - Look up the Product's user access list (Per-Product `AccessLevel` from auth-defaults.md).
   - For each user with `view` or higher: write a Notification row.
   - Push via SocketIO to that user's room.
3. Notifications include: product slug, type, current state ("scaffold behind by 1 minor" / "breaking change in between"), and the remediation command.

Notification model fields:
```
type:    text                                            # e.g. "test_app_stale" | "test_app_breaking_change"
title:   text
body:    text                                            # markdown OK
productId: text?                                         # for routing / filtering
severity: enum(INFO, WARNING, BREAKING)
ackedAt:  timestamp?                                     # user dismissed
createdAt: timestamp
userId:   text                                           # recipient
```

For users without active sessions (no SocketIO connection): the notification persists in the table, visible next time they log in.

## Release-time integration (`/concord-release` skill)

Insert a new step in the skill, after Phase 4 (version bump), before Phase 5 (knowledge updates):

> **Phase 4.5 — Breaking-change flag**
> Ask the operator: "Is this a breaking change for test apps? (yes/no, default no)". Default `no` because most releases aren't. If yes, prompt for the specific reason — capture it in `FrameworkRelease.notes`.

Then in Phase 9 (deploy production), after wheel publishes and helm rollout completes:

> **Phase 9.5 — Write FrameworkRelease row**
> `POST /v2/framework-releases` with the version, breaking flag, and notes. Triggers the TestAppState batch recompute + notification fan-out.

The Phase 11 sweep (Layer 5) **stays** — it's the one-shot belt-and-suspenders. The FrameworkRelease row + notifications + UI badges are the continuous-state side.

## Phased implementation plan

The whole feature is ~2-3 weeks of work. Phase it so each lands clean:

### Phase 1 — Backend foundation (1-2 days, TDD)
- New Prisma models (`FrameworkRelease`, `TestAppState`)
- Forward migrations
- Python client regen
- Frontend `models.ts` mirror
- Knowledge files (`prisma/schema-overview.md`, new entity sections)
- http-api routes (`POST /v2/framework-releases`, `GET /v2/framework-releases/latest`, `GET /v2/framework-releases?since=`)
- Audit logging on all writes
- Route tests (TDD)

### Phase 2 — Release-time integration (0.5 day)
- Extend `/concord-release` skill with Phase 4.5 + 9.5
- Tests: golden snapshot of new skill prompts

### Phase 3 — corectl pre-check (2-3 days, TDD)
- New module `corectl.framework_check` with the tiered policy
- Cache file management
- Click decorator wiring
- Escape hatches
- Tests for all 4 outcomes (patch, minor, breaking, network-offline)
- Tests for cache TTL behavior
- Tests for the escape-hatch logging

### Phase 4 — TestAppState ingestion (1-2 days)
- Extend upload endpoint to populate TestAppState
- Recompute job triggered by new FrameworkRelease writes
- Initial backfill script for existing test_packages → TestAppState
- Tests

### Phase 5 — UI surfaces (2-3 days)
- Three components above (Badge, Banner, AdminHealth page)
- Component tests
- SocketIO subscription
- Visual verification on staging

### Phase 6 — Notifications (1-2 days)
- Verify existing Notification model surface (or extend)
- Permission-scoped fan-out at FrameworkRelease write
- SocketIO push
- Notification-tray integration in the existing UI

**Total: ~10-15 days of careful work, across 6 separate PRs ideally.**

## Risks & open questions

1. **Network dependency in `corectl`** — the pre-check assumes corectl can hit the platform. For offline / VPN-not-up cases the cache handles short windows, but a dev who's offline for days will get stale info. Acceptable since the worst case is the cache expires and the next online command does the check.

2. **Constraint floor vs scaffold version** — a test app's `package.framework: ">=0.9.0"` floor doesn't track scaffold drift. We need BOTH `uploadedFrameworkVersion` (from manifest) and `uploadedScaffoldVersion` (from `.framework-version` stamp inside the tarball). The corectl stamp bug (2026-05-26) means stamps lag content; this spec doesn't fix that bug — see TODO below.

3. **Notification spam at major releases** — every release writes notifications for every stale product × every user with access. Throttle: aggregate by user within a 5-minute window into a single digest notification.

4. **The corectl `.framework-version` stamp bug must be fixed first or in parallel** — TestAppState's `uploadedScaffoldVersion` derives from that file. If the file lies, the state lies. Schedule the stamp-update fix as a corectl P0 before Phase 4.

5. **RBAC permission for `POST /v2/framework-releases`** — should it be `SYSTEM_MANAGE` (admin-only) or a new `RELEASES_MANAGE`? Likely the former, since this only fires from `/concord-release` which is already admin-only. Confirm with auth-defaults.md.

6. **Breaking flag retroactively** — what if someone realizes mid-week that v0.12.4 was actually breaking? Need an `UPDATE` endpoint on FrameworkRelease, audit-logged. Add to Phase 1.

7. **Cross-product impact** — when concord ships, all products see the new release. Notifications could be batched into a single "concord vX.Y.Z released, your apps are stale" message per user. UX call.

## Related

- `.claude/rules/version-coupling.md` — the contracts this spec extends
- `.claude/knowledge/deploy/runner.md` — Phase D Layers 1-5 (this spec adds continuous staleness alongside)
- `.claude/knowledge/workflows/version-skew.md` — case studies; this spec adds prevention for case studies 3 and 4
- `.claude/specs/dev-hold-claim.md` — exemplar spec format

## Decision log

| Decision | Choice | Rationale |
|---|---|---|
| Enforcement strictness | Tiered (patch=info, minor=warn, breaking=block) | Lowest friction for compatible bumps; loud blocking only on actual breaking changes |
| Notification channels | corectl-side + UI banner + SocketIO push (RBAC-scoped) | Hits devs in their working surface (corectl) AND product owners on the platform |
| Breaking-flag source | Manual prompt at /concord-release time | Human judgment; semver bumps don't always mean breaking |
| Backend storage | New Prisma models | Real schema, queryable, audit-loggable, durable |

## Approval gates before implementation

1. Mateo reviews this spec — confirm or revise the decisions above.
2. `db-schema-eng` reviews the Prisma diff (entity shape, indexes, constraints).
3. `frontend-eng` reviews the three component designs.
4. `corekinect-sdk-eng` reviews the corectl pre-check decorator + cache design.
5. The corectl `.framework-version` stamp bug is filed and assigned BEFORE Phase 4 (or Phase 4 gets blocked on it).

Once approved, implementation kicks off as 6 separate branches per the phase plan.
