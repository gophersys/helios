---
paths:
  - "apps/frontend/app/**/*.{ts,svelte}"
---

# Frontend React Rules

## Page Structure

New feature pages go in `src/app/pages/<domain>/`. Reference: `src/app/pages/products/` is the canonical example.

A typical domain has:
- `<domain>-page.tsx` — list page with cards, form, detail routing
- `<domain>-card.tsx` — card component for the grid
- `<domain>-detail.tsx` — detail view with tabs
- Sub-entity lists and upload forms as needed

## List Page Pattern

Follow `src/app/pages/products/products-page.tsx`:
- Check permission with `useAuth().hasPermission()`, redirect with `<Navigate>` if denied
- State: `entities[]`, `loading`, `error`, `showForm`, `editingId`, `form*` fields, `submitting`, `deleteTarget`, `selectedEntity`
- Fetch with `useCallback` + `useEffect`, set `loading=false` in `finally`
- `resetForm()` clears all form state
- `handleSubmit()`: sets `submitting=true`, tries API call, calls `resetForm()` + `fetchEntities()` on success, `finally` sets `submitting=false`
- Submit button: `disabled={submitting}`, text changes to "Saving..." when submitting
- Delete flow: `setDeleteTarget({id, name})` → `<ConfirmDeleteDialog>` → `handleDelete(id)`

## Card Component Pattern

Follow `src/app/pages/products/product-card.tsx`:
- Receives `entity`, `canManage`, `onEdit`, `onDelete`, `onSelect` props
- Uses `group` class with hover-reveal edit/delete buttons via `opacity-0 group-hover:opacity-100`
- All icon buttons must have both `title` and `aria-label`

## Detail Page Pattern

Follow `src/app/pages/products/product-detail.tsx`:
- Tab navigation with `activeTab` state
- `<BackButton>` at top
- Header with name, status badge, description, metadata counts
- Tab bar: active tab gets `border-b-2 border-accent text-accent`

## Sub-Entity List Pattern

Follow `src/app/pages/products/board-revision-list.tsx`:
- Inline add/edit form toggled by `showForm` state
- Section header with title + "Add" button
- Table or card list for items
- `<ConfirmDeleteDialog>` for delete confirmation

## Common Components

Always use these from `src/app/components/ui/`:
- `<ErrorAlert message={error} />` — displays error, returns null if no error
- `<ConfirmDeleteDialog>` — type-to-confirm deletion (uses `createPortal`)
- `<StatusBadge status={status} />` — colored pill for ACTIVE/DRAFT/RELEASED/etc.
- `<BackButton label="..." onClick={...} />` — back navigation
- `<Select>` / `<Select compact>` — styled select replacing native `<select>`
- `<ErrorBoundary>` — wraps route content in `layout.tsx`

## Types

- Shared model interfaces go in `src/app/types/models.ts` — never duplicate interfaces across pages
- `ApiResponse<T>` is in `src/app/types.ts`
- Import models as: `import { Product, BoardRevision } from '../../types/models'`

## API Calls

Use `api()` from `src/app/api.ts` for all requests. Never access `localStorage` directly for tokens. For file uploads use `apiUpload()`. For raw uploads (no JSON parse) use `apiUploadRaw()`.

## Hooks

- `useFetchData<T>(url)` — generic data fetcher with loading/error/refetch
- Create domain-specific hooks wrapping `useFetchData` (see `src/app/hooks/use-chipset-config.ts`)

## Route Registration

In `src/app/app.tsx`: lazy-import the page, add `<Route path="domain" element={<DomainPage />} />`. In `src/app/components/sidebar.tsx`: add nav link with Lucide icon, gated by `hasPermission()`.

## Styling Tokens

Never use hardcoded colors. Use the design token system:
- Surfaces: `bg-surface-0` (base input), `bg-surface-1` (card), `bg-surface-2` (hover/header)
- Text: `text-text-primary`, `text-text-secondary`, `text-text-tertiary`
- Semantic: `bg-accent`, `bg-error`, `bg-success`, `bg-warning` + `-muted` variants
- Borders: `border-border`, `border-border-subtle`
- Accent hover: `hover:bg-accent-hover`

Common class patterns:
- Card: `rounded-xl border border-border bg-surface-1 p-5`
- Input: `rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none`
- Primary button: `rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50`
- Secondary button: `rounded-lg px-3 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2`
- Page animation: `animate-fade-in` on root div
- Small text: `text-2xs` for labels, badges, metadata

## Testing

Tests are colocated as `*.spec.tsx` / `*.spec.ts` next to source files. Run with:
```bash
cd apps/frontend/app && npx nx test app
```

When creating **new** pages/components (via the `add-page` or `add-crud-feature` skill), add spec files. This is forward-looking only — existing pages without tests are not violations. Use test helpers from `src/testing/`:
- `renderApp(ui, { auth?, route? })` — wraps with AuthContext + MemoryRouter
- `mockFetch(data)` / `mockFetchRoutes(routes)` — mock `global.fetch`
- Factory functions in `src/testing/fixtures.ts` for test data

See `src/app/pages/products/products-page.spec.tsx` for the reference pattern.
