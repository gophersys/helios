# docs (Concord documentation site) — knowledge

MkDocs Material static documentation site served at `docs.<host>`. Its single most important responsibility is to render the markdown under `/docs/` into a navigable site with role-gated content — Operator, Developer, Maintainer, Admin tiers all see different subsets of the navigation based on a manifest the build emits.

Refresh this file when: the build tool changes, the role-filter mechanism changes, the navigation top-level changes shape, or a new MkDocs plugin/hook is added.

## Location

- Build assets: `apps/frontend/docs/`
- Site config: `mkdocs.yml` (repo root)
- Docs source: `docs/` (repo root)
- Hooks: `apps/frontend/docs/hooks/role_filter.py`, `apps/frontend/docs/hooks/generate_role_manifest.py`
- Plugin (legacy mkdocs plugin form): `apps/frontend/docs/plugins/concord_role_filter.py`
- Tests: none — the build is the test (a broken markdown or nav entry fails the build).

## Responsibilities

Owns:

- Rendering `/docs/*.md` to a static site under `apps/frontend/docs/site/`.
- Generating `role-manifest.json` from page frontmatter so the client can hide nav entries above a user's role.
- The Dockerfile + nginx config that serves the static site in K8s.
- Code reference embedding for `libs/python`, `libs/protocols`, `libs/` via `mkdocstrings`.

Does NOT own:

- Authentication. The site is publicly servable; role filtering is cosmetic. The shared cookie (`concord-auth`) set by the main app on the parent domain is what the client-side filter reads, but a determined visitor can fetch any page directly.
- The doc content itself — that lives at `docs/` at the repo root and is owned by whoever wrote the relevant feature.
- API documentation generation for the HTTP API — that's a separate concern (currently hand-written under `docs/reference/rest-api.md`).

## Internal structure

```
apps/frontend/docs/
├── hooks/
│   ├── role_filter.py            # MkDocs hook — runs during `mkdocs build`
│   └── generate_role_manifest.py # Standalone script — runs after `zensical build`
├── plugins/
│   └── concord_role_filter.py    # Legacy plugin form of role_filter
├── deploy/
│   ├── Dockerfile                # nginx + built site
│   └── nginx.conf
├── requirements.txt              # mkdocs-material, mkdocstrings, etc.
├── package.json                  # placeholder so nx picks it up
└── project.json                  # nx targets: serve/build/containerize/push/deploy

docs/                             # actual content (repo root, NOT under this app)
├── index.md
├── products/, builds/, validation/, manufacturing/, fixtures/
├── administration/, reference/, platform/
├── _internal/                    # excluded from build
└── _archive/                     # excluded from build

mkdocs.yml                        # repo root — site config

apps/frontend/docs/site/          # build output (gitignored)
```

## Key patterns

### MkDocs config

`mkdocs.yml` at the repo root drives everything:

- `docs_dir: docs` — content lives at the repo root, not under `apps/frontend/docs/`.
- `site_dir: apps/frontend/docs/site` — output is written into this app's directory so the Dockerfile can copy it.
- `exclude_docs: _internal/ _archive/` — these directories are never published.
- Theme: `material` with `slate` (dark) primary and a light toggle. Features include instant navigation, sticky tabs, sectioned indexes, suggest search, and code-copy.
- Markdown extensions: tables, admonitions, mermaid via `pymdownx.superfences`, syntax-highlight, tabbed content, attr lists.
- Hooks: `apps/frontend/docs/hooks/role_filter.py` runs on every page.
- Plugins: built-in `search`, plus `mkdocstrings` configured with `paths: [libs/python, libs/protocols, libs]` so Python docstrings can be embedded into pages with `::: module.path`.
- `nav:` is explicit — every top-level section (Products, Builds, Validation, Manufacturing, Fixtures, Administration, Reference, Platform) is hand-curated. New pages must be added here to appear.

### Role-manifest hook

Pages opt into role gating by adding YAML frontmatter:

```markdown
---
min_role: MAINTAINER
---

# Page title
```

The build runs `role_filter.py` as an MkDocs `on_page_markdown` hook. For each page with a recognized `min_role`, it records:

```json
{
  "/administration/users-and-roles/": { "min_role": "MAINTAINER", "min_level": 3 }
}
```

…and on `on_post_build` writes the manifest to `apps/frontend/docs/site/role-manifest.json` along with the hierarchy table `{OPERATOR:1, DEVELOPER:2, MAINTAINER:3, ADMIN:4}`.

Client-side: `extra_javascript` includes `assets/js/role-filter.js` (lives under `docs/assets/js/`) which reads the cookie `concord-auth` set by the main app, decodes the JWT to get the user's role, fetches `/role-manifest.json`, and hides nav entries whose `min_level` exceeds the user's level. Direct URL access is not blocked — this is a presentation filter.

Two implementations of the manifest writer exist:

- `role_filter.py` — the MkDocs hook used in the live build via `hooks:` in `mkdocs.yml`.
- `generate_role_manifest.py` — a standalone CLI script invoked by `nx serve docs` and `nx build docs -c development` after a Zensical build, because that build path doesn't run MkDocs hooks. It scans `docs/` for `---\nmin_role: …\n---` frontmatter via regex and writes the same JSON shape.
- `concord_role_filter.py` (in `plugins/`) — a legacy `BasePlugin` form of the same logic. Not currently wired; kept for reference.

