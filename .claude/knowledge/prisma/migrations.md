# Prisma migrations — knowledge

How schema changes get from `prisma/schema.prisma` into a running database
in dev, staging, and production. Includes the http-api init-container
behavior that applies migrations on every pod start and how to recover
from a failed migration (Prisma error code `P3009`).

Refresh this file when: the migration application flow changes (e.g. the
init container's auto-resolve logic); the nx targets change; a new
recovery procedure is needed; the seed flow changes.

## Location

```
prisma/
├── schema.prisma                       # single source of truth
├── project.json                        # nx targets
├── .env / .env.example                 # DATABASE_URL for the prisma CLI
├── seed/                               # python seed module (dev only)
└── migrations/
    ├── migration_lock.toml             # provider = "postgresql"
    ├── 0001_init/migration.sql         # baseline
    └── <YYYYMMDDhhmmss>_<name>/migration.sql
```

Migration directory name format: `<timestamp>_<snake_case_name>/`.
Each contains a single `migration.sql` — hand-readable, sometimes
hand-edited after `prisma migrate dev` generates it (for data backfills,
explicit `UPDATE` steps, doc comments).

## Workflow at a glance

| Where | Command | What happens |
|---|---|---|
| **Dev (your machine, devcontainer)** | `nx run database:migrate` → `yarn prisma migrate dev` | Diffs `schema.prisma` against the shadow DB, generates a new migration directory, applies it, regenerates the client. |
| **Dev (post-pull)** | `nx run database:setup` | `generate-client` then `migrate` — what you run after pulling main with new migrations. |
| **Staging / Production** | http-api init container runs `prisma migrate deploy` on pod start. | Applies any pending migrations strictly (no diff against schema). |
| **Dev DB reset** | `nx run database:reset` → `yarn prisma migrate reset --force` | Drops + recreates the DB, applies all migrations, runs seed. |

## Nx targets (`prisma/project.json`)

| Target | Underlying command | Purpose |
|---|---|---|
| `generate-client` | `yarn prisma generate` | Regenerate `libs/python/database/`. |
| `migrate` | `yarn prisma migrate dev` | Dev-only: diff + create + apply + regenerate. |
| `migrate-deploy` | `yarn prisma migrate deploy` | Apply pending migrations strictly. Used by the init container. |
| `setup` | generate-client → migrate | Post-pull bootstrap. |
| `reset` | `yarn prisma migrate reset --force` | Wipe + reapply + seed. |
| `seed` | `python3 -m seed.main` | Dev seed (admin user, demo data). |
| `push` | `yarn prisma db push --skip-generate` | **Avoid** in normal flow — pushes schema without a migration. Only for throwaway local exploration. |
| `studio` | `yarn prisma studio` | Local DB browser. |

All targets run with `cwd: prisma/` and use the `DATABASE_URL` from
`prisma/.env`. In dev the URL points at the docker-compose postgres
container.

## The init-container flow (staging + production)

Defined in
`deploy/production/helm/concord/templates/http-api-deployment.yaml` as an
`initContainer` named **`migrate-and-seed`**. Runs before the http-api
container starts on every pod.

1. **`wait-for-db`** init container blocks until Postgres accepts TCP on
   the host/port parsed from `DATABASE_URL` (30 × 2s retries).
2. **`migrate-and-seed`** init container:
   - `cd /prisma` (the schema + migrations dir baked into the image).
   - Invokes the Prisma CLI directly via Node (bypasses
     `prisma-client-python`'s nodeenv to avoid needing internet at pod
     start):
     `node /app/prisma-cli/node_modules/prisma/build/index.js migrate deploy --schema /prisma/schema.prisma`
   - **P3009 auto-resolve.** If `migrate deploy` returns non-zero and the
     stderr/stdout contains `P3009` (failed migration from a prior crash),
     the script parses the failed migration name out of Prisma's message
     and runs `migrate resolve --rolled-back <name> --schema /prisma/schema.prisma`,
     then retries `migrate deploy`. This recovers from the common case
     where a previous pod started a migration and was killed mid-way.
   - Hard-exits non-zero on any other failure — the pod will not become
     ready until migrations succeed.
   - **Seed.** Only runs in development envs (key: a known CI admin API
     key is created). Production deployments skip the seed step.

Until the init container exits cleanly, the http-api pod stays in
`Init:0/2` and the rolling deploy doesn't progress.

## Adding a migration — full flow

1. **Edit `prisma/schema.prisma`** with the new model/column/enum
   value. Add `///` doc comments where lifecycle matters.
2. From inside the dev container at the repo root:
   `nx run database:migrate`. Prisma:
   - Diffs the schema against the shadow DB.
   - Asks you for a name — use snake_case and reflect *what changed*
     (`add_board_revision_snr_length`, `collapse_status_lockstate`).
   - Writes `prisma/migrations/<ts>_<name>/migration.sql`.
   - Applies it to your local DB.
   - Regenerates the Python client.
3. **Inspect the generated SQL.** Add a header comment block at the top
   describing what the migration does + *why* (the recent migrations in
   this repo all do this — match the voice). Hand-add backfill `UPDATE`s
   for any new `NOT NULL` column on populated tables. Drop columns in a
   later migration if the change is destructive.
4. **Test the up path.** `nx run database:reset` to wipe + replay all
   migrations from scratch; verify seed + your migration apply cleanly.
5. **Commit.** Include `prisma/schema.prisma`, the new migration
   directory, and any consumer code in the same commit. The pre-commit
   knowledge-freshness hook will require `prisma/schema-overview.md` (and
   sometimes `prisma/enums.md` or this file) in the same commit.
6. **Deploy.** Once merged to main, the next staging/production rollout
   includes the migration. The init container applies it on first pod
   start; no manual step.

## Recovery procedures

### `P3009 — migrate found failed migrations` in production

This happens when a previous pod crashed mid-migration. The init
container auto-resolves it as described above — usually you don't have to
do anything. If the auto-resolve itself fails (migration is partially
applied but `_prisma_migrations` row says "failed"), recover by hand:

```
# Exec into a pod that has the prisma CLI baked in (e.g. http-api after init):
kubectl exec -n production deploy/http-api -- bash
cd /prisma
node /app/prisma-cli/node_modules/prisma/build/index.js \
    migrate status --schema /prisma/schema.prisma
# Identify the failed migration name, then:
node /app/prisma-cli/node_modules/prisma/build/index.js \
    migrate resolve --rolled-back <migration_name> --schema /prisma/schema.prisma
# Re-run deploy:
node /app/prisma-cli/node_modules/prisma/build/index.js \
    migrate deploy --schema /prisma/schema.prisma
```

If the migration partially succeeded (some statements ran, some didn't),
either:

- Manually finish the SQL (`psql` into the DB and run the remaining
  statements) and then mark the migration applied with
  `migrate resolve --applied <name>`, or
- Drop the partial changes (`psql` to undo what ran) and mark as rolled
  back, letting `migrate deploy` reapply.

The pre-commit knowledge-freshness hook reminds you to update this file
if you add new recovery patterns — the rule is: if you've recovered from
something twice, document it.

### Rolling back a bad migration after it shipped

Prisma doesn't support down-migrations. The pattern is **roll forward**:

1. Write a new migration that undoes the bad change.
2. Deploy it via the normal flow (init container picks it up).
3. If the bad migration is still listed as applied in `_prisma_migrations`
   but you want to reapply some structure, you can `migrate resolve
   --rolled-back <name>` and ship a fresh migration, but this rewrites
   history — only do it before the bad change is on production.

### Reset the dev DB

```
nx run database:reset
```

Drops the local DB, reapplies all migrations from
`prisma/migrations/0001_init/` forward, then runs the seed. Safe in dev,
catastrophic in staging/production — the target is intentionally not
wired into any staging/production workflow.

### Drift detected: dev schema differs from migration history

`prisma migrate dev` will detect drift between the migrations folder and
the current DB state (someone ran `prisma db push`, or hand-edited the
DB, or pulled a migration that doesn't reflect what's in the DB). The
prompt offers to reset; in dev, accept it. Never do this in staging or
production.

## Multi-deploy patterns for risky changes

Some changes can't ship in one migration because rolling deploys leave
old + new pods running against the same DB for a window.

**Renaming a column or enum value**: ship in three stages.

1. Migration A: add the new column/value alongside the old. Code reads
   both, writes the new. Deploy.
2. Migration B: backfill the new column from the old. Deploy. Old pods
   are gone.
3. Migration C: drop the old column/value. Deploy.

**Splitting a column**: same pattern — add new columns, dual-write, then
drop.

**Tightening a `NULL` to `NOT NULL`**: add the column nullable, backfill,
flip to `NOT NULL`. The init container won't accept a non-null migration
on a column with `NULL` rows.

## Common failure modes

- **`Migration <name> failed to apply cleanly` in dev.** Usually a
  forgotten backfill for a `NOT NULL` column. Add an `UPDATE` step before
  the `ALTER COLUMN SET NOT NULL` line in the SQL, then rerun.
- **`P3009: migrate found failed migrations` after a pod crash.** Auto-
  resolved by the init container; if it doesn't recover, see the manual
  procedure above.
- **`P3018: migration failed to apply` on an `ALTER TYPE … ADD VALUE`.**
  Postgres doesn't allow this inside a transaction in some versions.
  Prisma now emits these as their own statement outside `BEGIN/COMMIT`,
  but if you hand-edit a migration that mixes `ADD VALUE` with other
  DDL, split them into separate `migration.sql` files (one per
  migration directory).
- **Init container loops on a migration that "succeeded" locally.**
  Your local DB has the migration row marked applied, but production
  doesn't, and the migration SQL fails on real data
  (e.g. `ALTER TABLE NOT NULL` on a column with NULL rows). Inspect
  staging Postgres, add the backfill to the migration SQL, push a fix.
- **Schema drift error after pulling main.** Someone ran `prisma db
  push` or hand-edited the dev DB. `nx run database:reset` to start
  clean.
- **`yarn prisma migrate dev` complains about a missing shadow DB.** The
  dev compose stack isn't up. Bring up Postgres first — see
  [`../workflows/local-dev.md`](../workflows/local-dev.md).
- **Seed fails in dev with `unique constraint violated` on a model that
  was just renamed.** The seed script (`prisma/seed/`) references the
  old model name. Update the seed in the same commit as the schema
  change.

## Related knowledge

- [`schema-overview.md`](schema-overview.md) — what the migrations are
  changing.
- [`enums.md`](enums.md) — enum-specific change patterns.
- [`../rules/prisma-flow.md`](../rules/prisma-flow.md) — overall
  schema-change policy.
- [`../apps/backend/http-api.md`](../apps/backend/http-api.md) — owns
  the init container.
- [`../deploy/`](../deploy/) — Helm chart, deployment lifecycle.
