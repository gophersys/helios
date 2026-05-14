---
name: add-fixture
description: Define a new fixture (test rig) on the platform — registers a TestBedDesign, creates a Fixture instance, binds MTIB slots, and exposes it to validation/manufacturing runs. Use this for adding a new fixture configuration; use /onboard-mtib first if the underlying Verdin hardware isn't in the cluster yet.
argument-hint: "<fixture-name> — <product> — <DEV|RELEASE> — <MANUFACTURING|VALIDATION>"
---

# /add-fixture

Spawn `architect` first to confirm scope (is this a new fixture instance of an existing design, or a brand-new design?), then `http-api-eng` for the API-side wiring, then `frontend-eng` if the fixture-config UI needs a tweak. The bulk of the work is operator-driven through the web UI — this skill makes sure the prerequisites are in place.

## Authoritative knowledge to load

- `.claude/knowledge/product-domains/fixtures.md` — the domain model (TestBedDesign, Fixture, FixtureSlot, Node, FixturePurpose, NodeType, derived lock state).
- `.claude/knowledge/deploy/verdin-edge.md` — how MTIBs (Nodes) get on the cluster in the first place.
- `.claude/knowledge/apps/backend/http-api.md` — `/v2/fixtures/*` endpoints.
- `.claude/knowledge/product-domains/validation.md` and `.claude/knowledge/product-domains/manufacturing.md` — what runs *on* the fixture.

## Decide first: design vs instance

A **`TestBedDesign`** is the *template* — a versioned hardware design (PCB/wiring spec) bound 1:1 to a `TestPackage` via its `fixture.yaml` manifest. New designs are rare; they arrive when a new product variant launches or an existing fixture is redesigned.

A **`Fixture`** is a *physical instance* of a design — one rack, one set of slots, one specific MTIB binding. New fixtures are common; you stand up a new instance every time you build a new test rig.

Pick:

- **New design needed?** The fixture's hardware/wiring is unlike any existing design. → You must upload a test package (manufacturing or validation type) whose `fixture.yaml` introduces the new design. The platform creates the `TestBedDesign` row when the package upload succeeds; the design's status mirrors the package's (`DEVELOPMENT` → `RELEASED`). Use `corectl upload` from the project that defines this fixture.
- **Existing design, new instance?** Skip the design step — just create the Fixture instance.

## Pre-flight

- **Verdin nodes must be in the cluster as Ready.** Verify with `kubectl get nodes -l concord.corekinect.com/workload-edge=true`. Their `NodeType` (set during registration) must match what the fixture expects (`MANUFACTURING` or `VALIDATION` — they have to agree, see `fixtures.md::Entities`).
- **Nodes must be `register`ed in the platform DB.** Operators do this via the "Discover MTIBs" wizard at the Fixtures page. If a node shows in K8s but not in the platform, run `/onboard-mtib` first.
- **Test package** that defines the fixture's design must be uploaded (DEVELOPMENT is fine for dev fixtures, RELEASED for production fixtures). The fixture's `FixturePurpose` gates this: `DEV` fixtures accept DEVELOPMENT packages, `RELEASE` fixtures only accept RELEASED.
- **Product** must exist. If you're standing up the first fixture for a new product, create the product entry first via the admin UI (operator-only flow).

## The flow

1. **(if new design)** Upload the test package that defines the fixture design:
   ```bash
   cd <project-dir>
   corectl validate        # confirm manifest + fixture.yaml schema
   corectl upload          # → DEVELOPMENT
   # (operator promotes to RELEASED later via the UI or `corectl test release <pkg-id>`)
   ```
   The `TestBedDesign` row appears in the platform when the upload completes.

