# Update knowledge on change

**If you change code, you update the matching `.claude/knowledge/` file in the same commit.**

This is the rule that keeps `.claude/` from rotting. It's enforced by `.claude/hooks/commit-msg-knowledge-freshness.sh` — the commit will be rejected if a watched code path is touched without the corresponding knowledge update.

## The escape hatch

If the change genuinely does not alter behavior, shape, public surface, or architecture — for example a typo, a log message tweak, formatting, a version bump, a dependency lockfile sync — add `[no-arch-change]` to your commit message and the hook will let the commit through.

Use it sparingly. The default is to update the knowledge file.

## What counts as "the matching knowledge file"

The hook reads `.claude/hooks/knowledge-map.txt`, a two-column file mapping code-path prefixes to knowledge files. Example rows:

```
apps/backend/http-api/        .claude/knowledge/apps/backend/http-api.md
apps/backend/build-service/   .claude/knowledge/apps/backend/build-service.md
apps/frontend/app/            .claude/knowledge/apps/frontend/app.md
apps/edge/mtib-server/        .claude/knowledge/apps/edge/mtib-server.md
libs/python/                  .claude/knowledge/libs/python-corekinect.md
libs/protocols/               .claude/knowledge/libs/protocols.md
prisma/schema.prisma          .claude/knowledge/prisma/schema-overview.md
prisma/migrations/            .claude/knowledge/prisma/migrations.md
deploy/                       .claude/knowledge/deploy/
.ci/                          .claude/knowledge/ci/pipelines.md
```

The hook walks each staged file and matches the longest prefix. If a knowledge file is matched and isn't also in the staged file set, the commit fails with a message naming both files.

For `deploy/` the map points at a directory — the hook accepts any file under `.claude/knowledge/deploy/` as a valid companion update.

When you add a new code path that deserves its own knowledge file, you also add a row to `knowledge-map.txt` (and write the knowledge file). Both in the same commit.

## What a "knowledge update" looks like

It is not "touch the file with a whitespace edit." It is a real edit that reflects what changed:

- Added a new route module under `apps/backend/http-api/src/api/v2/widgets/`? The `apps/backend/http-api.md` knowledge file lists the new module under "Internal structure" and (if it introduces a new pattern) under "Key patterns".
- Added a new Prisma model? `prisma/schema-overview.md` gets the new entity under the right cluster, and if the model introduces a new enum, `prisma/enums.md` gets it too.
- Added a new env var? `deploy/secrets.md` (or `deploy/helm.md` if it's a plain config) gets the row.
- Renamed a function only used inside one app, no public API impact? Probably qualifies for `[no-arch-change]`.

If in doubt: ask "would a future Claude session reading the knowledge file get a wrong picture if I don't update it?" If yes, update it.

## Reviewing your own bypass

Before adding `[no-arch-change]`, re-read the diff. If you are about to type the marker out of frustration rather than because the change is truly cosmetic, stop and update the knowledge file. The hook can be appeased, but the system only works if you mean it.
