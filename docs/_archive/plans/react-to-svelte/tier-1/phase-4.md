# Phase 4 — Theme Store and Layout

## Objective

Implement the theme toggle system and the main authenticated layout component that wraps all protected pages.

---

## 1. Create `src/lib/stores/theme.svelte.ts`

```typescript
import { getContext, setContext } from 'svelte';
import { browser } from '$app/environment';

type Theme = 'light' | 'dark';

class ThemeState {
  theme = $state<Theme>('dark');

  constructor() {
    if (browser) {
      const stored = localStorage.getItem('concord-theme') as Theme | null;
      if (stored) {
        this.theme = stored;
      } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        this.theme = 'dark';
      } else {
        this.theme = 'light';
      }
      this.applyTheme();
    }
  }

  private applyTheme(): void {
    if (!browser) return;
    document.documentElement.classList.remove('light', 'dark');
    document.documentElement.classList.add(this.theme);
  }

  toggle(): void {
    this.theme = this.theme === 'dark' ? 'light' : 'dark';
    if (browser) {
      localStorage.setItem('concord-theme', this.theme);
      this.applyTheme();
    }
  }
}

const THEME_KEY = Symbol('theme');

export function createThemeContext(): ThemeState {
  const theme = new ThemeState();
  setContext(THEME_KEY, theme);
  return theme;
}

export function getTheme(): ThemeState {
  return getContext<ThemeState>(THEME_KEY);
}
```

---

## 2. Create `src/lib/components/ui/theme-toggle.svelte`

```svelte
<script lang="ts">
  import { Sun, Moon } from 'lucide-svelte';
  import { getTheme } from '$lib/stores/theme.svelte';

  const theme = getTheme();
</script>

<button
  onclick={() => theme.toggle()}
  class="flex h-8 w-8 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-surface-2 hover:text-text-primary"
  title={theme.theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
  aria-label={theme.theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
>
  {#if theme.theme === 'dark'}
    <Sun size={18} strokeWidth={1.75} />
  {:else}
    <Moon size={18} strokeWidth={1.75} />
  {/if}
</button>
```

---

## 3. Create `src/lib/components/layout.svelte`

This is the main authenticated layout with sidebar and content area.

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import Sidebar from './sidebar.svelte';
  import SettingsModal from './settings/settings-modal.svelte';

  let { children } = $props();

  // Sidebar collapse state (persisted)
  let collapsed = $state(false);
  let settingsOpen = $state(false);

  onMount(() => {
    if (browser) {
      const stored = localStorage.getItem('concord-sidebar-collapsed');
      collapsed = stored === 'true';
    }
  });

  function toggleSidebar(): void {
    collapsed = !collapsed;
    if (browser) {
      localStorage.setItem('concord-sidebar-collapsed', String(collapsed));
    }
  }
</script>

<div class="flex min-h-screen bg-surface-0">
  <Sidebar
    {collapsed}
    onToggle={toggleSidebar}
    onSettingsClick={() => (settingsOpen = true)}
  />

  <main
    class="flex-1 transition-[margin] duration-200 ease-in-out"
    style:margin-left={collapsed ? '64px' : '260px'}
  >
    <div class="mx-auto max-w-7xl px-6 py-6">
      {@render children()}
    </div>
  </main>
</div>

