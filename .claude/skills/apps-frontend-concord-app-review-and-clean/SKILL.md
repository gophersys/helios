---
name: apps-frontend-concord-app-review-and-clean
description: Review and clean the SvelteKit frontend for pattern violations, accessibility issues, and design token consistency
user-invocable: true
argument-hint: [route-name|all]
---

# Review & Clean Frontend App

Audit the SvelteKit frontend for pattern violations, design token consistency, accessibility, type safety, and code quality. Optionally target a single route/component directory or scan everything.

Arguments: $ARGUMENTS

## Scope

If an argument is provided (e.g., `catalog`, `codebases`, `users`), review only that route and its related components at `src/lib/components/<arg>/`. If the argument is `all` or omitted, review every route and component.

## Execution Strategy

Launch **parallel agents** (using the Task tool with `subagent_type: "general-purpose"`) for each review dimension. Each agent reads the relevant source files and reports findings. After all agents complete, compile a unified report and apply auto-fixable changes.

### Agent 1: Component Pattern Review

Read every `.svelte` file in the target scope and verify:

1. **Script tag** — Must use `<script lang="ts">`

2. **Props interface** — Every component with props must define `interface Props { ... }` and destructure with `let { ... }: Props = $props()`
   - Never use `export let` (Svelte 4 syntax)
   - Optional props use `?` in interface and defaults in destructuring

3. **Reactivity** — Verify correct usage:
   - `$state()` for mutable reactive variables
   - `$derived()` for computed read-only values (never `$state` for computed)
   - `$effect()` for side effects (never raw reactive statements)

4. **Event handlers** — Must use `handle*` prefix (handleSubmit, handleDelete, handleToggle)
   - Never bare function names like `delete`, `submit`, `toggle` in `onclick`

5. **Import ordering** — Must follow:
   - Svelte imports (`onMount`, `getContext`)
   - SvelteKit imports (`goto`, `page`)
   - Third-party (`lucide-svelte`)
   - Type imports (`import type { ... }`)
   - Lib imports (`$lib/api`, `$lib/stores/*`, `$lib/components/ui`)
   - Relative imports (`./component.svelte`)

6. **Snippet usage** — Components that accept children or slots use `Snippet` type, rendered with `{@render children()}`

**Reference files:**
- `apps/frontend/app/src/lib/components/catalog/product-detail.svelte`
- `apps/frontend/app/src/lib/components/catalog/board-list.svelte`
- `apps/frontend/app/src/lib/components/ui/card.svelte`

### Agent 2: Design Token & Styling Review

Read every `.svelte` file and check for design token violations:

1. **No hardcoded colors** — Flag any use of:
   - Tailwind color literals: `bg-blue-500`, `text-gray-600`, `border-red-300`, etc.
   - Hex/RGB in classes or style attributes
   - **Correct alternatives:**
     - `bg-surface-0/1/2/3` for backgrounds
     - `text-text-primary/secondary/tertiary` for text
     - `bg-accent`, `hover:bg-accent-hover` for primary actions
     - `bg-success-muted text-success` for positive states
     - `bg-error-muted text-error` for negative states
     - `bg-warning-muted text-warning` for caution states
     - `border-border` or `border-border-subtle` for borders

2. **Typography consistency:**
   - Page titles: `text-xl font-semibold text-text-primary`
   - Section titles: `text-sm font-semibold text-text-primary`
   - Body text: `text-sm text-text-secondary`
   - Labels: `text-2xs font-medium text-text-tertiary`
   - Badges: `text-2xs font-medium` with semantic bg/text color pair

3. **Button patterns:**
   - Primary: `bg-accent text-white hover:bg-accent-hover disabled:opacity-50`
   - Secondary: `text-text-secondary hover:bg-surface-2`
   - Danger: `text-text-tertiary hover:bg-error-muted hover:text-error`
   - All buttons with icons: `flex items-center gap-1.5` or `gap-2`

4. **Input patterns:**
   - `w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none`
   - Or `bg-surface-1` for inputs inside surface-0 containers

5. **Card patterns:**
   - Use `card card-md` utility class or `rounded-xl border border-border bg-surface-1 p-4`

6. **Status colors** — Must use `StatusBadge` component or match its color mapping:
   - ACTIVE/RELEASED/ONLINE → `bg-success-muted text-success`
   - DEPRECATED/PENDING → `bg-warning-muted text-warning`
   - FAILED/EOL/ERROR → `bg-error-muted text-error`
   - DRAFT → `bg-accent-muted text-accent`
   - OFFLINE/UNKNOWN → `bg-surface-2 text-text-tertiary`

7. **Spacing** — Verify 4px grid alignment (p-2=8px, p-3=12px, p-4=16px, gap-2/3/4)

8. **No inline styles** — Flag any `style="..."` attributes (use Tailwind classes instead)

**Reference files:**
- `apps/frontend/app/src/app.css` (design token definitions)
- `apps/frontend/app/tailwind.config.js` (token mapping)
- `apps/frontend/app/src/lib/components/ui/status-badge.svelte`

### Agent 3: API Integration & Type Safety Review

Read every route `+page.svelte` and data-fetching component and verify:

1. **API calls typed** — All `apiFetch` calls use `ApiResponse<T>` wrapper:
   ```ts
   const res = await apiFetch<ApiResponse<{ data: Item[] }>>('/v2/items');
   ```

