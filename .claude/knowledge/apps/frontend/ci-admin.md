# ci-admin — knowledge

A self-contained SvelteKit dashboard for the CoreKinect **CI platform** — the separate Helm release in the `devops` namespace that runs nightly and weekly E2E pipelines against the main repos. It is **not** part of the Concord platform service mesh: it has its own SQLite store, its own server-side SvelteKit routes (no `http-api` dependency), and its own deployment image. Its single most important responsibility is to ingest pipeline run results via POST and render them as queryable runs, trends, and file-level hotspots.

Refresh this file when: a route is added/removed, the SQLite schema changes, the ingest contract changes, or it grows a dependency on the main platform (it currently has none).

## Location

- Code: `apps/frontend/ci-admin/`
- Entry point: `apps/frontend/ci-admin/src/routes/+layout.svelte` (sidebar + main shell)
- DB layer: `apps/frontend/ci-admin/src/lib/server/db.ts` (better-sqlite3, file at `$CI_DATA_DIR/ci.db`)
- API routes: `apps/frontend/ci-admin/src/routes/api/{runs,trends,hotspots}/+server.ts`
- Tests: none currently

## Responsibilities

Owns:

- Ingesting pipeline results via `POST /api/runs` (called by CI pipeline finalize steps).
- Persisting runs, stages, and findings in a local SQLite database with WAL mode.
- Rendering an Overview, a runs list, a per-run detail, a trends view, and a file-hotspots view.
- Computing roll-ups: pass rate, total issues, total cost, severity distribution, rising/falling trend direction.

Does NOT own:

