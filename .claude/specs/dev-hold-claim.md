# DEV_HOLD fixture-claim — design spec

Local-dev TDD loop for test authors. Lets a developer lease a real fixture or a
set of raw nodes for the duration of a development session, with the backend
honoring the lease against concurrent scheduled work.

## Conceptual model

Reservation state for a Fixture is **derived live** today (no stored flag).
DEV_HOLD follows that pattern: it's its own entity, and "is fixture busy?"
becomes "any active TestRun OR ManufacturingSession OR FixtureClaim."

A claim has two mutually-exclusive binding modes:

- **fixture-mode**: `fixtureId` set → all slots of that fixture are held
- **node-mode (ad-hoc)**: `claimedNodes` set → specific nodes held; no Fixture row created. Used when no Fixture exists yet (first-time bootstrap) or for cross-fixture node scratch.

The two modes share the same lifecycle (heartbeat, expire, release) and the same audit surface.

## Schema diff

```prisma
enum FixtureClaimStatus {
  ACTIVE        // heartbeat alive, holder using the hardware
  RELEASED      // explicit release by holder via API
  EXPIRED       // sliding TTL elapsed without heartbeat
  ABANDONED     // hard ceiling (8h) hit
}

model FixtureClaim {
  id              String              @id @default(cuid())

  userId          String
  user            User                @relation(fields: [userId], references: [id])

  // EXACTLY ONE of (fixtureId, claimedNodes) is meaningful at a time.
  fixtureId       String?
  fixture         Fixture?            @relation(fields: [fixtureId], references: [id])

  claimedNodes    ClaimedNode[]

  status          FixtureClaimStatus  @default(ACTIVE)

  acquiredAt      DateTime            @default(now())
  lastHeartbeatAt DateTime            @default(now())
  expiresAt       DateTime
  hardCeilingAt   DateTime
  releasedAt      DateTime?

  description     String?

  createdAt       DateTime            @default(now())
  updatedAt       DateTime            @updatedAt

  @@index([fixtureId, status])
  @@index([userId, status])
}

model ClaimedNode {
  id        String       @id @default(cuid())
  claimId   String
  claim     FixtureClaim @relation(fields: [claimId], references: [id], onDelete: Cascade)
  nodeId    String
  node      Node         @relation(fields: [nodeId], references: [id])
  label     String?      // optional slot label hint for the claimer

  @@unique([claimId, nodeId])
  @@index([nodeId])
}
```

User, Fixture, Node get a back-relation field added (no schema breakage).

## TTL math

- `expiresAt = lastHeartbeatAt + 5 min` (sliding window)
- `hardCeilingAt = acquiredAt + 8 hours` (immutable, set at creation)
- A heartbeat sets `lastHeartbeatAt = now`, `expiresAt = min(now + 5min, hardCeilingAt)`
- Background job (or computed-on-read) transitions ACTIVE → EXPIRED when `now > expiresAt`, ACTIVE → ABANDONED when `now > hardCeilingAt`

## API

All endpoints use `@require_permissions` and emit `log_audit` per repo policy.

### `POST /v2/fixture-claims` — create

Required permission: `VALIDATION_RUN` (validation devs) or `MANUFACTURING_MANAGE` (mfg devs).

Body (one shape):
```json
// fixture-mode
{ "fixtureId": "fix_abc", "ttlSeconds": 18000, "description": "regression scratch" }
// node-mode
{ "nodes": [{ "nodeId": "node_xyz", "label": "slot1" }], "ttlSeconds": 18000, "description": "..." }
```

`ttlSeconds` is optional, defaults to 1h, clamped to 8h ceiling.

Response 201:
```json
{
  "id": "clm_...",
  "status": "ACTIVE",
  "fixtureId": "fix_abc",                // null in node-mode
  "slotBindings": [
    { "label": "slot1", "nodeId": "node_xyz", "mtibHost": "10.4.45.38:50053" }
  ],
  "acquiredAt": "...",
  "expiresAt": "...",
  "hardCeilingAt": "..."
}
```