When you change the role-filter logic, change **all three** in lockstep or the dev and prod paths drift.

### Build runner: Zensical

The active dev/build target uses `zensical` (a wrapper around MkDocs Material) rather than vanilla `mkdocs`. See `project.json` `serve`/`build` targets. It runs with `PYTHONPATH=libs/python:libs:libs/protocols` so `mkdocstrings` can import the Python SDK and the protocols package directly from source.

### Embedding Python docstrings

Reference pages like `docs/reference/python-sdk/test-framework/context.md` use `mkdocstrings`:

```markdown
::: corekinect.test.context.TestContext
    options:
      members: [setup, teardown, ...]
```

This pulls docstrings from the live source tree at build time. Changes to docstrings in `libs/python/corekinect/...` are reflected on the next docs deploy. Keep the Google docstring style (`Args:`, `Returns:`, `Raises:`) as configured in `mkdocs.yml`.

## External dependencies

| Concern | Where |
|---|---|
| Source content | `/docs/` at the repo root. |
| Library docstrings | `libs/python/`, `libs/protocols/`, `libs/` (mkdocstrings `paths:`). |
| Auth cookie | `concord-auth` on the parent domain, set by the main `app` (`apps/frontend/app/src/lib/api.ts`). The docs site is at `docs.<host>` so the parent-domain cookie is readable. |
| Hosting | nginx in `apps/frontend/docs/deploy/Dockerfile`. K8s exposes via the `concord-docs` ingress at `docs.<host>`. |
| Build deps | `apps/frontend/docs/requirements.txt`: `mkdocs-material`, `mkdocstrings[python]`, `mkdocs-awesome-pages-plugin`, plus a handful of runtime deps (`grpcio`, `protobuf`, `minio`, `sqlalchemy`, …) so docstring imports of platform code don't fail. |

No runtime backend dependency — the site is fully static once built. Role filtering is the only thing that touches another service (it reads the JWT cookie issued by `http-api`).

## How to add common things

### Add a new doc page

1. Create the markdown under `docs/<section>/<slug>.md`.
2. Optionally add `---\nmin_role: <ROLE>\n---` frontmatter for role-gating.
3. Add the page to `mkdocs.yml` under the matching `nav:` section — it will not appear otherwise.
4. Cross-link from neighbouring pages where it fits naturally.
5. `nx serve docs` (port 4000) to preview; verify the role filter behaves by clearing the `concord-auth` cookie and reloading.

### Change role visibility for a page

Edit the page's frontmatter `min_role:` field. Rebuild — the manifest regenerates from frontmatter on every build. No code change needed.

### Add a new role tier

This is a cross-cutting change:

1. Update `ROLE_HIERARCHY` in **all three** of `hooks/role_filter.py`, `hooks/generate_role_manifest.py`, `plugins/concord_role_filter.py`.
2. Update the matching enum in `prisma/schema.prisma` and follow the Prisma flow (see [`rules/prisma-flow.md`](../../../rules/prisma-flow.md)).
3. Update `apps/frontend/app/src/lib/types/models.ts` and any permission tables.
4. Update the role-filter JS asset (`docs/assets/js/role-filter.js`) to handle the new level.
5. Update this knowledge file plus the glossary.

### Embed Python API docs

Use `mkdocstrings`:

````markdown
## My class

::: corekinect.<module>.<Class>
    options:
      heading_level: 3
      show_source: false
````

Make sure the symbol is importable with `PYTHONPATH=libs/python:libs:libs/protocols` — otherwise the build fails.

## Common failure modes

- **Role manifest is missing pages.** Two causes: the page lacks `min_role` frontmatter (intended — unrestricted), or the build path didn't run the manifest writer. The `nx serve docs` and `nx build docs -c development` targets invoke `generate_role_manifest.py` explicitly because Zensical doesn't run MkDocs hooks. The staging/production builds use the MkDocs path, where `role_filter.py` runs as a hook. If you added a new build path, wire the manifest writer.
- **`mkdocstrings` ImportError on build.** A page references a symbol that requires an import the runtime can't satisfy (missing dep in `requirements.txt`, or path-shadowing). The build fails with the import traceback. Fix: add the missing dep, or guard the import in the source module.
- **Page in `nav:` but file missing.** `mkdocs build --strict` fails. The CI build runs strict; fix by either removing the nav entry or creating the page.
- **Role filter not hiding nav after deploy.** The cookie isn't readable on the docs subdomain — either the user logged in over plain HTTP and the cookie was set without `Secure`, or the parent-domain logic in `apps/frontend/app/src/lib/api.ts#getParentDomain()` computed the wrong domain. Inspect `document.cookie` on the docs page; if `concord-auth` is absent, the issue is at the app side.
- **Stale `role-manifest.json` after content change.** Browser cache. The manifest is fetched without versioning. Hard-refresh or set a cache-bust in the role-filter JS asset.

## Related knowledge

- [`apps/frontend/app.md`](app.md) — the main app that sets the shared auth cookie consumed by this site.
- [`architecture.md`](../../architecture.md) — where docs sits in the platform diagram.
- [`rules/auth-defaults.md`](../../../rules/auth-defaults.md) — how the JWT is issued and what it contains.
- [`rules/prisma-flow.md`](../../../rules/prisma-flow.md) — needed when adding/removing Role enum values.
- [`deploy/helm.md`](../../deploy/helm.md) — the `concord-docs` deployment + ingress.
