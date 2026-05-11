---
name: add-prisma-model
description: Add a new Prisma model with a forward migration, regenerate the client, and propagate types to backend + frontend. Also covers adding enum values to existing models.
argument-hint: "<model name> — <one-line purpose>"
---

# /add-prisma-model

Spawn `db-schema-eng` (`.claude/agents/db-schema-eng.md`).

Use this for: adding new models, adding fields to existing models, adding enum values, adding indexes. The flow is the same — every Prisma change goes through this skill.

## Authoritative knowledge to load

- `.claude/rules/prisma-flow.md` — the flow is enforced.
- `.claude/knowledge/prisma/schema-overview.md` — model graph + where new models belong.
- `.claude/knowledge/prisma/enums.md` — master enum table; check whether a new value belongs to an existing enum.
- `.claude/knowledge/prisma/migrations.md` — migration mechanics + recovery from failures.

## What the agent does

The flow follows `.claude/rules/prisma-flow.md` exactly:

1. **Edit `prisma/schema.prisma`**:
   - Add the model in the right cluster (products, builds, runs, fixtures, users, audit).
   - Field naming: camelCase.
   - Relations: explicit `@relation` blocks. Indexes (`@@index`) on `where`-clause hot paths.
   - Cascade-deletes only when the parent owns the child's entire lifetime.

2. **Generate the migration** (from inside the devcontainer):
   ```bash
   cd prisma && npx prisma migrate dev --name add_<model>_model
   ```
   Inspect the generated SQL in `prisma/migrations/<ts>_<name>/migration.sql` before committing. If the SQL surprises you, fix the schema and regenerate.

3. **Mirror the schema** (the SDK wheel ships its own copy):
   ```bash
   cp prisma/schema.prisma libs/python/database/schema.prisma
   ```

4. **Regenerate the Python client**:
   ```bash
   npx prisma generate
   ```

5. **Update knowledge** — touch each that applies:
   - **`.claude/knowledge/prisma/schema-overview.md`** — add the new entity under the right cluster (Products / Builds / Runs / Fixtures / Users / Audit). Note its relations.
   - **`.claude/knowledge/prisma/enums.md`** — if the model introduces a new enum or extends one. Update the master table.
   - **`.claude/knowledge/product-domains/<domain>.md`** — the domain file most affected (builds, validation, manufacturing, fixtures, products, users-rbac). Add the new model to its "Entities" table and explain its role.
   - **`.claude/knowledge/apps/backend/http-api.md`** — if the model gains its own `src/api/v2/<domain>/` module (often comes later, with `/add-endpoint`).

6. **Hand off**:
   - `http-api-eng` (via `/add-endpoint`) for any endpoints that read/write the model.
   - `frontend-eng` (via `/add-page`) for `models.ts` mirror + UI.

## Adding an enum value to an existing enum

Same flow, but step 1 is "add a value to an existing `enum` block in `schema.prisma`". The migration adds the value to the Postgres enum type. Step 5 is critical:

- **`enums.md`** — the new value goes in the master table.
- **Frontend `models.ts`** — the TypeScript enum mirror must add the value too. **The hand-sync is the #1 source of drift bugs.** Don't forget.
- Any backend code that `match`/`switch`es on the enum must handle the new value (Python won't catch this — it's a runtime concern). Audit the consumers.

## Don't

- Don't `prisma db push` to any environment. The init container runs `migrate deploy`.
- Don't edit a committed migration. Write a new forward migration.
- Don't skip the schema mirror — the SDK wheel needs it.

## Verify

- Dev DB applied the migration: log in to compose Postgres (`docker compose exec postgres psql -U concord`), `\d <table>`.
- Generated client compiles: `nx build http-api` succeeds.
- Knowledge updates landed: review the diff against the file list above.
- Frontend `models.ts` mirror is in sync (if API surface changed).
