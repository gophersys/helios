---
paths:
  - "apps/frontend/app/**/*.{ts,svelte}"
---

# Frontend SvelteKit Rules

## Page Structure

SvelteKit uses file-based routing. Pages go in `src/routes/<domain>/+page.svelte`. Reference: `src/routes/products/` is the canonical example.

A typical domain has:
- `src/routes/<domain>/+page.svelte` — list page with cards, filters, actions
- `src/routes/<domain>/[id]/+page.svelte` — detail view with tabs
- `src/lib/components/<domain>/` — reusable components for the domain

## Route Conventions

- `+page.svelte` — page component
- `+layout.svelte` — layout wrapper (sidebar, auth checks)
- `+error.svelte` — error boundary for the route
- Dynamic params use `[id]` brackets: `src/routes/products/[id]/+page.svelte`

## Component Pattern

Components live in `src/lib/components/`. Use Svelte 5 runes (`$state`, `$derived`, `$effect`, `$props`):

```svelte
<script lang="ts">
  import { getAuth } from '$lib/stores/auth.svelte';

  let { entityId }: { entityId: string } = $props();

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('products:manage'));

  let data = $state<Entity | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
</script>
```

## Permission Gating

Every page must check permissions on mount:

```svelte
onMount(async () => {
  if (!auth.hasPermission('products:view')) {
    goto('/');
    return;
  }
  // ... fetch data
});
```

Manage actions (create, edit, delete) are gated with:
```svelte
const canManage = $derived(auth.hasPermission('products:manage'));
```

## Common Components

Always use these from `src/lib/components/ui/`:
- `<StatusBadge status={status} />` — colored pill for ACTIVE/DRAFT/RELEASED/etc.
- Error alerts, confirm dialogs, back buttons as needed

## Types

- Shared model interfaces go in `src/lib/types/models.ts` — never duplicate interfaces across pages
- `ApiResponse<T>` is in `src/lib/types.ts`
- Import models as: `import type { Product } from '$lib/types/models'`

## API Calls

Use `api` from `$lib/api` for all requests:
```typescript
import { api } from '$lib/api';

const res = await api.get<ApiResponse<Product[]>>('/v2/products');
```

Never access `localStorage` directly for tokens. For file uploads use `apiUpload()`. For raw uploads (no JSON parse) use `apiUploadRaw()`.

## Stores

Svelte 5 rune-based stores live in `src/lib/stores/`:
- `auth.svelte.ts` — authentication state, `hasPermission()`, login/logout
- `theme.svelte.ts` — dark/light theme

Access via context: `const auth = getAuth();`

## Styling & Design System

All styling rules, spacing constraints, typography hierarchy, and component patterns are defined in:

- **`/DESIGN.md`** — the full design system reference (colors, spacing, typography, component patterns)
- **`.claude/rules/ui-design-system.md`** — enforcement rules that must be followed for all UI code

Key principles: 4px grid, design token colors only, component classes from `app.css`, `rounded-lg` for cards. Read those files before any UI work.

## Environment Awareness

Environment is baked in at build time via `PUBLIC_APP_ENVIRONMENT`:
```typescript
import { PUBLIC_APP_ENVIRONMENT, PUBLIC_APP_VERSION } from '$env/static/public';
```

- `development` / `local` — shows DEV badge (warning color), View As enabled
- `staging` — shows STAGING badge (accent color), View As hidden
- `production` — no badge, View As hidden

## Testing

Run with: `nx test app`
