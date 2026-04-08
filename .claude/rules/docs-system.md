# Documentation System

Concord uses a feature-first documentation structure served via Zensical (Material for MkDocs). Documents are organized by **product feature area**, not by document type. Each top-level section becomes a tab in the UI.

## Structure

```
docs/
├── index.md                     Home — landing page with role routing
├── products/                    Products — hardware, repos, build matrix, recipes, stage config
├── builds/                      Builds — triggering, config, CI, monitoring, artifacts
├── validation/                  Validation — queue, execution, results, real-time, stages
├── manufacturing/               Manufacturing — config, fixtures, sessions, POST, results
├── fixtures/                    Fixtures — designs, instances, slots, MTIB deployment
├── administration/              Administration — setup, users, permissions, API keys, ops
├── reference/                   Reference — Python SDK, REST API, corectl, error codes
│   └── python-sdk/              SDK classes (mkdocstrings auto-generated)
├── platform/                    Platform — architecture, build system, validation system
├── assets/js/                   Client-side scripts (role filter, external links)
├── _internal/                   EXCLUDED — engineering-only (research, journals, vision)
└── _archive/                    EXCLUDED — superseded plans and docs
```

`_internal/` and `_archive/` are excluded from the build via `exclude_docs` in mkdocs.yml.

## Where Does a New Document Go?

| Question | Section | Example |
|----------|---------|---------|
| How do I use feature X? | `{feature}/` | products/creating-products.md |
| What's the API/SDK for X? | `reference/` | reference/rest-api.md |
| How is X designed internally? | `platform/` | platform/build-system/build-service.md |
| How do I set up the platform? | `administration/` | administration/initial-setup.md |

## Role Visibility

Every page has a `min_role` frontmatter field. The role-filter.js hides pages above the user's role level.

| min_role | Who sees it |
|----------|-------------|
| OPERATOR | Everyone |
| DEVELOPER | Developer, Maintainer, Admin |
| MAINTAINER | Maintainer, Admin |
| ADMIN | Admin only |

## Naming Conventions

- **Filenames**: lowercase kebab-case, descriptive (`build-matrix.md` not `04-matrix.md`)
- **Index files**: every directory has an `index.md`
- **Frontmatter**: every page must have `min_role` in YAML frontmatter

## Cross-References

Use relative paths from the current file:

```markdown
See [Build Artifacts](../builds/artifacts.md) for download details.
```

## Zensical / MkDocs

Config lives at the repo root: `mkdocs.yml`. Theme: Material with slate palette, navigation tabs.

```bash
npx nx serve docs      # http://localhost:4000 (dev, live reload)
npx nx run docs:build  # static site in apps/frontend/docs/site/
```

## Deployment

| Environment | URL | How |
|-------------|-----|-----|
| Development | `localhost:4000` | `npx nx serve docs` |
| Staging | `docs.staging.concord.local` | `nx update platform -c staging` |
| Production | `docs.concord.local` | `nx update platform -c production` |

Auth: the main app sets a `concord-auth` cookie on the parent domain. The docs JS reads this cookie for auth and role filtering. No cookie → redirect to `/login`.

## Rules

1. **Every new doc gets a nav entry.** Update `mkdocs.yml` nav and the parent `index.md`.
2. **Every page gets `min_role` frontmatter.** No exceptions.
3. **Use the product voice.** See `.claude/rules/docs-voice.md`. No AI patterns.
4. **One source of truth.** Don't duplicate — link to the authority.
5. **Archive, don't delete.** Move superseded docs to `_archive/`.
6. **Cross-link liberally.** Every page should link to related pages.
