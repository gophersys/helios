# app (Concord frontend) — knowledge

The primary user-facing UI for the Concord platform. SvelteKit + Svelte 5 (runes), Tailwind v4, built as a static SPA and served by Nginx. Talks to `http-api` over REST and Socket.IO; mirrors backend types by hand. Its single most important responsibility is to be the source of truth for every human interaction with the platform — login, products, builds, validation, manufacturing, fixtures, users, releases.

Refresh this file when: a top-level route is added or removed, the API client contract changes, a new global store is added, or the SocketIO/auth flow shifts.

## Location

- Code: `apps/frontend/app/`
- Entry point: `apps/frontend/app/src/routes/+layout.svelte` (root layout creates auth + theme contexts)
- API client: `apps/frontend/app/src/lib/api.ts`
- Type mirrors: `apps/frontend/app/src/lib/types/models.ts`
- Unit tests: `apps/frontend/app/src/**/*.test.ts` (vitest)
- E2E tests: `apps/frontend/app/e2e/*.spec.ts` (Playwright)

## Responsibilities

Owns:

- All user-facing screens for the platform (everything under `src/routes/`).
- The thin API client (`apiFetch`, `api.{get,post,put,patch,delete}`, `apiUpload*`).
- Auth state + JWT lifecycle (localStorage + parent-domain cookie for docs).
- SocketIO subscriptions: `/notifications`, `/kubernetes`, run streams.
- Hand-mirrored TypeScript types of every backend response shape.
- Toast, error-reporting modal, and global error boundary.
- The "view-as-role" impersonation header for admins.

Does NOT own:

- Authentication itself (handled by `http-api` via Google OAuth + JWT).
- The docs site, the CI dashboard, or the CI platform UI — those are independent SvelteKit/MkDocs apps.
- Server-side rendering — `adapter-static` is used; everything is a static SPA.
- Code generation against the backend — there is none. Type sync is manual.

## Internal structure

```
apps/frontend/app/
├── src/
│   ├── app.css                # Tailwind v4 entry + design tokens
│   ├── app.html               # SvelteKit shell
│   ├── hooks.client.ts
│   ├── routes/                # SvelteKit file-router (URL = path)
│   │   ├── +layout.svelte     # Root: auth/theme contexts, EnvBanner, ErrorBoundary
│   │   ├── +page.svelte       # / dashboard
│   │   ├── login/
│   │   ├── products/[id]/
│   │   ├── builds/[id], builds/runs/[id], builds/prs/[productId]/[prNumber], builds/settings/
│   │   ├── validation/{benches,runs,queue,designs}/
│   │   ├── manufacturing/{session/[id]/run/[runId],sessions}/
│   │   ├── fixtures/[id]/
│   │   ├── kubernetes/{pods,nodes,jobs,services,deployments,events,rbac,config}/
│   │   ├── ci/builds/[id]/
│   │   ├── users/, releases/, history/, error-reports/, case-study/
│   └── lib/
│       ├── api.ts             # apiFetch + apiUpload + api.* helpers
│       ├── docs.ts            # links into docs site
│       ├── types/
│       │   ├── models.ts      # backend type mirrors (~1500 lines)
│       │   ├── ci.ts, queue.ts, stages.ts
│       ├── stores/            # Svelte 5 runes state (singletons + contexts)
│       │   ├── auth.svelte.ts        # AuthState class, context
│       │   ├── theme.svelte.ts       # context
│       │   ├── notifications.svelte.ts  # singleton, SocketIO-fed
│       │   ├── toast.svelte.ts       # singleton
│       │   ├── error-reporter.svelte.ts
│       ├── services/          # API call modules per domain
│       │   ├── products.ts, validation.ts, stages.ts, queue.ts, ci.ts
│       │   ├── websocket.ts   # SocketIO namespace plumbing
│       ├── components/        # by domain: dashboard, products, validation,
│       │                      #   manufacturing, fixtures, users, ci, ui, icons,
│       │                      #   layout.svelte, sidebar.svelte
│       ├── constants/, hooks/, actions/, utils/
├── static/                    # served as-is by Nginx
│   └── corectl/install.sh     # GENERATED — do not edit directly; source is
│                              #   tools/corectl/install.sh. Synced by
│                              #   nx run corectl:sync-install-script, which
│                              #   containerize depends on.
├── deploy/                    # Dockerfile + nginx.conf
├── e2e/                       # Playwright specs + page objects + fixtures
├── tests/                     # vitest setup
├── vite.config.ts             # /v2, /auth, /socket.io → backendUrl
├── svelte.config.js           # adapter-static, $lib/$components aliases
├── tailwind.* / postcss.config.js
└── project.json               # nx targets
```

