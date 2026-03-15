# React to Svelte Migration — Master Overview

## Purpose

This document is the **rebase anchor** for the Concord frontend migration from React 19 to SvelteKit with Svelte 5 (Runes). After completing each tier, the implementing agent should re-read this document, compare expected state vs actual state, and update the tier plans if implementation revealed necessary changes.

---

## Critical Principles (Read First)

### 1. Visual Parity is Non-Negotiable

Every migrated component, page, and interaction MUST look identical to the React version. Same:
- Layout and spacing
- Colors (via the existing design token system)
- Typography
- Animations
- Hover/focus states
- Responsive breakpoints

Do NOT change the design. Do NOT "improve" anything visually. The goal is a 1:1 port.

### 2. Svelte 5 with Runes

We are using **Svelte 5** (latest LTS) which introduces **Runes** — a new reactivity model:

```svelte
<script>
  // State (replaces React's useState)
  let count = $state(0);

  // Derived (replaces React's useMemo)
  let doubled = $derived(count * 2);

  // Effects (replaces React's useEffect)
  $effect(() => {
    console.log('count changed:', count);
  });

  // Props (replaces React's props destructuring)
  let { name, onSubmit } = $props();
</script>
```

### 3. SvelteKit for Routing

SvelteKit replaces React Router. File-based routing:
- `src/routes/+page.svelte` → `/`
- `src/routes/products/+page.svelte` → `/products`
- `src/routes/system/nodes/[nodeName]/+page.svelte` → `/system/nodes/:nodeName`

### 4. Keep Tailwind + Design Tokens

The existing Tailwind config and CSS custom properties remain unchanged. Copy `tailwind.config.js` and `styles.css` directly.

---

## Technology Stack Comparison

| Layer | React (Current) | Svelte (Target) |
|-------|-----------------|-----------------|
| Framework | React 19 | Svelte 5 |
| Meta-framework | Vite (SPA) | SvelteKit |
| Routing | react-router-dom 7 | SvelteKit file-based |
| State | useState/useContext | $state / $derived / Context |
| Effects | useEffect | $effect |
| Auth | Context + localStorage | Context + cookies |
| Styling | Tailwind CSS | Tailwind CSS (unchanged) |
| Icons | lucide-react | lucide-svelte |
| OAuth | @react-oauth/google | Custom (SvelteKit auth) |
| WebSocket | socket.io-client | socket.io-client (unchanged) |
| Terminal | @xterm/xterm | @xterm/xterm (unchanged) |

---

## Migration Strategy

We will migrate in **4 tiers**, each building on the previous:

### Tier 1: Foundation & Auth
- Project scaffolding (SvelteKit, Tailwind, design tokens)
- API client module
- Auth context and login flow
- Layout (sidebar, header, theme toggle)
- Protected routes

### Tier 2: Core Pages
- Dashboard
- Users
- Permission Sets
- History
- Guides

### Tier 3: Domain Features
- Products (full CRUD, detail view, sub-entities)
- Codebases (full CRUD, releases, artifacts)
- Inventory (components, assemblies, BOM editor)

### Tier 4: System Monitor & Advanced
- System overview, nodes, pods, deployments, services, jobs, config
- Log streaming (WebSocket)
- Pod exec terminal (WebSocket + xterm)
- RBAC viewer
- YAML editor

---

## File Structure Comparison

### React (Current)
```
apps/frontend/concord-app/src/
├── main.tsx                          # Entry point
├── app/
│   ├── app.tsx                       # Root component + routes
│   ├── auth-provider.tsx             # Auth context
│   ├── theme-provider.tsx            # Theme context
│   ├── api.ts                        # API client
│   ├── types.ts                      # Shared types
│   ├── types/models.ts               # Model interfaces
│   ├── hooks/
│   │   ├── use-fetch-data.ts
│   │   └── use-chipset-config.ts
│   ├── components/
│   │   ├── layout.tsx
│   │   ├── sidebar.tsx
│   │   ├── ui/                       # Reusable UI components
│   │   │   ├── status-badge.tsx
│   │   │   ├── error-alert.tsx
│   │   │   ├── loading-state.tsx
│   │   │   └── ...
│   │   ├── system/                   # System monitor components
│   │   └── settings/                 # Settings modal sections
│   └── pages/
│       ├── login.tsx
│       ├── dashboard.tsx
│       ├── products/
│       │   ├── products-page.tsx
│       │   ├── product-card.tsx
│       │   └── ...
│       └── system/
│           ├── system-page.tsx
│           └── ...
└── styles.css
```