Refuses with 409 if any of the requested nodes (or any slot of the requested fixture) is currently held by another active claim, an ACTIVE TestRun, or an ACTIVE ManufacturingSession.

### `POST /v2/fixture-claims/<id>/heartbeat` — extend lease

Permission: caller must be the claim's `userId` (or admin).
Refuses 410 if claim is EXPIRED/RELEASED/ABANDONED.

Response 200: `{ id, lastHeartbeatAt, expiresAt }`

### `POST /v2/fixture-claims/<id>/release` — finalize

Permission: caller must be the claim's `userId` (or admin).
Idempotent: returns 200 on already-released.

Response 200: claim object with `status=RELEASED, releasedAt=...`

### `GET /v2/fixture-claims` — list

Query params: `userId` (defaults to caller), `status` (defaults to ACTIVE), `fixtureId`.
Response 200: `{ claims: [ ... ] }`

### `GET /v2/fixture-claims/<id>` — fetch one

Response 200: claim object.

## Reservation gate

Wherever a TestRun or ManufacturingSession starts and binds to a fixture, the start path must check:

```
busy = (
    any active TestRun on fixtureId
    OR any active ManufacturingSession on fixtureId
    OR any ACTIVE FixtureClaim where fixtureId == this.fixtureId
    OR any ACTIVE FixtureClaim with ClaimedNode.nodeId IN (this fixture's slot nodes)
)
if busy: return 409
```

Symmetrically, claim-create checks the same conditions. The `is_fixture_busy()` helper is the single source of truth for both paths.

## Node→address resolution helper

Extracted from current scheduler.py logic. Signature:

```python
def resolve_node_addresses(node_ids: list[str], *, port: int = MTIB_PORT) -> dict[str, str]:
    """Return { nodeId: 'ip:port' } using K8s API for live IP lookup, falling back to Node.ipAddress."""
```

Used by both scheduler.py (existing path) and the new claim endpoints.

## corectl surface

State file written to project root: `.concord-claim.json`

```json
{
  "id": "clm_...",
  "fixtureId": "fix_abc",
  "slotBindings": [{ "label": "slot1", "nodeId": "node_xyz", "mtibHost": "10.4.45.38:50053" }],
  "expiresAt": "...",
  "hardCeilingAt": "...",
  "heartbeatPid": 12345
}
```

`.gitignore` gets `.concord-claim.json` appended (and the templates).

### `corectl test claim` — acquire

```
corectl test claim --fixture sigma5-bench-mateo [--ttl 3600]
corectl test claim --node verdin-15005689 [--node verdin-15005690 ...] [--ttl 3600]
```

Behavior:
1. POST to /v2/fixture-claims
2. Write .concord-claim.json
3. Fork a heartbeat daemon (detached process) that POSTs heartbeat every 60s and exits when the state file disappears or claim becomes non-ACTIVE.
4. Print summary to stdout (id, expires, slot bindings).

### `corectl test unclaim` — release

1. Read .concord-claim.json
2. POST /v2/fixture-claims/<id>/release
3. Delete .concord-claim.json (daemon notices and exits)
4. If state file missing: print "no active claim" and exit 0.

### `corectl test status` — show

Prints current claim from state file + live status from backend (in case it expired).

### `corectl test run <stage>` — modified

Before invoking pytest:
1. Read .concord-claim.json (skip if missing — falls back to existing MTIB_HOST/MTIB_HOSTS env)
2. Inject env: single-slot → `MTIB_HOST=<slot[0].mtibHost>`; multi-slot → `MTIB_HOSTS=h1,h2,...`
3. Run pytest subprocess as today.

## Audit events

- `fixture.claim.create` — details: { fixtureId, nodeIds, ttlSeconds, description }
- `fixture.claim.heartbeat` — details: { expiresAt } (low volume; skip if hot path becomes noisy)
- `fixture.claim.release` — details: { reason: "explicit"|"expired"|"abandoned" }

## All-three-envs

This is backend behavior — no new env vars introduced. helm values untouched. The migration runs in the init container as part of the normal deploy.