## Key patterns

### SvelteKit routing

File-system routing under `src/routes/`. Folders map to URL segments; `[id]` is a param; `+page.svelte` is the page; `+layout.svelte` is the wrapper; `+error.svelte` is the route-level error UI. The app uses `adapter-static` (see `svelte.config.js`) with `fallback: 'index.html'` so it serves as a single-page app — there is no server-side rendering and no `+page.server.ts` files in the main app.

Aliases: `$lib → src/lib`, `$components → src/lib/components`.

### The `api.ts` contract

`apiFetch<T>(path, options)` is the only outbound HTTP call site. Behaviour:

- Injects `Authorization: Bearer <jwt>` from `localStorage['concord-token']`.
- Injects `X-View-As-Role` from `localStorage['concord-view-as-role']` when present (admin/maintainer impersonation).
- 401 → clear token + redirect to `/login` (the auth store explicitly bypasses this on login attempts so it can show the error inline).
- Tracks every call via `trackAction()` for the error-reporter (last-N-actions ring buffer).
- On 5xx or non-GET 4xx, fires `reportApiError(...)` which surfaces a "report this" modal.
- Convenience wrapper: `api.get/post/put/patch/delete<T>(path, body?)`. For multipart: `apiUpload(path, formData)` or `apiUploadRaw(path, formData)`.