### Svelte (Target)
```
apps/frontend/concord-app/src/
├── app.html                          # HTML template
├── app.css                           # Global styles (same as styles.css)
├── lib/
│   ├── api.ts                        # API client
│   ├── types.ts                      # Shared types
│   ├── types/models.ts               # Model interfaces
│   ├── stores/
│   │   ├── auth.svelte.ts            # Auth state (runes-based)
│   │   └── theme.svelte.ts           # Theme state
│   ├── components/
│   │   ├── layout.svelte
│   │   ├── sidebar.svelte
│   │   ├── ui/                       # Reusable UI components
│   │   │   ├── status-badge.svelte
│   │   │   ├── error-alert.svelte
│   │   │   ├── loading-state.svelte
│   │   │   └── ...
│   │   ├── system/                   # System monitor components
│   │   └── settings/                 # Settings modal sections
│   └── utils/
│       └── fetch-data.svelte.ts      # Reactive data fetcher
├── routes/
│   ├── +layout.svelte                # Root layout
│   ├── +page.svelte                  # Dashboard (/)
│   ├── login/+page.svelte
│   ├── products/
│   │   ├── +page.svelte              # Products list
│   │   └── [id]/+page.svelte         # Product detail
│   └── system/
│       ├── +layout.svelte            # System layout with sub-nav
│       ├── +page.svelte              # Overview
│       ├── nodes/
│       │   ├── +page.svelte          # Nodes list
│       │   └── [nodeName]/+page.svelte
│       └── ...
└── hooks.server.ts                   # Auth hooks
```

---

## Component Migration Patterns

### React → Svelte Cheat Sheet

#### State
```tsx
// React
const [count, setCount] = useState(0);
setCount(c => c + 1);

// Svelte 5
let count = $state(0);
count += 1;
```

#### Props
```tsx
// React
function Button({ label, onClick }: { label: string; onClick: () => void }) {
  return <button onClick={onClick}>{label}</button>;
}

// Svelte 5
<script>
  let { label, onclick } = $props();
</script>
<button {onclick}>{label}</button>
```

#### Effects
```tsx
// React
useEffect(() => {
  fetchData();
}, [dependency]);

// Svelte 5
$effect(() => {
  // Automatically tracks `dependency` if used inside
  fetchData();
});
```

#### Context
```tsx
// React
const AuthContext = createContext<AuthContextValue>(...);
const { user } = useContext(AuthContext);

// Svelte 5
import { getContext, setContext } from 'svelte';
// In parent: setContext('auth', authState);
// In child: const auth = getContext<AuthState>('auth');
```

#### Conditional Rendering
```tsx
// React
{loading ? <Spinner /> : <Content />}
{error && <Error message={error} />}

// Svelte
{#if loading}
  <Spinner />
{:else}
  <Content />
{/if}
{#if error}
  <Error message={error} />
{/if}
```

#### Lists
```tsx
// React
{items.map(item => <Item key={item.id} {...item} />)}

// Svelte
{#each items as item (item.id)}
  <Item {...item} />
{/each}
```

#### Event Handlers
```tsx
// React
<button onClick={(e) => handleClick(e)}>

// Svelte
<button onclick={(e) => handleClick(e)}>
```

#### Two-way Binding
```tsx
// React
<input value={name} onChange={(e) => setName(e.target.value)} />

// Svelte
<input bind:value={name} />
```

#### Class Binding
```tsx
// React
<div className={`base ${active ? 'active' : ''} ${large ? 'large' : ''}`}>

// Svelte
<div class="base" class:active class:large>
```

---

## Component Inventory

### Tier 1 — Foundation (17 components)

