---
name: apps-frontend-concord-app-add-page
description: Create a new Concord frontend page with list, detail, and CRUD following established SvelteKit patterns
user-invocable: true
argument-hint: <page-name> <description>
---

# Add Frontend Page

Create a new page for the Concord SvelteKit frontend app.

Arguments: $ARGUMENTS

## Steps

1. **Read the reference pattern** — Read these files to understand established conventions:
   - `apps/frontend/app/src/routes/products/+page.svelte` (list page with search, filter, pagination)
   - `apps/frontend/app/src/routes/products/[id]/+page.svelte` (detail view with tabs)
   - `apps/frontend/app/src/lib/components/products/product-card.svelte` (card component)
   - `apps/frontend/app/src/lib/components/products/product-detail.svelte` (detail with tabs)
   - `apps/frontend/app/src/lib/components/ui/` (common components: card, modal, tabs, pagination, etc.)
   - `apps/frontend/app/src/lib/types/models.ts` (shared type definitions)
   - `apps/frontend/app/src/lib/api.ts` (API layer: apiFetch, api.get/post/put/delete)

2. **Add model types** to `src/lib/types/models.ts` — never define interfaces locally in page files

3. **Create route files** at `src/routes/<domain>/`:
   - `+page.svelte` — list page: permission check on mount, fetch data, grid of cards, pagination
   - For detail view: `src/routes/<domain>/[id]/+page.svelte` — BackButton, header, tabs

4. **Create components** at `src/lib/components/<domain>/`:
   - `<domain>-card.svelte` — card: title, description, metadata, status badge
   - `<domain>-detail.svelte` — detail with tab navigation (if needed)
   - Sub-entity components as needed

5. **Every page must**:
   - Check `auth.hasPermission()` on mount and `goto('/')` if denied
   - Use `$lib/api` for ALL API calls (never direct `fetch` or `localStorage`)
   - Use `$lib/components/ui/error-alert.svelte` for error display
   - Use `$lib/components/ui/confirm-delete-dialog.svelte` for deletions
   - Use `$lib/components/ui/select.svelte` (not native `<select>`) for dropdowns
   - Use `$lib/components/ui/pagination.svelte` for list pagination
   - Have `submitting` state on forms with `disabled={submitting}` on buttons
   - Use Svelte 5 runes (`$state`, `$derived`, `$effect`) — NOT Svelte 4 stores
   - Add `aria-label` to all icon-only buttons
   - Import icons from `lucide-svelte`

6. **Add sidebar link** in `src/lib/components/sidebar.svelte`:
   - Add entry in the appropriate section (primary, admin, or system)
   - Gate with `auth.hasPermission('<domain>:view')`
   - Use Lucide icon

7. **Verify** — run `npx nx typecheck app` and `npx nx build app` from the repo root

8. **Test** — Add test files following the patterns in `src/lib/components/products/`:
   - `src/lib/components/<domain>/<component>.test.ts` — vitest unit tests
   - Use `createMockFetch()` from `src/tests/helpers.ts` for API mocking
   - Use `createMockUser()`, `createMockProduct()` etc. from `src/tests/helpers.ts`
   - Run: `cd apps/frontend/app && npx vitest run`