- Any concept from the main Concord platform: no Products, BuildRuns, TestRuns, Fixtures, Users, Permissions, AuditLog. None of those names appear here.
- Authentication. The dashboard is publicly servable inside the `devops` namespace ingress; access is controlled at the network layer (it's not on the public internet).
- Reading from MinIO, K8s, or the Postgres concord DB. It does not call any other service.
- Runtime scheduling of CI runs — that's the CI platform's own Helm chart, separate from this dashboard.

## Internal structure

```
apps/frontend/ci-admin/
├── src/
│   ├── app.css, app.html
│   ├── lib/
│   │   ├── types.ts              # frontend-only types
│   │   ├── stage-colors.ts
│   │   └── server/
│   │       └── db.ts             # better-sqlite3 + migrate() + queries
│   └── routes/
│       ├── +layout.svelte        # sidebar nav: Overview / Runs / Trends / Hotspots
│       ├── +page.svelte          # Overview
│       ├── +page.server.ts       # load(): listRuns({limit:10}) + getTrends(7)
│       ├── runs/
│       │   ├── +page.svelte
│       │   ├── +page.server.ts
│       │   └── [id]/
│       │       ├── +page.svelte
│       │       └── +page.server.ts
│       ├── trends/
│       │   ├── +page.svelte
│       │   └── +page.server.ts
│       ├── hotspots/
│       │   ├── +page.svelte
│       │   └── +page.server.ts
│       └── api/
│           ├── runs/+server.ts        # GET list, POST create
│           ├── runs/[id]/+server.ts   # GET detail
│           ├── trends/+server.ts
│           └── hotspots/+server.ts
├── deploy/
│   └── Dockerfile                # node:22-alpine, builds via npm, serves via node build/index.js
├── svelte.config.js              # adapter-node (this one is NOT static)
├── vite.config.js, tsconfig.json
├── package.json                  # deps: better-sqlite3, lucide-svelte, minio, uuid
└── project.json                  # nx targets: serve (port 4300), build, check
```

## Key patterns

### Why it's independent

The dashboard runs in the `devops` namespace alongside the CI platform Helm release; it has no DNS or network access requirement to the Concord backend. It exists as a separate app because:

- **Different audience.** CI run health is a maintainers-and-DevOps concern, not a platform-user concern. Mixing it into the main app would dilute the navigation.
- **Different write path.** Ingest is a server-to-server POST from CI pipeline steps. Routing that through the main `http-api` would require a permission model that doesn't otherwise apply.
- **Different storage shape.** Runs/stages/findings are flat, append-mostly, queried by date and file. SQLite + WAL is sufficient and avoids a Postgres dependency.
- **Different release cadence.** The CI dashboard ships with the CI platform, not the Concord platform.

`adapter-node` (not `adapter-static`) is used so server-side load functions can read SQLite directly.

### SQLite schema

`migrate()` in `src/lib/server/db.ts` creates three tables on first open:

```sql
runs (
  id TEXT PRIMARY KEY, pipeline TEXT, verdict TEXT, branch TEXT, commit_sha TEXT,
  duration_seconds INT, total_cost REAL, total_issues INT, severity TEXT,
  created_at TEXT DEFAULT (datetime('now'))
)

stages (
  id TEXT PRIMARY KEY, run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
  name TEXT, verdict TEXT, severity TEXT, issues INT, cost REAL, model TEXT,
  duration_seconds INT, summary TEXT, logs TEXT, created_at TEXT
)

findings (
  id TEXT PRIMARY KEY, run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
  stage TEXT, file TEXT, severity TEXT, message TEXT, created_at TEXT
)
```

Indexes on `stages.run_id`, `findings.run_id`, `runs.created_at DESC`, `findings.file`. `journal_mode = WAL` and `foreign_keys = ON` are set on open. The DB path is `$CI_DATA_DIR/ci.db` (defaults to `./data/ci.db` when unset). In K8s this maps to a PVC mounted at `/data`.

### Ingest contract (`POST /api/runs`)

Body shape (see `CreateRunInput` in `db.ts`):

```json
{
  "pipeline": "nightly-e2e",
  "branch": "main",
  "commitSha": "abc1234",
  "durationSeconds": 1842,
  "stages": [
    {
      "stage": "lint",
      "verdict": "pass",
      "severity": "info",
      "issues": 0,
      "cost_usd": 0.0023,
      "model": "claude-3.5-haiku",
      "duration_seconds": 42,
      "summary": "...",
      "logs": "...",
      "findings": [
        { "file": "apps/backend/.../foo.py", "severity": "low", "message": "..." }
      ]
    }
  ]
}
```

`createRun()` computes run-level totals (cost sum, issue sum, max-severity, overall verdict = `fail` if any stage failed) and writes everything in a single transaction. Returns `{ id }` with `201`.

### Query layer

`listRuns({pipeline?, verdict?, limit, offset})` filters on pipeline/verdict, paginates, returns `{runs, total}`. `getRun(id)` joins stages and findings. `getTrends(days)` rolls up daily totals and computes a rising/falling indicator (latest day vs. window average, with 20%/30% thresholds). `getHotspots(limit)` groups findings by file and returns the most-touched files. Everything is parameterized via named bindings (`:pipeline`, `:days`, `:limit`) — no string interpolation.

### Server load functions

Every page has a `+page.server.ts` that calls the DB layer directly and returns the data:

```ts
// +page.server.ts (Overview)
export const load: PageServerLoad = async () => {
  const { runs } = listRuns({ limit: 10 });
  const trends = getTrends(7);
  // compute stats inline
  return { runs, trends, stats };
};
```

Pages consume `data` via the standard SvelteKit `$props()` shape. There is no client-side fetch path for the views themselves — only the `+server.ts` endpoints are reachable as JSON.

### Sidebar shell

`+layout.svelte` defines a fixed left sidebar with Overview / Runs / Trends / Hotspots and the active state is computed by checking `pathname.startsWith(href)` (with an exact-match exception for `/`). It uses the same Tailwind v4 design tokens (`sidebar-bg`, `border-border`, `accent`) as the main app but in this app's own `app.css` — they are not shared.

## External dependencies

| Concern | Where |
|---|---|
| Storage | SQLite file at `$CI_DATA_DIR/ci.db` (default `./data/`). In K8s, mounted from a PVC. |
| Ingest source | CI pipeline finalize step posts to `POST /api/runs`. No authentication on this endpoint today; rely on network isolation in the `devops` namespace. |
| Object storage (planned) | `minio` is listed in `dependencies` for fetching raw logs/artifacts, but there is no MinIO call site in `db.ts` yet. |
| Hosting | `node:22-alpine` runtime; `node build/index.js` on port 3000 inside the container. |
| Build | `npm install` + `npm run build` + `svelte-kit sync`. Standalone — no nx-managed shared cache; project.json delegates to `npx vite dev` / `npm run build`. |

Env vars:

- `CI_DATA_DIR` — directory containing `ci.db`. Default: `<cwd>/data`. The Dockerfile sets `CI_DATA_DIR=/data`.
- `PORT` — node server port. Default 3000.

## How to add common things

### Add a new view

1. Create `src/routes/<slug>/+page.svelte` and `+page.server.ts`.
2. In the `load` function, call into `src/lib/server/db.ts` — never import `better-sqlite3` from a `+page.svelte`; the SQLite handle is server-only.
3. Add the entry to the sidebar `nav` array in `src/routes/+layout.svelte` with a `lucide-svelte` icon.
4. If the view needs new query shapes, add the function to `db.ts` and export the row + result types from there.

### Wire a new K8s data source

The dashboard currently does **not** read from the K8s API or the platform Postgres. If a future view needs to (e.g., live job status from the CI platform's K8s namespace), the design is:

1. Add a new `src/lib/server/<source>.ts` module with the K8s client and any required credentials (read from env).
2. Wire env vars through `deploy/Dockerfile` and the CI platform's Helm values.
3. Call it from a `+page.server.ts` `load` function so the secret never reaches the browser.
4. Document the new dependency in the `External dependencies` table above and in the CI platform's deploy knowledge.

### Add a new field to the run/stage/finding tables

This is a forward-only migration:

1. Add a new `CREATE TABLE` column inside `migrate()` guarded by `ALTER TABLE ... ADD COLUMN ... IF NOT EXISTS`-equivalent (SQLite doesn't natively support `IF NOT EXISTS` for `ADD COLUMN`, so wrap in a `PRAGMA table_info` check or version-stamp the migration).
2. Update the matching `CreateRunInput`, `RunRow`, `StageRow`, or `FindingRow` interface in `db.ts`.
3. Update the ingest validation in `createRun()`.
4. Update consuming views and queries.
5. The DB is on a PVC — existing rows will have NULL for the new column. Default it.

## Common failure modes

- **`ci.db` not writable on startup.** The data directory isn't mounted, or the container user can't write to it. The Dockerfile leaves the user as `node` and expects the PVC to be world-writable or the `node` UID to own it. Check `ls -la /data` in the running pod.
- **`SQLITE_BUSY: database is locked` under concurrent writes.** Two server instances pointing at the same SQLite file. The PVC is RWO; only one pod should mount it. If horizontal scaling is required, switch to Postgres — SQLite + WAL handles concurrent readers but not multi-process writers across hosts.
- **Trends view shows "stable" forever.** The rising/falling logic needs `avgIssues > 0` (resp. `avgCost > 0`) before flagging a direction. A fresh DB or a quiet week stays stable until thresholds are exceeded.
- **Ingest succeeds but the run doesn't appear in the list.** Created without `pipeline` or with an unexpected `verdict` value — the row is in the DB but the list view filters by pipeline. Confirm with `GET /api/runs?limit=5` directly.
- **Build fails with `better-sqlite3` native module error.** The npm install path runs in `node:22-alpine`; the Dockerfile installs `python3 make g++` to compile the native module. If you change the base image, re-install those.

## Related knowledge

- [`architecture.md`](../../architecture.md) — places ci-admin in the third tier of the diagram.
- [`apps/frontend/app.md`](app.md) — the main user app (different audience, different stack choices).
- [`ci/pipelines.md`](../../ci/pipelines.md) — the CI platform that produces the runs this dashboard renders.
- [`deploy/helm.md`](../../deploy/helm.md) — the CI platform Helm release lives in the `devops` namespace, separate from the main `concord` chart.