| React Component | Svelte Target | Priority |
|-----------------|---------------|----------|
| `main.tsx` | `app.html` + `+layout.svelte` | 1 |
| `app.tsx` | `routes/+layout.svelte` | 1 |
| `auth-provider.tsx` | `lib/stores/auth.svelte.ts` | 1 |
| `theme-provider.tsx` | `lib/stores/theme.svelte.ts` | 1 |
| `api.ts` | `lib/api.ts` | 1 |
| `components/layout.tsx` | `lib/components/layout.svelte` | 1 |
| `components/sidebar.tsx` | `lib/components/sidebar.svelte` | 1 |
| `components/ui/theme-toggle.tsx` | `lib/components/ui/theme-toggle.svelte` | 1 |
| `components/ui/error-alert.tsx` | `lib/components/ui/error-alert.svelte` | 1 |
| `components/ui/loading-state.tsx` | `lib/components/ui/loading-state.svelte` | 1 |
| `components/ui/empty-state.tsx` | `lib/components/ui/empty-state.svelte` | 1 |
| `components/ui/status-badge.tsx` | `lib/components/ui/status-badge.svelte` | 1 |
| `components/ui/page-header.tsx` | `lib/components/ui/page-header.svelte` | 1 |
| `components/ui/confirm-delete-dialog.tsx` | `lib/components/ui/confirm-delete-dialog.svelte` | 1 |
| `components/ui/back-button.tsx` | `lib/components/ui/back-button.svelte` | 1 |
| `components/ui/select.tsx` | `lib/components/ui/select.svelte` | 1 |
| `pages/login.tsx` | `routes/login/+page.svelte` | 1 |

### Tier 2 — Core Pages (7 components)

| React Component | Svelte Target | Priority |
|-----------------|---------------|----------|
| `pages/dashboard.tsx` | `routes/+page.svelte` | 2 |
| `pages/users.tsx` | `routes/users/+page.svelte` | 2 |
| `pages/permission-sets.tsx` | `routes/permission-sets/+page.svelte` | 2 |
| `pages/history/history-page.tsx` | `routes/history/+page.svelte` | 2 |
| `pages/guides/guides-page.tsx` | `routes/guides/+page.svelte` | 2 |
| `components/settings/settings-modal.tsx` | `lib/components/settings/settings-modal.svelte` | 2 |
| `components/settings/sections/*.tsx` (4 files) | `lib/components/settings/sections/*.svelte` | 2 |

### Tier 3 — Domain Features (22 components)

| React Component | Svelte Target | Priority |
|-----------------|---------------|----------|
| `pages/products/products-page.tsx` | `routes/products/+page.svelte` | 3 |
| `pages/products/product-card.tsx` | `lib/components/products/product-card.svelte` | 3 |
| `pages/products/product-detail.tsx` | `lib/components/products/product-detail.svelte` | 3 |
| `pages/products/board-revision-list.tsx` | `lib/components/products/board-revision-list.svelte` | 3 |
| `pages/products/firmware-app-list.tsx` | `lib/components/products/firmware-app-list.svelte` | 3 |
| `pages/products/firmware-build-list.tsx` | `lib/components/products/firmware-build-list.svelte` | 3 |
| `pages/products/firmware-build-upload.tsx` | `lib/components/products/firmware-build-upload.svelte` | 3 |
| `pages/codebases/codebases-page.tsx` | `routes/codebases/+page.svelte` | 3 |
| `pages/codebases/codebase-card.tsx` | `lib/components/codebases/codebase-card.svelte` | 3 |
| `pages/codebases/codebase-detail.tsx` | `lib/components/codebases/codebase-detail.svelte` | 3 |
| `pages/codebases/release-form.tsx` | `lib/components/codebases/release-form.svelte` | 3 |
| `pages/codebases/artifact-list.tsx` | `lib/components/codebases/artifact-list.svelte` | 3 |
| `pages/codebases/artifact-upload.tsx` | `lib/components/codebases/artifact-upload.svelte` | 3 |
| `pages/inventory/inventory-catalog.tsx` | `routes/inventory/+page.svelte` | 3 |
| `pages/inventory/components-tab.tsx` | `lib/components/inventory/components-tab.svelte` | 3 |
| `pages/inventory/component-card.tsx` | `lib/components/inventory/component-card.svelte` | 3 |
| `pages/inventory/assemblies-tab.tsx` | `lib/components/inventory/assemblies-tab.svelte` | 3 |
| `pages/inventory/assembly-card.tsx` | `lib/components/inventory/assembly-card.svelte` | 3 |
| `pages/inventory/bom-editor.tsx` | `lib/components/inventory/bom-editor.svelte` | 3 |
| `pages/inventory/image-upload.tsx` | `lib/components/inventory/image-upload.svelte` | 3 |
| `hooks/use-fetch-data.ts` | `lib/utils/fetch-data.svelte.ts` | 3 |
| `hooks/use-chipset-config.ts` | `lib/utils/chipset-config.svelte.ts` | 3 |

