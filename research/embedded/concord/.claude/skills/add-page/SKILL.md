---
name: add-page
description: Add a new SvelteKit page to the main app, with the right auth gating, API call, and tests.
argument-hint: "<route path> — <one-line purpose>"
---

# /add-page

Spawn `frontend-eng` (`.claude/agents/frontend-eng.md`).

## What the agent does

1. **Pick the route folder**: `apps/frontend/app/src/routes/<domain>/<segment>/`.

2. **Create the page**: `+page.svelte` + `+page.ts` (loader). Use `apiFetch<ApiResponse<T>>(...)` from `src/lib/api.ts` for any backend call.

3. **Gate permissions in the loader**: don't rely on visual gating only. If the user lacks permission, redirect to a friendly page (or the dashboard).

4. **Wire SocketIO** if the page shows real-time data — subscribe in `onMount`, unsubscribe in `onDestroy`.

5. **Mirror types**: if the response shape isn't already in `src/lib/types/models.ts`, add it. Coordinate with `http-api-eng` on the canonical shape.

6. **Tailwind + design tokens**: use existing utility classes. No arbitrary hex values, no inline styles.

7. **Tests**:
   - Vitest unit/component test in `*.test.ts` for any non-trivial logic.
   - Playwright E2E in `*.e2e.ts` for the golden user flow.

8. **Update knowledge**: `.claude/knowledge/apps/frontend/app.md`.

## Decision points

- Does the page belong in the main nav? → update the nav store.
- Pagination? → use the `pagination` field on the API response.
- Empty state? → write it before the populated state.

## Verify

```bash
nx serve app                            # localhost:4200 — manual click-through
nx test app                             # vitest
nx run app:test:e2e                     # Playwright
nx typecheck app
```
