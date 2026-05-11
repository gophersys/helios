# Prisma flow

The database schema is canonical in `prisma/schema.prisma`. Any change touches a fixed sequence.

## When you change `schema.prisma`

1. **Edit** `prisma/schema.prisma`. Add a model, field, relation, or enum value.
2. **Create migration**: from inside the devcontainer, `cd prisma && npx prisma migrate dev --name <descriptive-name>`. This generates `prisma/migrations/<timestamp>_<name>/migration.sql` and applies it to your local Postgres.
3. **Regenerate the Python client**: `npx prisma generate` (runs automatically as part of `nx build http-api` and friends, but if you're iterating, run it explicitly).
4. **Mirror the schema** to `libs/python/database/schema.prisma`. The Python wheel ships with its own copy used for client generation in CI; they must match.
5. **Update the frontend type mirror** at `apps/frontend/app/src/lib/types/models.ts`. Backend has no codegen to the frontend — types are synced by hand.
6. **Update knowledge**: `.claude/knowledge/prisma/schema-overview.md` for new entities, `.claude/knowledge/prisma/enums.md` for new enum values, plus any product-domain file the entity belongs to.

## Migrations are forward-only

- Don't edit a migration once it's committed. Write a new one.
- Don't `prisma db push` against staging or production — it bypasses migration history. `migrate deploy` is what the K8s init container runs.
- For rollback: write a forward migration that reverses the change. Down-migrations aren't supported in this codebase.

## Deploy-time migration

Every production/staging deploy runs `prisma migrate deploy` in an init container before `concord-http-api` starts. See `deploy/production/helm/concord/templates/http-api-deployment.yaml`.

If migrations fail, the pod stays in `Init:CrashLoopBackOff`. Inspect with:

```bash
kubectl -n <env> logs <pod> -c migrate-and-seed
```

The most common failure is `P3009 — migration failed to apply cleanly`. Fix: read the error, hand-write a corrective forward migration, redeploy.

## Resetting the local DB

```bash
nx stop platform
docker volume rm development-postgres_data
nx start platform   # Postgres comes up empty; init container applies all migrations
```

## What gets seeded

A seed script under `prisma/seed.py` (or referenced from `package.json`) populates dev with a baseline product, admin user, and fixture. It runs only in development — `migrate-and-seed` skips it in staging/prod.

## Enums

Defined exclusively in `schema.prisma`. Use them in Python via `from database import enums`. **Never** type enum values as raw strings (`"ACTIVE"`); always reference the constant (`enums.TestRunStatus.ACTIVE`). When you add a value:

1. Add to `schema.prisma` enum block + migration.
2. Use the new constant in code.
3. Add a TypeScript mirror in `apps/frontend/app/src/lib/types/models.ts` if the value reaches the API surface.
4. Update `.claude/knowledge/prisma/enums.md`.

The frontend type mirror is the only place TS and Python can drift. Catch it in code review.

## Bulk-edit transactions

Multi-step writes that must be atomic use Prisma's transaction API in Python:

```python
async with db.tx() as tx:
    await tx.product.update(...)
    await tx.audit_log.create(...)
```

If you find yourself writing two independent `db.x.update(...)` calls that both need to succeed or both roll back, wrap them.
