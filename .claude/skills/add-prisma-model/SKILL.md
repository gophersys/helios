---
name: add-prisma-model
description: Add a new Prisma model with a forward migration, regenerate the client, and propagate types to backend + frontend.
argument-hint: "<model name> — <one-line purpose>"
---

# /add-prisma-model

Spawn `db-schema-eng` (`.claude/agents/db-schema-eng.md`).

## What the agent does

The flow follows `.claude/rules/prisma-flow.md` exactly:

1. **Edit `prisma/schema.prisma`**:
   - Add the model in the right cluster (products, builds, runs, fixtures, users, audit).
   - Field naming: camelCase.
   - Relations: explicit `@relation` blocks. Indexes (`@@index`) on `where`-clause hot paths.
   - Cascade-deletes only when the parent owns the child's entire lifetime.

2. **Generate the migration**:
   ```bash
   cd prisma && npx prisma migrate dev --name add_<model>_model
   ```
   Inspect the generated SQL in `prisma/migrations/<ts>_<name>/migration.sql` before committing.

3. **Mirror schema**:
   ```bash
   cp prisma/schema.prisma libs/python/database/schema.prisma
   ```

4. **Regenerate the client**:
   ```bash
   npx prisma generate
   ```

5. **Update knowledge**:
   - `.claude/knowledge/prisma/schema-overview.md` — add the new entity under the right cluster.
   - `.claude/knowledge/prisma/enums.md` — if the model introduces enums.
   - `.claude/knowledge/product-domains/<domain>.md` — if the model belongs to a domain.

6. **Hand off**:
   - `http-api-eng` for any endpoints that read/write the model.
   - `frontend-eng` for `models.ts` and UI.

## Don't

- Don't `prisma db push` to any environment. The init container runs `migrate deploy`.
- Don't edit a committed migration. Write a new forward migration.
- Don't skip the schema mirror — the SDK wheel needs it.

## Verify

- Dev DB applied the migration: log in to compose Postgres, `\d <table>`.
- Generated client compiles: `nx build http-api` succeeds.
- Knowledge updates landed: review the diff.
