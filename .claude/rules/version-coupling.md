# Version coupling — if you touch X, you MUST also Y

Concord ships multiple independently-versioned artifacts that have to
move together: the platform images, the corekinect Python wheel, the
corectl CLI wheel, the test-runner Docker image, the test packages
that test apps upload via `corectl test upload`, and the database
schema. A change in one frequently invalidates assumptions in another.

This file encodes the couplings. When you touch a path on the left,
you MUST also do the action on the right (or check that the listed
enforcement layer will do it for you). Each entry names **where the
enforcement lives** so a future agent can verify the contract is
satisfied or trace exactly why it broke.

This rule is auto-loaded into every concord session. It is short on
purpose — the full incident reasoning lives in
[`workflows/version-skew.md`](../knowledge/workflows/version-skew.md).

## Quick reference

```
libs/python/corekinect/   →  test-runner image rebuild, test apps re-upload (if framework constraint changed)
libs/protocols/mtib/      →  test-runner rebuild, mtib-server image rebuild
tools/corectl/            →  wheel publish (per-env pypi), test-runner rebuild, dev hosts run `corectl upgrade`
prisma/schema.prisma      →  forward migration, Python client regen, frontend models.ts mirror, knowledge files
deploy/{helm,ctl-sh,...}  →  all-three-envs rule (dev compose, staging values, production values)
```

## The contracts

### 1. `libs/python/corekinect/**`

**You MUST:**

1. **Rebuild the test-runner image.** The runner Docker image bakes
   corekinect in at build time (`COPY libs/python /libs/python`). A
   wheel-only republish leaves runner pods on the old version.
2. **Bump the corekinect wheel version** if the change is public-API.
   Wheel publishes happen via `nx run corekinect:push -c <env>` and
   are gated by the corekinect-version-bump check in
   `scripts/release_gate.py`.