### Tier 4 — System Monitor (33 components)

| React Component | Svelte Target | Priority |
|-----------------|---------------|----------|
| `pages/system/system-page.tsx` | `routes/system/+layout.svelte` | 4 |
| `pages/system/overview.tsx` | `routes/system/+page.svelte` | 4 |
| `pages/system/nodes-list.tsx` | `routes/system/nodes/+page.svelte` | 4 |
| `pages/system/node-detail.tsx` | `routes/system/nodes/[nodeName]/+page.svelte` | 4 |
| `pages/system/pods-list.tsx` | `routes/system/pods/+page.svelte` | 4 |
| `pages/system/pod-detail.tsx` | `routes/system/pods/[namespace]/[name]/+page.svelte` | 4 |
| `pages/system/deployments-list.tsx` | `routes/system/deployments/+page.svelte` | 4 |
| `pages/system/deployment-detail.tsx` | `routes/system/deployments/[namespace]/[name]/+page.svelte` | 4 |
| `pages/system/services-list.tsx` | `routes/system/services/+page.svelte` | 4 |
| `pages/system/service-detail.tsx` | `routes/system/services/[namespace]/[name]/+page.svelte` | 4 |
| `pages/system/jobs-list.tsx` | `routes/system/jobs/+page.svelte` | 4 |
| `pages/system/job-detail.tsx` | `routes/system/jobs/[namespace]/[name]/+page.svelte` | 4 |
| `pages/system/config-list.tsx` | `routes/system/config/+page.svelte` | 4 |
| `pages/system/events-list.tsx` | `routes/system/events/+page.svelte` | 4 |
| `pages/system/rbac.tsx` | `routes/system/rbac/+page.svelte` | 4 |
| `components/system/metric-card.tsx` | `lib/components/system/metric-card.svelte` | 4 |
| `components/system/status-indicator.tsx` | `lib/components/system/status-indicator.svelte` | 4 |
| `components/system/resource-age.tsx` | `lib/components/system/resource-age.svelte` | 4 |
| `components/system/usage-bar.tsx` | `lib/components/system/usage-bar.svelte` | 4 |
| `components/system/progress-ring.tsx` | `lib/components/system/progress-ring.svelte` | 4 |
| `components/system/label-list.tsx` | `lib/components/system/label-list.svelte` | 4 |
| `components/system/info-row.tsx` | `lib/components/system/info-row.svelte` | 4 |
| `components/system/resource-table.tsx` | `lib/components/system/resource-table.svelte` | 4 |
| `components/system/collapsible-section.tsx` | `lib/components/system/collapsible-section.svelte` | 4 |
| `components/system/namespace-selector.tsx` | `lib/components/system/namespace-selector.svelte` | 4 |
| `components/system/action-button.tsx` | `lib/components/system/action-button.svelte` | 4 |
| `components/system/log-viewer.tsx` | `lib/components/system/log-viewer.svelte` | 4 |
| `components/system/terminal.tsx` | `lib/components/system/terminal.svelte` | 4 |
| `components/system/yaml-viewer.tsx` | `lib/components/system/yaml-viewer.svelte` | 4 |
| `components/system/yaml-editor.tsx` | `lib/components/system/yaml-editor.svelte` | 4 |
| `components/system/resource-yaml-dialog.tsx` | `lib/components/system/resource-yaml-dialog.svelte` | 4 |
| `components/ui/error-boundary.tsx` | `routes/+error.svelte` | 4 |
| `pages/placeholder.tsx` | N/A (remove) | 4 |