Always use `apiFetch`/`api.*`. Never `fetch()` directly except in the very narrow login flow (so 401s don't trigger the global redirect).

### Auth flow

- Auth state lives in `AuthState` (`stores/auth.svelte.ts`), created at the root layout via `createAuthContext()` and consumed via `getAuth()`.
- `auth.init()` reads the token, calls `GET /v2/auth/me`, and populates `user` + `permissions`.
- `auth.login(email, password)` posts to `/v2/auth/login`, stores the token, then re-fetches `/v2/auth/me`.
- `auth.devLogin(email)` exists only for dev mode (`AUTH_ENABLED=false`).
- `setToken` also writes the JWT to a parent-domain cookie (`concord-auth`) so the docs subdomain at `docs.<host>` can read it for role filtering.
- The root `+effect(() => …)` in `+layout.svelte` redirects unauthenticated users to `/login`.

### Stores

Svelte 5 runes (`$state`, `$derived`, `$effect`) wrap singleton or context-scoped classes. Two patterns:

- **Context-scoped** (multi-instance possible, route-scoped lifecycle): `AuthState`, `ThemeState`. Created in `+layout.svelte` via `setContext`, read via `getContext`.
- **Module-singleton** (process-wide): `getNotifications()` returns a single `NotificationState`; same for `toasts`. Used for state that has no useful scope smaller than the app.

`NotificationState` mirrors the contract: fetch initial list via `GET /v2/notifications`, increment `unreadCount` via `GET /v2/notifications/unread-count`, then receive live pushes via the SocketIO `/notifications` namespace and call `addRealtime(...)`.

### Type mirroring (the discipline)

`src/lib/types/models.ts` is the hand-maintained mirror of every Python response shape from `http-api`. There is no codegen. When a backend `Module.from_json/to_json` shape changes:

1. Update the Python handler + its tests.
2. Update the matching interface in `models.ts` in the same commit.
3. Update every component that reads or writes that field.

The knowledge-freshness hook does not catch this — it's discipline. The exception is enums: domain enums live in Prisma; their TS string-union mirrors must be updated alongside `models.ts` when an enum value is added (see `rules/prisma-flow.md`).

### SocketIO

The frontend connects to multiple namespaces (`services/websocket.ts`):

- `/notifications` — feeds `NotificationState`.
- `/kubernetes` (named `systemSocket` in code) — pod logs, exec sessions.
- `/runs` — live test-run progress.

Authentication uses the JWT in the `auth` payload (Socket.IO supports this natively, unlike a plain WS). Transports order is `['polling', 'websocket']` to survive proxies that block upgrade.

### Tailwind v4

PostCSS-based, single entry at `src/app.css`. Design tokens (`bg-surface-0`, `text-text-primary`, `border-accent`, etc.) defined there. No `tailwind.config.js`. Components compose `tailwind-variants` for variant-driven styles and `clsx` / `tailwind-merge` for runtime composition.

### Run-error banner (P2.3)

The run-detail pages (validation runs, manufacturing session runs)
surface a top-of-page failure banner when a run finishes with a
visible problem. Lives at
`src/lib/components/execution/run-error-banner.svelte` (thin
renderer) over `run-error-banner.ts` (pure-TS classification — unit
tested at `run-error-banner.test.ts`).

Three variants:

- `all-skipped` — yellow warning banner. Fires when
  `status === 'FAILED' AND completedCount > 0 AND passedCount === 0
  AND failedCount === 0` — the v0.12.0 → 0.12.3 silent-skew pathology.
  Headline names the count (`All 126 tests skipped — run did not
  execute`); detail prefers the API-supplied `errorMessage` and falls
  back to a synthetic remediation pointing at
  `corectl test refresh-framework && corectl test upload`.
- `failed` — red alert banner. Fires when `status === 'FAILED'` with
  a non-empty `errorMessage` and at least one passed/failed test.
  Headline is "Run failed"; detail is the verbatim errorMessage.
- `cancelled` — neutral surface-2 banner. Fires when
  `status === 'CANCELLED'` with a note.

Wired into `run-execution-page.svelte` between the top-level
ErrorAlert and the `RunExecutionHeader`. Visible on every page that
uses `RunExecutionPage` — validation runs, manufacturing session
runs, and any future executors.

The classification logic mirrors the http-api detection at
`apps/backend/http-api/src/api/v2/runs/reporter.py::report_finish`
(P2.2): both compute `all_skipped` the same way. If the http-api
synthesizes an `errorMessage`, the frontend renders it; if the
http-api didn't (defensive), the frontend synthesizes one. Tested
in `run-error-banner.test.ts` (15 unit tests).

No Svelte component-test harness exists in this app, so the
component itself is verified visually in dev. The pure-TS helper
behind it is the unit-tested boundary.

## External dependencies

| Concern | Where |
|---|---|
| Backend API | `http-api` at the path the dev proxy or ingress points at. Dev: `vite.config.ts` proxies `/v2`, `/auth`, `/socket.io` to `VITE_BACKEND_URL` (default `http://localhost:9001`). Staging/prod: same-origin via ingress. |
| Auth provider | Google OAuth via `http-api`; dev bypass via `/v2/auth/dev-login`. |
| Realtime | Socket.IO over the same backend host. Namespaces: `/notifications`, `/kubernetes`, `/runs`. |
| Static hosting | `nginx` in `deploy/Dockerfile`. K8s exposes via the `concord` ingress at the platform root domain. |
| Build info | `/build-info.json` is served alongside the SPA. The root layout polls it every 60s and prompts a reload when the version changes (catches stale chunks after a deploy). |

Env vars consumed at build/runtime:

- `VITE_BACKEND_URL` — dev only, proxy target.
- `PUBLIC_APP_ENVIRONMENT` — `development|local|staging|production`, controls the banner and dev-only toasts.
- `PUBLIC_APP_VERSION` — embedded version string, used for the update prompt.

## How to add common things

### Add a new page

1. Create the route under `src/routes/<domain>/.../+page.svelte` (and `+page.svelte` for any required nested layout).
2. If the page needs auth + permissions, check `auth.hasPermission(...)` inline or guard via the root layout — there is no per-route loader because the app is static.
3. Add the API call(s) to a service module under `src/lib/services/<domain>.ts` rather than calling `api.*` directly from the component.
4. Add the response shapes to `src/lib/types/models.ts` (mirror the backend).
5. Add an entry to the sidebar in `src/lib/components/sidebar.svelte` (gated by permission).
6. Write a Playwright spec under `e2e/<domain>.spec.ts` if the page has meaningful interaction.

### Add a new API call

1. Add the response interface(s) to `src/lib/types/models.ts`.
2. Add a function to the relevant `src/lib/services/<domain>.ts`:
   ```ts
   import { api } from '$lib/api';
   import type { ApiResponse, Widget } from '$lib/types/models';
   export async function listWidgets(): Promise<Widget[]> {
     const res = await api.get<ApiResponse<Widget[]>>('/v2/widgets');
     return res.data;
   }
   ```
3. Consume from components — never call `api.*` directly from a `.svelte` file unless it's a one-off.

### Sync a backend type change

1. Pull the matching field/shape change into the right `interface` in `models.ts`.
2. Update every component that reads or writes the field — the TS compiler will not catch a renamed field if both sides use `unknown` casts; rely on `nx run app:check` after editing.
3. If the change touches an enum, update the string-union type in `models.ts` and any `Permissions.*`-style constants used on the frontend.
4. Commit backend + frontend changes together. The hook expects both `apps/backend/http-api.md` and `apps/frontend/app.md` to be updated when the contract changes.

## Common failure modes

- **"Session expired" on every request after deploy.** The JWT signing key (`JWT_SECRET_KEY`) was rotated server-side. Frontend has no way to know — it just gets 401s. Fix: log out and back in. If it persists, the secret-sync into K8s failed; see `deploy/secrets.md`.
- **`Failed to fetch dynamically imported module` after a deploy.** The user has a stale `index.html` referencing chunks the server no longer has. The root layout's `unhandledrejection` handler matches this string and reloads the page once (with a 10s session-storage lock to prevent reload loops). If a user is stuck looping, clear sessionStorage manually.
- **Notifications stop arriving.** Either the SocketIO `/notifications` namespace failed to authenticate (token expired in localStorage but cookie still present), or the backend `notify_user(...)` is writing the DB row but the socketio emit is silently failing. Check the network tab for the `/socket.io/?EIO=4...` polling request; if it 401s, log out and back in. Server-side, check the http-api logs for `socketio.emit` errors.
- **`models.ts` drift.** A component reads `run.startedAt` (camelCase) but the API responds with `started_at` (snake_case) because the backend `to_json` was changed without updating the mirror. Symptom: silent `undefined`. Fix: re-read the actual JSON from devtools and update `models.ts`. There is no enforcement — code review is the safety net.
- **`X-View-As-Role` leaking into prod.** Admin sets view-as-role for debugging, navigates to a different env via the env banner, role header still sent. The header is dropped server-side for non-admins but can mask real permission bugs. Fix: clear localStorage `concord-view-as-role` or use the auth menu's "stop viewing as".

## Related knowledge

- [`architecture.md`](../../architecture.md) — system overview, request lifecycle.
- [`conventions.md`](../../conventions.md) — handler shape, response envelope, type-mirror discipline.
- [`apps/backend/http-api.md`](../backend/http-api.md) — the API the frontend talks to.
- [`apps/frontend/docs.md`](docs.md) — the docs subdomain that shares the auth cookie.
- [`apps/frontend/ci-admin.md`](ci-admin.md) — sibling standalone dashboard, not part of this app.
- [`workflows/local-dev.md`](../../workflows/local-dev.md) — running `nx serve app` against a staging backend.
- [`rules/prisma-flow.md`](../../../rules/prisma-flow.md) — backend schema → frontend type mirror.


## TestBedDesign UI (renamed from FixtureDesign, 2026-05-14)

The user-facing TestBed design rows are surfaced in three places:

- `src/lib/components/products/testbed-designs-section.svelte` — the per-product list (was `fixture-designs-section.svelte`).
- `src/lib/components/fixtures/testbed-designs.svelte` — the admin CRUD page (was `fixture-designs.svelte`).
- `src/routes/validation/testbed-designs/+page.svelte` — the validation-engineer index (was `routes/validation/designs/+page.svelte`).

All UI strings show "TestBed Design" (capital T, capital B). The TypeScript types in `models.ts` are `TestBedDesign` and `TestBedDesignSummary`. API client calls hit `/v2/test-bed-designs` (not the old `/v2/fixtures/designs`). Concord's `Fixture` (the physical rig) is unchanged — see `product-domains/fixtures.md`.

**v0.10.2** (2026-05-14): user-visible string sweep finishing the TestBedDesign rename. Lowercase 'fixture design(s)' → 'TestBed design(s)' across empty states, error toasts, loading labels, dialog confirmations, and form fields. No schema, no API, no shape change.

## FixtureClaim (DEV_HOLD) types

`src/lib/types/models.ts` carries the type mirrors for the developer-lease feature:

- `FixtureClaimStatus` — string-union `'ACTIVE' | 'RELEASED' | 'EXPIRED' | 'ABANDONED'` matching the Prisma enum.
- `FixtureClaim` — the lease itself; `fixtureId` is non-null in fixture-mode and null in node-mode. `claimedNodes` is populated only in node-mode.
- `ClaimedNode` — the node-mode child rows, one per held node.

Only the type definitions land in this commit. The API-client wiring (`api.fixtureClaims.*`) and any UI that surfaces "I'm holding this fixture" indicators ship in follow-up commits and add their own knowledge entries when they do.
