---
name: apps-frontend-concord-app-add-page
description: Create a new Concord frontend page with list, detail, and CRUD following established patterns
user-invocable: true
argument-hint: <page-name> <description>
---

# Add Frontend Page

Create a new page for the Concord frontend app.

Arguments: $ARGUMENTS

## Steps

1. **Read the reference pattern** — Read these files to understand established conventions:
   - `apps/frontend/app/src/app/pages/products/products-page.tsx` (list page)
   - `apps/frontend/app/src/app/pages/products/product-card.tsx` (card component)
   - `apps/frontend/app/src/app/pages/products/product-detail.tsx` (detail view with tabs)
   - `apps/frontend/app/src/app/pages/products/board-revision-list.tsx` (sub-entity list)
   - `apps/frontend/app/src/app/components/ui/` (common components)
   - `apps/frontend/app/src/app/types/models.ts` (shared type definitions)

2. **Add model types** to `src/app/types/models.ts` — never define interfaces locally in page files

3. **Create page files** at `src/app/pages/<domain>/`:
   - `<domain>-page.tsx` — list page: permission check, fetch, grid of cards, inline form, detail routing
   - `<domain>-card.tsx` — card: hero area, title, description, metadata, hover-reveal edit/delete
   - `<domain>-detail.tsx` — detail: BackButton, header, tabs, tab content areas
   - Sub-entity lists and upload forms as needed

4. **Every page must**:
   - Check `hasPermission()` and `<Navigate>` if denied
   - Use `<ErrorAlert>` for error display
   - Use `<ConfirmDeleteDialog>` for deletions
   - Use `<Select>` (not native `<select>`) for dropdowns
   - Have `submitting` state on forms with `disabled={submitting}` on buttons
   - Use `api()` from `../../api` for all requests (never direct `fetch` or `localStorage`)
   - Add `aria-label` to all icon-only buttons
   - Use `animate-fade-in` on root div

5. **Register the route** in `src/app/app.tsx`:
   - Add lazy import: `const DomainPage = lazy(() => import('./pages/domain/domain-page').then(m => ({ default: m.DomainPage })));`
   - Add route: `<Route path="domain" element={<DomainPage />} />`

6. **Add sidebar link** in `src/app/components/sidebar.tsx`:
   - Add entry with Lucide icon, gated by `hasPermission()`

7. **Verify** — run `npx tsc --noEmit` and `npx vite build` from the app directory

8. **Test** — Add spec files following the patterns in `src/app/pages/products/`:
   - `<domain>-page.spec.tsx` — test permission guard, loading state, data rendering, form submission
   - `<domain>-card.spec.tsx` — test rendering, click interactions
   - Use `renderApp()` from `src/testing/render-app` for provider wrapping
   - Use `mockFetch()` / `mockFetchRoutes()` from `src/testing/mock-api`
   - Use factory functions from `src/testing/fixtures.ts` (add new ones as needed)
   - Run: `cd apps/frontend/app && npx nx test app`