**Total: 79 components** (17 + 7 + 22 + 33)

---

## Dependencies

### Current (React)
```json
{
  "@fontsource-variable/inter": "^5.2.8",
  "@react-oauth/google": "^0.13.4",
  "@xterm/addon-fit": "^0.11.0",
  "@xterm/xterm": "^6.0.0",
  "lucide-react": "^0.563.0",
  "react": "19.0.0",
  "react-dom": "19.0.0",
  "react-router-dom": "^7.13.0",
  "socket.io-client": "^4.8.3"
}
```

### Target (Svelte)
```json
{
  "@fontsource-variable/inter": "^5.2.8",
  "@sveltejs/kit": "^2.0.0",
  "@xterm/addon-fit": "^0.11.0",
  "@xterm/xterm": "^6.0.0",
  "lucide-svelte": "^0.470.0",
  "socket.io-client": "^4.8.3",
  "svelte": "^5.0.0"
}
```

---

## Tier Summary

| Tier | Scope | Components | Phases | Status |
|------|-------|------------|--------|--------|
| **Tier 1** | Foundation & Auth | 17 | 6 | `[ ]` |
| **Tier 2** | Core Pages | 7 | 4 | `[ ]` |
| **Tier 3** | Domain Features | 22 | 6 | `[ ]` |
| **Tier 4** | System Monitor | 33 | 6 | `[ ]` |

**Total: 79 components across 22 phases**

---

## Risk Mitigation

### Google OAuth
React uses `@react-oauth/google`. For Svelte, we need to implement OAuth manually using SvelteKit's auth patterns. The flow:
1. Redirect to Google OAuth consent screen
2. Google redirects back with auth code
3. Server hook exchanges code for tokens
4. Store user session in cookie

### WebSocket (SocketIO)
`socket.io-client` is framework-agnostic. The integration pattern changes slightly:
- React: create socket in `useEffect`, cleanup on unmount
- Svelte: create socket in `$effect`, cleanup via return function

### xterm.js
xterm is also framework-agnostic. Same pattern as WebSocket — initialize in `$effect`, destroy on cleanup. Must use `bind:this` to get DOM reference for terminal container.

### Portals (Modals)
React uses `createPortal`. Svelte uses `<svelte:body>` or the `portal` action pattern. For dialogs, we can use SvelteKit's built-in `<dialog>` element with `.showModal()`.

---

## Verification Protocol

After each phase:
1. Run `npm run dev` — app starts without errors
2. Visually compare migrated pages to React version
3. Test all interactive elements (forms, buttons, navigation)
4. Check responsive behavior at 3 breakpoints (mobile, tablet, desktop)
5. Verify dark/light theme toggle
6. Check browser console for errors/warnings

After each tier:
1. Full app walkthrough
2. Cross-reference with React app for visual parity
3. Update tier overview with completion notes

---

## Plan Locations

```
docs/v2/plans/react-to-svelte/
  overview.md              ← you are here (master rebase anchor)
  tier-1/
    overview.md            — architecture, component list, phase checklist
    phase-1.md             — project scaffolding (SvelteKit, Tailwind, tokens)
    phase-2.md             — API client and types
    phase-3.md             — auth store and login page
    phase-4.md             — theme store and layout
    phase-5.md             — sidebar and navigation
    phase-6.md             — UI components (status-badge, error-alert, etc.)
  tier-2/
    overview.md
    phase-1.md             — dashboard page
    phase-2.md             — users and permission-sets pages
    phase-3.md             — history page
    phase-4.md             — settings modal and guides
  tier-3/
    overview.md
    phase-1.md             — products list page and card
    phase-2.md             — product detail and sub-entities
    phase-3.md             — codebases list and card
    phase-4.md             — codebase detail, releases, artifacts
    phase-5.md             — inventory catalog and tabs
    phase-6.md             — inventory cards, BOM editor, image upload
  tier-4/
    overview.md
    phase-1.md             — system layout and overview
    phase-2.md             — nodes and events pages
    phase-3.md             — pods and deployments pages
    phase-4.md             — services, jobs, config pages
    phase-5.md             — log viewer and terminal (WebSocket)
    phase-6.md             — RBAC page and YAML editor
```