{#if settingsOpen}
  <SettingsModal onClose={() => (settingsOpen = false)} />
{/if}
```

---

## 4. Create Settings Modal Placeholder

**`src/lib/components/settings/settings-modal.svelte`:**

```svelte
<script lang="ts">
  import { X } from 'lucide-svelte';
  import ThemeToggle from '../ui/theme-toggle.svelte';

  let { onClose }: { onClose: () => void } = $props();
</script>

<!-- Overlay -->
<div
  class="fixed inset-0 z-40 bg-overlay animate-overlay-in"
  onclick={onClose}
  onkeydown={(e) => e.key === 'Escape' && onClose()}
  role="button"
  tabindex="-1"
></div>

<!-- Modal -->
<div
  class="fixed inset-y-0 right-0 z-50 w-full max-w-md animate-modal-in bg-surface-1 shadow-xl"
>
  <div class="flex h-14 items-center justify-between border-b border-border px-5">
    <h2 class="text-sm font-semibold text-text-primary">Settings</h2>
    <button
      onclick={onClose}
      class="flex h-8 w-8 items-center justify-center rounded-lg text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
      title="Close"
      aria-label="Close settings"
    >
      <X size={18} strokeWidth={1.75} />
    </button>
  </div>

  <div class="p-5">
    <div class="mb-4">
      <h3 class="mb-2 text-2xs font-medium uppercase tracking-widest text-text-tertiary">
        Appearance
      </h3>
      <div class="flex items-center justify-between rounded-lg border border-border bg-surface-0 px-3 py-2">
        <span class="text-sm text-text-primary">Theme</span>
        <ThemeToggle />
      </div>
    </div>

    <p class="text-2xs text-text-tertiary">
      More settings coming in Tier 2...
    </p>
  </div>
</div>
```

---

## 5. Update Root Layout

**`src/routes/+layout.svelte`:**

```svelte
<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { createAuthContext } from '$lib/stores/auth.svelte';
  import { createThemeContext } from '$lib/stores/theme.svelte';
  import Layout from '$lib/components/layout.svelte';

  let { children } = $props();

  // Create contexts at the root
  const auth = createAuthContext();
  const theme = createThemeContext();

  // Initialize auth on mount
  onMount(async () => {
    await auth.init();
  });

  // Redirect logic
  $effect(() => {
    if (auth.isLoading) return;

    const isLoginPage = $page.url.pathname === '/login';

    if (!auth.isAuthenticated && !isLoginPage) {
      goto('/login');
    }
  });

  // Determine if we should show the layout
  $effect(() => {
    // This is just for tracking — the actual rendering logic is below
  });

  const isLoginPage = $derived($page.url.pathname === '/login');
</script>

{#if auth.isLoading}
  <div class="flex min-h-screen items-center justify-center bg-surface-0">
    <div class="text-sm text-text-tertiary">Loading...</div>
  </div>
{:else if isLoginPage}
  {@render children()}
{:else if auth.isAuthenticated}
  <Layout>
    {@render children()}
  </Layout>
{/if}
```

---

## 6. Create Sidebar Placeholder

We'll fully implement the sidebar in Phase 5, but we need a placeholder now.

**`src/lib/components/sidebar.svelte`:**

```svelte
<script lang="ts">
  import { PanelLeftClose } from 'lucide-svelte';
  import { getTheme } from '$lib/stores/theme.svelte';

  let {
    collapsed,
    onToggle,
    onSettingsClick
  }: {
    collapsed: boolean;
    onToggle: () => void;
    onSettingsClick: () => void;
  } = $props();

  const theme = getTheme();
</script>

<aside
  class="fixed inset-y-0 left-0 z-30 flex flex-col border-r border-border bg-sidebar-bg transition-[width] duration-200 ease-in-out"
  class:w-16={collapsed}
  class:w-sidebar={!collapsed}
>
  <!-- Brand -->
  <div
    class="flex h-14 items-center"
    class:justify-center={collapsed}
    class:px-2={collapsed}
    class:justify-between={!collapsed}
    class:px-5={!collapsed}
  >
    {#if collapsed}
      <button onclick={onToggle} title="Expand sidebar" aria-label="Expand sidebar">
        <img
          src={theme.theme === 'dark' ? '/assets/ck-logo.png' : '/assets/ck-logo-dark.png'}
          alt="CoreKinect"
          class="h-4"
        />
      </button>
    {:else}
      <div class="flex flex-col gap-1.5">
        <img
          src={theme.theme === 'dark' ? '/assets/corekinect-logo.png' : '/assets/corekinect-logo-dark.png'}
          alt="CoreKinect"
          class="h-3.5"
        />
        <span class="text-2xs font-medium uppercase tracking-widest text-text-tertiary">
          Concord
        </span>
      </div>
      <button
        onclick={onToggle}
        title="Collapse sidebar"
        aria-label="Collapse sidebar"
        class="flex h-7 w-7 items-center justify-center rounded-lg text-text-tertiary transition-colors hover:bg-sidebar-hover hover:text-text-primary"
      >
        <PanelLeftClose size={16} strokeWidth={1.75} />
      </button>
    {/if}
  </div>

  <!-- Divider -->
  <div class="border-t border-border" class:mx-2={collapsed} class:mx-4={!collapsed}></div>

  <!-- Navigation placeholder -->
  <nav class="flex-1 space-y-0.5 pt-4 pb-2" class:px-2={collapsed} class:px-3={!collapsed}>
    <p class="px-3 text-2xs text-text-tertiary">Navigation coming in Phase 5...</p>
  </nav>

  <!-- Bottom -->
  <div class="border-t border-border space-y-0.5" class:p-2={collapsed} class:p-3={!collapsed}>
    <button
      onclick={onSettingsClick}
      title={collapsed ? 'Settings' : undefined}
      class="group relative flex w-full items-center rounded-lg text-[13px] font-medium transition-all text-text-secondary hover:bg-sidebar-hover hover:text-text-primary"
      class:justify-center={collapsed}
      class:px-0={collapsed}
      class:py-2={true}
      class:gap-3={!collapsed}
      class:px-3={!collapsed}
    >
      <span class="shrink-0">⚙️</span>
      {#if !collapsed}
        <span class="truncate">Settings</span>
      {/if}
    </button>
  </div>
</aside>
```

---

## 7. Update Dashboard Page

**`src/routes/+page.svelte`:**

```svelte
<script lang="ts">
  import { getAuth } from '$lib/stores/auth.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';

  const auth = getAuth();
</script>

<svelte:head>
  <title>Dashboard — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="Dashboard"
      description="Welcome to Concord. More features coming soon."
    />
  </div>

  <div class="rounded-xl border border-border bg-surface-1 p-6">
    <p class="text-sm text-text-secondary">
      Logged in as <span class="font-medium text-text-primary">{auth.user?.name}</span>
      ({auth.user?.email})
    </p>
  </div>
</div>
```

---

## 8. Create PageHeader Component

**`src/lib/components/ui/page-header.svelte`:**

```svelte
<script lang="ts">
  let {
    title,
    description
  }: {
    title: string;
    description?: string;
  } = $props();
</script>

<div>
  <h1 class="text-xl font-semibold text-text-primary">{title}</h1>
  {#if description}
    <p class="mt-1 text-sm text-text-secondary">{description}</p>
  {/if}
</div>
```

---

## Verification

1. `npm run dev` starts without errors
2. Login, then navigate to dashboard
3. Sidebar renders with CoreKinect branding
4. Sidebar collapses when toggle button clicked
5. Sidebar state persists on page refresh
6. Settings button opens modal
7. Theme toggle in settings modal switches between light/dark
8. Theme persists on page refresh
9. All colors match the React app exactly

---

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `src/lib/stores/theme.svelte.ts` | Create | Theme state with runes |
| `src/lib/components/ui/theme-toggle.svelte` | Create | Theme toggle button |
| `src/lib/components/layout.svelte` | Create | Main layout |
| `src/lib/components/sidebar.svelte` | Create | Sidebar placeholder |
| `src/lib/components/settings/settings-modal.svelte` | Create | Settings modal |
| `src/lib/components/ui/page-header.svelte` | Create | Page header |
| `src/routes/+layout.svelte` | Modify | Add theme context, layout |
| `src/routes/+page.svelte` | Modify | Dashboard with header |

---

## Next Phase

Phase 5 will fully implement the sidebar with navigation links.
