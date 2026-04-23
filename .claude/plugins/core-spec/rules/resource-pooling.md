# Resource Pooling Protocol

When multiple agent teammates execute tests against a shared platform (database, API,
hardware), they MUST follow this protocol to avoid collisions.

## Architecture

```
┌── SHARED PLATFORM (one instance) ────────────────────────────┐
│  docker-compose: http-api :9001, postgres :5433, minio :8675 │
│  Frontend: :4200                                              │
│  K8s cluster (MTIB deployments)                               │
│  External APIs (Bitbucket, CoreCloud)                         │
└──────────────────────────────────────────────────────────────┘
        ↑           ↑           ↑           ↑
   Teammate A  Teammate B  Teammate C  Teammate D
   (Stage 2)   (Stage 7)   (Stage 10)  (Stage 14)
```

All teammates share the SAME platform. No separate instances per teammate.

## The Three Rules

### Rule 1: DB Wipe Happens ONCE — Before Any Team Starts

```
Global Setup (run by lead, BEFORE creating any team):
  1. nx stop platform          # Stop everything
  2. Reset DB: prisma migrate reset --force
  3. Re-run migrations: prisma migrate deploy
  4. Run platform seed (roles, permissions, dev users ONLY)
  5. nx start platform         # Restart everything
  6. Verify health: GET /v2/docs → 200
  7. NOW create teams and launch waves
```

**NEVER wipe the DB during wave execution.** Teammates clean up their own data
at the end of their stage, not by wiping the whole DB.

### Rule 2: Teammates Use Stage-Prefixed Test Data

Every piece of test data created by a teammate MUST be uniquely identifiable
so it doesn't collide with other teammates' data:

```typescript
// Each teammate prefixes ALL test data with their stage number
const PREFIX = `s${STAGE_NUMBER}`;  // e.g., "s2", "s7", "s10"

// Product names
const productName = `${PREFIX}-Alpha-Test`;           // "s3-Alpha-Test"

// Fixture names
const fixtureName = `${PREFIX}-E2E-Fixture`;          // "s7-E2E-Fixture"
const stationId = `${PREFIX}-station-33`;             // "s7-station-33"

// User emails
const userEmail = `${PREFIX}-test@concord.dev`;       // "s14-test@concord.dev"

// Bitbucket branches
const branchName = `e2e/${PREFIX}-test-${timestamp}`; // "e2e/s5-test-1712625600"

// MinIO keys
const storagePrefix = `e2e/${PREFIX}/`;               // "e2e/s10/"

// API keys
const apiKeyName = `${PREFIX}-E2E-Key`;               // "s14-E2E-Key"
```

### Rule 3: Hardware Is Serial — Never Parallel

Physical hardware (MTIB, J-Link probes, DUTs) can only be used by ONE
teammate at a time. Stages requiring hardware MUST run sequentially.

```
PARALLEL-SAFE (no hardware):
  Stage 2: Auth & Navigation (UI only)
  Stage 3: Product CRUD (API + UI)
  Stage 10: Mfg Backend (unit tests only)
  Stage 11: Mfg Frontend (vitest only)
  Stage 14: User Management (API + UI)

SERIAL ONLY (hardware required):
  Stage 9: Validation Execution (MTIB)
  Stage 13: Manufacturing E2E (MTIB)
  → These run in Wave 4, sequentially, never parallel
```

## Resource Contention Matrix

| Resource | Concurrent OK? | Isolation Method |
|----------|:--------------:|-----------------|
| HTTP API (:9001) | Yes | Flask handles concurrent requests |
| PostgreSQL (:5433) | Yes | Stage-prefixed data avoids collisions |
| MinIO (:8675) | Yes | Stage-prefixed storage keys |
| Frontend (:4200) | Yes | Read-only navigation is safe; forms use prefixed data |
| K8s API | Yes | Stage-prefixed deployment names |
| Bitbucket API | Yes | Stage-prefixed branch names |
| CoreCloud API | Yes | Only used in serial stages (Wave 4) |
| MTIB hardware | **NO** | Serial only — Wave 4 sequential |
| Fixture locking | **NO** | Only one fixture per MTIB — serial stages |

## Teammate Cleanup Protocol

Each teammate cleans up ITS OWN data at the end of its stage:

```typescript
// At end of stage:
async function cleanup(page: Page, prefix: string) {
  // Delete products created by this stage
  const products = await apiGet(page, `/v2/products?search=${prefix}`);
  for (const p of products) await apiDelete(page, `/v2/products/${p.id}`);

  // Delete fixtures
  const fixtures = await apiGet(page, `/v2/fixtures?search=${prefix}`);
  for (const f of fixtures) await apiDelete(page, `/v2/fixtures/${f.id}`);

  // Delete users
  const users = await apiGet(page, `/v2/users?search=${prefix}`);
  for (const u of users) await apiDelete(page, `/v2/users/${u.id}`);

  // Delete Bitbucket branches
  await cleanupE2EBranches(repo, `e2e/${prefix}-`);

  // Delete MinIO artifacts
  await cleanupMinioArtifacts(`e2e/${prefix}/`);
}
```

**Exception:** The final cleanup stage (Stage 16) does a comprehensive sweep
to catch anything teammates missed.

## Platform Lifecycle During Overnight Execution

```
T+0:00  Lead: Stop platform, wipe DB, restart, seed, verify health
T+0:05  Lead: Create Wave 1 team (2 teammates)
T+0:05  Teammates work against SHARED platform — prefixed data
T+1:00  Wave 1 complete — teammates clean up their data
T+1:05  Lead: Merge worktrees, reconcile, deploy to staging
T+1:15  Lead: Create Wave 2 team (4 teammates)
T+1:15  Teammates work against SAME platform — prefixed data
T+2:30  Wave 2 complete — teammates clean up their data
...
T+8:00  Stage 16: Final cleanup sweep — verify zero non-system data
```

The platform runs CONTINUOUSLY. No restarts between waves. Each teammate
is a good citizen — creates prefixed data, cleans up after itself.

## What Teammates Must Know

Include this in EVERY teammate's prompt:

```
RESOURCE POOLING RULES:
- You share the platform with other teammates. DO NOT wipe the DB.
- Prefix ALL test data with "s{YOUR_STAGE_NUMBER}-" to avoid collisions.
- Clean up your prefixed data at the end of your stage.
- MTIB hardware is NOT available to you (only Wave 4 sequential stages).
- The API at localhost:9001 handles concurrent requests — safe to use.
- The frontend at localhost:4200 handles concurrent navigation — safe to use.
- If you need data created by another stage, use SendMessage to request it.
```