3. **Re-upload affected test apps** IF the test app's
   `package.framework` constraint in `concord.yaml` would no longer
   satisfy the new corekinect version. Most active test packages
   (e.g., sigma5_manufacturing's `dev-99490cd3-1779845120`) declare
   permissive constraints like `">=0.9.0"` and don't need re-upload.

**Enforcement layers (Phase D, branch `chore/enforce-runner-corekinect-coupling`):**

- **Layer 1** — `deploy/runner/project.json` `implicitDependencies`
  lists `corekinect`. Nx affected-graph marks the runner dirty on any
  corekinect change. Code: [`deploy/runner/project.json`](../../deploy/runner/project.json).
  Tests: [`deploy/runner/tests/test_project_dependencies.py`](../../deploy/runner/tests/test_project_dependencies.py).
- **Layer 2** — `deploy/ctl.sh` `_check_runner_corekinect_freshness`
  function refuses `nx update platform` if the runner image's baked
  `COREKINECT_GIT_SHA` differs from `_corekinect_sha`. Escape:
  `CONCORD_FORCE_STALE_RUNNER=1` (loud-warn).
- **Layer 3** — `scripts/release-gates/check-runner-affected.sh` runs
  as Phase 1.5 of `/concord-release`. Refuses to cut a release that
  touches corekinect without `test-runner` in the affected set.
  Escape: `CONCORD_FORCE_NO_RUNNER_REBUILD=1`.
- **Layer 4** — `deploy/runner/check_framework_constraint.py` runs in
  the runner pod between extract and pytest. PEP 440 specifier check
  of `package.framework` vs `corekinect.__version__`. Escape:
  `CONCORD_FORCE_STALE_PACKAGE=1`.

**Knowledge:** [`deploy/runner.md`](../knowledge/deploy/runner.md) has the full design.

**See also:** [`workflows/version-skew.md` case study #3](../knowledge/workflows/version-skew.md)
(stale test package on new runner).

### 2. `libs/protocols/mtib/**`

**You MUST:**

1. **Rebuild the test-runner image.** Corekinect imports the generated
   mtib gRPC stubs at runtime. Stale stubs → AttributeError or
   silently-incompatible serialization.
2. **Rebuild the mtib-server image** (`apps/edge/mtib-server`). The
   server-side gRPC handlers compile against the same protos.
3. **Regenerate protocol code** if the `.proto` schema changed: run
   the relevant `nx run protocols:create` target (see
   [`libs/protocols.md`](../knowledge/libs/protocols.md)).
4. **Confirm wire compatibility** between the new mtib-server pods
   and any older corekinect clients still running in test packages.
   Breaking proto changes need a coordinated rollout (deploy new
   server first, then update clients).

**Enforcement layers:**

- Layer 1 of runner enforcement (implicitDependencies lists
  `protocols`). Nx marks both `test-runner` and `mtib-server` as
  affected on any protocol change.
- No standalone mtib-server freshness gate today — if proto wire
  changes silently, you find out at runtime. (Improvement candidate.)

**Knowledge:** [`libs/protocols.md`](../knowledge/libs/protocols.md),
[`apps/edge/mtib-server.md`](../knowledge/apps/edge/mtib-server.md).

### 3. `tools/corectl/**`

**You MUST:**

1. **Bump the corectl wheel version** if the change is public-API.
2. **Publish to staging pypi**, then **publish to production pypi**.
   Done by `nx run corectl:push -c <env>`. The release gate at
   `scripts/release_gate.py` enforces a corectl version bump if any
   `tools/corectl/src/**` file changed in the release range.
3. **Rebuild the test-runner image.** corectl ships inside the runner
   image at `/app/corectl` and is invoked by some flows (e.g.,
   `corectl test refresh-framework`).
4. **Notify dev hosts** that `corectl upgrade` is recommended. This is
   surfaced by corectl's own `--version` self-check against pypi.

**Enforcement layers:**

- Same Layer 1 / Layer 3 as corekinect (`corectl` in
  `implicitDependencies`).
- Wheel publish step is gated by Phase 4 (Version bump) and Phase 9.2
  (Build + publish wheels) of `/concord-release`.

**Knowledge:** [`tools/corectl.md`](../knowledge/tools/corectl.md).

### 4. `prisma/schema.prisma`

**You MUST:**

1. **Write a forward migration**:
   `cd prisma && npx prisma migrate dev --name <descriptive-name>`.
   Migrations are forward-only — never edit a committed migration.
2. **Regenerate the Python client** (`npx prisma generate`).
3. **Mirror the schema** to `libs/python/database/schema.prisma`.
4. **Update the frontend type mirror** at
   `apps/frontend/app/src/lib/types/models.ts` by hand.
5. **Update knowledge files**:
   - [`prisma/schema-overview.md`](../knowledge/prisma/schema-overview.md)
     for new entities.
   - [`prisma/enums.md`](../knowledge/prisma/enums.md) for enum values.
   - The product-domain file the entity belongs to.

**Enforcement layers:**

- The full sequence lives in [`rules/prisma-flow.md`](prisma-flow.md).
- Migrations get applied automatically by the http-api's
  `migrate-and-seed` init container on deploy. A bad migration → pod
  stuck `Init:CrashLoopBackOff`.
- The frontend `models.ts` mirror has NO automated enforcement —
  catch in code review.

**Knowledge:** [`prisma/schema-overview.md`](../knowledge/prisma/schema-overview.md).

### 5. `deploy/development/docker-compose.yaml`, `deploy/production/helm/values-{staging,production}.yaml`

**You MUST:**

Touch all three files together. Any env var, port, replica count, or
helm value that exists in one **must** exist in all three with a value
appropriate for that environment. The CI helm-values-completeness
check (added in v0.9.18) catches some of these, but the discipline
must hold at the source.

**Enforcement layers:**

- [`rules/all-three-envs.md`](all-three-envs.md) (full rationale).
- CI check (helm template render with each values file).
- No git-time hook — by-eye review.

**Knowledge:** [`deploy/helm.md`](../knowledge/deploy/helm.md),
[`deploy/secrets.md`](../knowledge/deploy/secrets.md).

### 6. `apps/frontend/app/src/lib/types/models.ts`

This is a **type mirror** of the Prisma schema. If the schema changes
and `models.ts` doesn't, the frontend will silently misinterpret API
responses (missing fields show as `undefined`; renamed fields look
like deletions). See contract #4 above for the trigger; this entry
is here for symmetry — if you're touching `models.ts`, also confirm
the schema change is real and has its migration.

### 7. The skill files in `.claude/skills/`

If you change a skill that other skills or agents reference, search
for callers:

```bash
grep -rn '\<skill-name\>' .claude/
```

A renamed skill needs to be updated everywhere — there's no compile-time check.

## When this rule fires

The session-load behavior is automatic (auto-loaded with every
session). The contracts above are reference material. The mechanism
that *enforces* a contract is the named enforcement layer — that's
where a violation gets refused at the gate.

If you discover a coupling that isn't listed here, add it in the same
commit as the work that taught you about it. The same way
`update-knowledge-on-change.md` keeps the knowledge files honest, this
file keeps the coupling map honest.

## Related

- [`workflows/version-skew.md`](../knowledge/workflows/version-skew.md) — case studies of what went wrong when these contracts were violated.
- [`deploy/runner.md`](../knowledge/deploy/runner.md) — Phase D's four-layer enforcement of contracts #1-3.
- [`prisma-flow.md`](prisma-flow.md) — full prisma sequence.
- [`all-three-envs.md`](all-three-envs.md) — three-environment discipline.
- [`update-knowledge-on-change.md`](update-knowledge-on-change.md) — the parent rule that says "knowledge updates in the same commit as code."