2. **Create the Fixture instance** in the platform UI (`/fixtures` → "New fixture"). Or scripted via http-api — the actual `FixtureCreateRequest` shape (`apps/backend/http-api/src/api/v2/fixtures/types.py:6`):
   ```
   POST /v2/fixtures
     {
       "name": "alpha-c1-panel-01",
       "productId": "<product-uuid>",
       "type": "MANUFACTURING" | "VALIDATION",
       "designId": "<design-uuid>",            // optional but expected for fixtures backed by a design
       "stationId": "<station-uuid>",          // optional
       "description": "...",                    // optional
       "metadata": { ... },                     // optional
       "slots": [{ "slotIndex": 0, "label": "Slot 1" }, ...],  // optional explicit slot list
       "panelRows": 5, "panelCols": 1           // optional, for panel auto-layout
     }
   ```
   The instance starts with all slots empty (`nodeId: null`). `purpose` is **not** a create-time field — it defaults to `RELEASE` in Prisma and gets set via `PUT /v2/fixtures/<id>` if you need `DEV`.

3. **Bind each slot to a Node** via the slot-assign endpoint:
   ```
   POST /v2/fixtures/<fixture-id>/slots/<slot-uuid>/assign
     { "nodeId": "<node-uuid>" }            // or { "nodeId": null } to unassign
   ```
   The slot URL takes the slot's UUID (not its index). The same endpoint handles assign and unassign; `null` releases the slot and tears down its MTIB deployment.

   On a non-null assignment, the backend's `_deploy_mtib_for_slot` (`apps/backend/http-api/src/api/v2/fixtures/fixtures.py:1146`) renders `apps/backend/http-api/assets/templates/mtib_server_deployment.yaml` and applies it into the right namespace. The MTIB pod lands on the Verdin within ~30s. See `.claude/knowledge/deploy/verdin-edge.md::MTIB Deployment template` for the full substitution table.

4. **Verify the fixture is healthy**:
   - `GET /v2/fixtures/<fixture-id>` should report `lockState: FREE` (derived live — see `fixtures.md::Lifecycle`).
   - Each slot's `mtib-server` pod is `Ready` (check via the UI's fixture-health view, or `kubectl -n <env> get pods -l app.kubernetes.io/name=concord-mtib-server`).
   - `MOTION_ENABLED` is correctly derived from fixture type — `true` for `VALIDATION`, `false` for `MANUFACTURING`. Inspect the mtib-server pod's env vars to confirm.

## Decision points

- **`DEV` vs `RELEASE` purpose**: dev fixtures accept any test package; release fixtures gate on `TestPackage.status=RELEASED`. Pick `DEV` for an engineer's bench, `RELEASE` for the manufacturing floor or the customer-facing validation rig.
- **`MANUFACTURING` vs `VALIDATION` type**: must agree across the fixture, its slots' nodes, and the test package's type. `MOTION_ENABLED` derivation depends on this — validation fixtures get motion (FluidNC linear rails), manufacturing does not.
- **Panel layout for multi-slot fixtures**: the design's `panelLayout` JSON template can be overridden per-instance. Default to the design's template unless there's a reason to differ.

## Don't

- Don't create a fixture instance referencing a `TestBedDesign` that's `DEVELOPMENT` if `purpose=RELEASE`. The package-status gate will reject runs on it.
- Don't bind a `MANUFACTURING` node to a `VALIDATION` fixture (or vice versa). The types must agree on both sides.
- Don't manually `kubectl apply` an mtib-server Deployment. The platform owns those — see `deploy/verdin-edge.md::MTIB Deployment template`.
- Don't bind two slots to the same node. The DB enforces `@unique` on `FixtureSlot.nodeId` (NULL is exempt — multiple empty slots are fine).

## Verify

- `GET /v2/fixtures/<id>` returns the fixture with all slots populated, `lockState=FREE`.
- Each slot's bound Node shows `status: ONLINE` (live-derived from K8s + gRPC health, not stored).
- A no-op test run against the fixture succeeds: `corectl run smoke --fixture <fixture-name>`.

## Update knowledge

If the fixture introduces a new pattern (new slot layout, new MTIB config field, new FixturePurpose gate behavior), update `.claude/knowledge/product-domains/fixtures.md`. Otherwise no `.claude/` change is needed — adding a fixture instance is a data operation, not a code change.

## Related

- `/onboard-mtib` — if the Verdin nodes aren't in the cluster yet.
- `/concord-release` — if a new fixture design ships with a release.
- `/debug-prod` — if a newly-created fixture is misbehaving.