2. **Error handling** — Every API call wrapped in try/catch:
   ```ts
   try { ... } catch (err) {
     error = err instanceof Error ? err.message : 'Failed to load';
   }
   ```

3. **Loading state** — Every data-fetching page has `loading` state with `LoadingState` component

4. **No duplicate fetches** — Same data shouldn't be fetched by multiple components (pass as props instead)

5. **Form submission pattern:**
   - `e.preventDefault()` at start
   - `error = null` reset
   - `submitting = true` before API call
   - `resetForm()` after success
   - `finally { submitting = false }`

6. **Envelope extraction** — Paginated responses extract from nested `data.data` correctly

7. **Model types** — All interfaces defined in `src/lib/types/models.ts`, never locally

8. **No direct fetch()** — All API calls through `api.*` or `apiFetch`, never raw `fetch()`

**Reference files:**
- `apps/frontend/app/src/lib/api.ts`
- `apps/frontend/app/src/lib/types/models.ts`
- `apps/frontend/app/src/routes/codebases/+page.svelte`

### Agent 4: Accessibility & UX Review

Read every `.svelte` file and check:

1. **Icon buttons** — Every button with only an icon must have `aria-label`:
   ```svelte
   <button aria-label="Edit" onclick={handleEdit}>
     <Pencil size={14} />
   </button>
   ```

2. **Form labels** — Every input has an associated `<label>` with visible text or `aria-label`

3. **Page title** — Every route has `<svelte:head><title>Page — Concord</title></svelte:head>`

4. **Keyboard navigation** — Interactive elements use `<button>` not `<div onclick>` or `<span onclick>`

5. **Focus management** — Modals trap focus; forms auto-focus first input

6. **Loading indicators** — All async operations show loading state

7. **Empty states** — Lists show `EmptyState` component when empty (not just nothing)

8. **Error states** — All error-prone operations show `ErrorAlert`

9. **Confirm destructive actions** — All delete operations use `ConfirmDeleteDialog`

10. **Animation** — Page root uses `animate-fade-in` class

**Reference files:**
- `apps/frontend/app/src/lib/components/ui/confirm-delete-dialog.svelte`
- `apps/frontend/app/src/lib/components/ui/empty-state.svelte`

### Agent 5: Auth, Permissions & Route Guard Review

Read every route `+page.svelte` and verify:

1. **Permission guard** — Every protected page checks permissions on mount:
   ```ts
   onMount(() => {
     if (!auth.hasPermission('Concord.Admin.<Module>.View')) {
       goto('/');
       return;
     }
     fetchData();
   });
   ```

2. **Auth context** — Uses `const auth = getAuth()` (not creating new auth state)

3. **Permission-gated UI** — Write operations (create, edit, delete buttons) only shown when `canManage` is true:
   ```ts
   const canManage = $derived(auth.hasPermission('Concord.Admin.<Module>.Manage'));
   ```

4. **No hardcoded permission strings** — Permission strings match the pattern `Concord.Admin.<Module>.<View|Manage>`

5. **Sidebar links** — Each route's sidebar link is gated by the same permission used in the page guard

**Reference files:**
- `apps/frontend/app/src/lib/stores/auth.svelte.ts`
- `apps/frontend/app/src/lib/components/sidebar.svelte`
- `apps/frontend/app/src/routes/catalog/+page.svelte`

### Agent 6: CRUD Page Pattern Review

Read every route `+page.svelte` and verify it follows the standard CRUD flow:

1. **State groups** — Organized into: list state, form state, delete state, detail state

2. **Form lifecycle:**
   - `resetForm()` clears all `form*` variables, `editingId`, and `showForm`
   - `startEdit(item)` populates form from existing object and sets `editingId`
   - `handleSubmit` branches on `editingId` (PUT vs POST)
   - After success: `resetForm()` then re-fetch list

3. **Delete lifecycle:**
   - `promptDelete(id)` sets `deleteTarget` object
   - `handleDelete(id)` calls API delete then re-fetches
   - `ConfirmDeleteDialog` with `open={!!deleteTarget}`

4. **Detail navigation:**
   - `selectedItem` state for detail view
   - Conditional render: loading → detail → list
   - `onBack` callback to clear selection
   - `onRefresh` callback to re-fetch detail

5. **Shared UI usage:**
   - `PageHeader` with title and description
   - `ErrorAlert message={error}`
   - `LoadingState` during initial fetch
   - `EmptyState` when list is empty
   - `FormCard` for inline create/edit form

**Reference file:** `apps/frontend/app/src/routes/codebases/+page.svelte`

## Output

After all agents complete, compile findings into a structured report:

```
## Frontend Review Report

### Critical (must fix)
- [ ] Finding with file:line reference

### Design Token Violations
- [ ] Hardcoded color with suggested replacement

### Accessibility Issues
- [ ] Missing aria-label / keyboard navigation issue

### Pattern Deviations
- [ ] Component not following standard pattern

### Missing Tests
- [ ] Component/page that lacks test coverage
```

Then apply auto-fixable changes (hardcoded colors, missing aria-labels, etc.) and list what was fixed vs what needs manual review.

## Verification

After applying fixes, run:
```bash
cd apps/frontend/app
npx svelte-check
npm run build
```

Type checking and build must pass clean.
