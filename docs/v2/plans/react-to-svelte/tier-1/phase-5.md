# Phase 5 — Sidebar and Navigation

## Objective

Fully implement the sidebar with navigation links, mode toggle (Manufacturing/Validation), user info section, and permission-gated admin links. This must be pixel-perfect to the React version.

---

## 1. Update `src/lib/components/sidebar.svelte`

Full implementation porting all React sidebar functionality:

```svelte
<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { browser } from '$app/environment';
  import {
    LayoutDashboard,
    FlaskConical,
    Container,
    Server,
    ClipboardCheck,
    ScrollText,
    BarChart3,
    Settings,
    Users,
    ShieldCheck,
    Cpu,
    Package,
    GitBranch,
    BookOpen,
    History,
    LogOut,
    PanelLeftClose,
    Monitor
  } from 'lucide-svelte';
  import { getTheme } from '$lib/stores/theme.svelte';
  import { getAuth } from '$lib/stores/auth.svelte';

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
  const auth = getAuth();

  type Mode = 'manufacturing' | 'validation';
  const STORAGE_KEY = 'concord-mode';

  function getInitialMode(): Mode {
    if (!browser) return 'manufacturing';
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'manufacturing' || stored === 'validation') return stored;
    return 'manufacturing';
  }

  let mode = $state<Mode>(getInitialMode());

  function handleModeChange(newMode: Mode): void {
    mode = newMode;
    if (browser) {
      localStorage.setItem(STORAGE_KEY, newMode);
    }
  }

  const manufacturingNav = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/tests', icon: FlaskConical, label: 'Tests' },
    { to: '/deployments', icon: Container, label: 'Deployments' },
    { to: '/nodes', icon: Server, label: 'Nodes' },
    { to: '/results', icon: ClipboardCheck, label: 'Test Results' },
    { to: '/logs', icon: ScrollText, label: 'Logs' },
    { to: '/statistics', icon: BarChart3, label: 'Statistics' }
  ];

  const validationNav = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/tests', icon: FlaskConical, label: 'Tests' },
    { to: '/deployments', icon: Container, label: 'Deployments' },
    { to: '/nodes', icon: Server, label: 'Nodes' },
    { to: '/results', icon: ClipboardCheck, label: 'Test Results' },
    { to: '/logs', icon: ScrollText, label: 'Logs' },
    { to: '/statistics', icon: BarChart3, label: 'Statistics' }
  ];

  const navItems = $derived(mode === 'manufacturing' ? manufacturingNav : validationNav);

  const isAdmin = $derived(
    auth.hasPermission('Concord.Admin.Users.View') ||
    auth.hasPermission('Concord.Admin.Inventory.View') ||
    auth.hasPermission('Concord.Admin.Codebases.View') ||
    auth.hasPermission('Concord.Admin.Products.View') ||
    auth.hasPermission('Concord.Admin.History.View') ||
    auth.hasPermission('Concord.Admin.System.View')
  );

  function handleLogout(): void {
    auth.logout();
    goto('/login');
  }

  function isActive(path: string, end = false): boolean {
    if (end) {
      return $page.url.pathname === path;
    }
    return $page.url.pathname === path || $page.url.pathname.startsWith(path + '/');
  }
</script>

<aside
  class="fixed inset-y-0 left-0 z-30 flex flex-col border-r border-border bg-sidebar-bg transition-[width] duration-200 ease-in-out"
  class:w-16={collapsed}
  class:w-sidebar={!collapsed}
>
  <!-- Brand + collapse toggle -->
  <div
    class="flex h-14 items-center"
    class:justify-center={collapsed}
    class:px-2={collapsed}
    class:justify-between={!collapsed}
    class:px-5={!collapsed}
  >
    {#if collapsed}
      <button
        onclick={onToggle}
        title="Expand sidebar"
        aria-label="Expand sidebar"
        class="flex items-center justify-center"
      >
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

  <!-- Mode toggle -->
  <div
    class="flex rounded-lg bg-surface-2 p-0.5"
    class:mx-2={collapsed}
    class:mt-3={true}
    class:mx-4={!collapsed}
  >
    <button
      onclick={() => handleModeChange('manufacturing')}
      class="flex-1 rounded-md text-center text-2xs font-medium transition-all"
      class:px-1={collapsed}
      class:py-1.5={true}
      class:px-2={!collapsed}
      class:bg-accent-muted={mode === 'manufacturing'}
      class:text-accent={mode === 'manufacturing'}
      class:shadow-sm={mode === 'manufacturing'}
      class:text-text-tertiary={mode !== 'manufacturing'}
      class:hover:text-text-secondary={mode !== 'manufacturing'}
    >
      {collapsed ? 'M' : 'Manufacturing'}
    </button>
    <button
      onclick={() => handleModeChange('validation')}
      class="flex-1 rounded-md text-center text-2xs font-medium transition-all"
      class:px-1={collapsed}
      class:py-1.5={true}
      class:px-2={!collapsed}
      class:bg-accent-muted={mode === 'validation'}
      class:text-accent={mode === 'validation'}
      class:shadow-sm={mode === 'validation'}
      class:text-text-tertiary={mode !== 'validation'}
      class:hover:text-text-secondary={mode !== 'validation'}
    >
      {collapsed ? 'V' : 'Validation'}
    </button>
  </div>

  <!-- Navigation -->
  <nav
    class="flex-1 space-y-0.5 pt-4 pb-2"
    class:px-2={collapsed}
    class:px-3={!collapsed}
  >
    {#each navItems as { to, icon: Icon, label }}
      <a
        href={to}
        ondblclick={onToggle}
        title={collapsed ? label : undefined}
        class="group relative flex items-center rounded-lg text-[13px] font-medium transition-all"
        class:justify-center={collapsed}
        class:px-0={collapsed}
        class:py-2={true}
        class:gap-3={!collapsed}
        class:px-3={!collapsed}
        class:bg-sidebar-active={isActive(to, to === '/')}
        class:text-accent={isActive(to, to === '/')}
        class:text-text-secondary={!isActive(to, to === '/')}
        class:hover:bg-sidebar-hover={!isActive(to, to === '/')}
        class:hover:text-text-primary={!isActive(to, to === '/')}
      >
        {#if isActive(to, to === '/')}
          <div class="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r bg-accent"></div>
        {/if}
        <Icon size={18} strokeWidth={1.75} class="shrink-0" />
        {#if !collapsed}
          <span class="truncate">{label}</span>
        {/if}
      </a>
    {/each}

    <!-- Admin section -->
    {#if isAdmin}
      <div class="pt-4">
        <div class="border-t border-border" class:mx-0={collapsed} class:mx-1={!collapsed}></div>
        <div class="pt-4">
          {#if !collapsed}
            <span class="mb-2 block px-3 text-2xs font-medium uppercase tracking-widest text-text-tertiary">
              Admin
            </span>
          {/if}

          {#if auth.hasPermission('Concord.Admin.System.View')}
            <a
              href="/system"
              ondblclick={onToggle}
              title={collapsed ? 'System' : undefined}
              class="group relative flex items-center rounded-lg text-[13px] font-medium transition-all"
              class:justify-center={collapsed}
              class:px-0={collapsed}
              class:py-2={true}
              class:gap-3={!collapsed}
              class:px-3={!collapsed}
              class:bg-sidebar-active={isActive('/system')}
              class:text-accent={isActive('/system')}
              class:text-text-secondary={!isActive('/system')}
              class:hover:bg-sidebar-hover={!isActive('/system')}
              class:hover:text-text-primary={!isActive('/system')}
            >
              {#if isActive('/system')}
                <div class="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r bg-accent"></div>
              {/if}
              <Monitor size={18} strokeWidth={1.75} class="shrink-0" />
              {#if !collapsed}<span class="truncate">System</span>{/if}
            </a>
          {/if}

          {#if auth.hasPermission('Concord.Admin.Inventory.View')}
            <a
              href="/inventory"
              ondblclick={onToggle}
              title={collapsed ? 'Inventory' : undefined}
              class="group relative flex items-center rounded-lg text-[13px] font-medium transition-all"
              class:justify-center={collapsed}
              class:px-0={collapsed}
              class:py-2={true}
              class:gap-3={!collapsed}
              class:px-3={!collapsed}
              class:bg-sidebar-active={isActive('/inventory')}
              class:text-accent={isActive('/inventory')}
              class:text-text-secondary={!isActive('/inventory')}
              class:hover:bg-sidebar-hover={!isActive('/inventory')}
              class:hover:text-text-primary={!isActive('/inventory')}
            >
              {#if isActive('/inventory')}
                <div class="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r bg-accent"></div>
              {/if}
              <Cpu size={18} strokeWidth={1.75} class="shrink-0" />
              {#if !collapsed}<span class="truncate">Inventory</span>{/if}
            </a>
          {/if}

          {#if auth.hasPermission('Concord.Admin.Codebases.View')}
            <a
              href="/codebases"
              ondblclick={onToggle}
              title={collapsed ? 'Codebases' : undefined}
              class="group relative flex items-center rounded-lg text-[13px] font-medium transition-all"
              class:justify-center={collapsed}
              class:px-0={collapsed}
              class:py-2={true}
              class:gap-3={!collapsed}
              class:px-3={!collapsed}
              class:bg-sidebar-active={isActive('/codebases')}
              class:text-accent={isActive('/codebases')}
              class:text-text-secondary={!isActive('/codebases')}
              class:hover:bg-sidebar-hover={!isActive('/codebases')}
              class:hover:text-text-primary={!isActive('/codebases')}
            >
              {#if isActive('/codebases')}
                <div class="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r bg-accent"></div>
              {/if}
              <GitBranch size={18} strokeWidth={1.75} class="shrink-0" />
              {#if !collapsed}<span class="truncate">Codebases</span>{/if}
            </a>
          {/if}

          {#if auth.hasPermission('Concord.Admin.Products.View')}
            <a
              href="/products"
              ondblclick={onToggle}
              title={collapsed ? 'Products' : undefined}
              class="group relative flex items-center rounded-lg text-[13px] font-medium transition-all"
              class:justify-center={collapsed}
              class:px-0={collapsed}
              class:py-2={true}
              class:gap-3={!collapsed}
              class:px-3={!collapsed}
              class:bg-sidebar-active={isActive('/products')}
              class:text-accent={isActive('/products')}
              class:text-text-secondary={!isActive('/products')}
              class:hover:bg-sidebar-hover={!isActive('/products')}
              class:hover:text-text-primary={!isActive('/products')}
            >
              {#if isActive('/products')}
                <div class="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r bg-accent"></div>
              {/if}
              <Package size={18} strokeWidth={1.75} class="shrink-0" />
              {#if !collapsed}<span class="truncate">Products</span>{/if}
            </a>
          {/if}

          {#if auth.hasPermission('Concord.Admin.History.View')}
            <a
              href="/history"
              ondblclick={onToggle}
              title={collapsed ? 'History' : undefined}
              class="group relative flex items-center rounded-lg text-[13px] font-medium transition-all"
              class:justify-center={collapsed}
              class:px-0={collapsed}
              class:py-2={true}
              class:gap-3={!collapsed}
              class:px-3={!collapsed}
              class:bg-sidebar-active={isActive('/history')}
              class:text-accent={isActive('/history')}
              class:text-text-secondary={!isActive('/history')}
              class:hover:bg-sidebar-hover={!isActive('/history')}
              class:hover:text-text-primary={!isActive('/history')}
            >
              {#if isActive('/history')}
                <div class="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r bg-accent"></div>
              {/if}
              <History size={18} strokeWidth={1.75} class="shrink-0" />
              {#if !collapsed}<span class="truncate">History</span>{/if}
            </a>
          {/if}

          <a
            href="/guides"
            ondblclick={onToggle}
            title={collapsed ? 'Guides' : undefined}
            class="group relative flex items-center rounded-lg text-[13px] font-medium transition-all"
            class:justify-center={collapsed}
            class:px-0={collapsed}
            class:py-2={true}
            class:gap-3={!collapsed}
            class:px-3={!collapsed}
            class:bg-sidebar-active={isActive('/guides')}
            class:text-accent={isActive('/guides')}
            class:text-text-secondary={!isActive('/guides')}
            class:hover:bg-sidebar-hover={!isActive('/guides')}
            class:hover:text-text-primary={!isActive('/guides')}
          >
            {#if isActive('/guides')}
              <div class="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r bg-accent"></div>
            {/if}
            <BookOpen size={18} strokeWidth={1.75} class="shrink-0" />
            {#if !collapsed}<span class="truncate">Guides</span>{/if}
          </a>

          {#if auth.hasPermission('Concord.Admin.Users.View')}
            <a
              href="/users"
              ondblclick={onToggle}
              title={collapsed ? 'Users' : undefined}
              class="group relative flex items-center rounded-lg text-[13px] font-medium transition-all"
              class:justify-center={collapsed}
              class:px-0={collapsed}
              class:py-2={true}
              class:gap-3={!collapsed}
              class:px-3={!collapsed}
              class:bg-sidebar-active={isActive('/users')}
              class:text-accent={isActive('/users')}
              class:text-text-secondary={!isActive('/users')}
              class:hover:bg-sidebar-hover={!isActive('/users')}
              class:hover:text-text-primary={!isActive('/users')}
            >
              {#if isActive('/users')}
                <div class="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r bg-accent"></div>
              {/if}
              <Users size={18} strokeWidth={1.75} class="shrink-0" />
              {#if !collapsed}<span class="truncate">Users</span>{/if}
            </a>

            <a
              href="/permission-sets"
              ondblclick={onToggle}
              title={collapsed ? 'Permission Sets' : undefined}
              class="group relative flex items-center rounded-lg text-[13px] font-medium transition-all"
              class:justify-center={collapsed}
              class:px-0={collapsed}
              class:py-2={true}
              class:gap-3={!collapsed}
              class:px-3={!collapsed}
              class:bg-sidebar-active={isActive('/permission-sets')}
              class:text-accent={isActive('/permission-sets')}
              class:text-text-secondary={!isActive('/permission-sets')}
              class:hover:bg-sidebar-hover={!isActive('/permission-sets')}
              class:hover:text-text-primary={!isActive('/permission-sets')}
            >
              {#if isActive('/permission-sets')}
                <div class="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r bg-accent"></div>
              {/if}
              <ShieldCheck size={18} strokeWidth={1.75} class="shrink-0" />
              {#if !collapsed}<span class="truncate">Permission Sets</span>{/if}
            </a>
          {/if}
        </div>
      </div>
    {/if}
  </nav>

  <!-- Bottom -->
  <div
    class="border-t border-border space-y-0.5"
    class:p-2={collapsed}
    class:p-3={!collapsed}
  >
    <button
      onclick={onSettingsClick}
      ondblclick={onToggle}
      title={collapsed ? 'Settings' : undefined}
      class="group relative flex w-full items-center rounded-lg text-[13px] font-medium transition-all text-text-secondary hover:bg-sidebar-hover hover:text-text-primary"
      class:justify-center={collapsed}
      class:px-0={collapsed}
      class:py-2={true}
      class:gap-3={!collapsed}
      class:px-3={!collapsed}
    >
      <Settings size={18} strokeWidth={1.75} class="shrink-0" />
      {#if !collapsed}<span class="truncate">Settings</span>{/if}
    </button>

    <!-- User info + logout -->
    {#if auth.user}
      <div
        class="mt-1 flex items-center rounded-lg"
        class:justify-center={collapsed}
        class:py-2={collapsed}
        class:gap-2={!collapsed}
        class:px-3={!collapsed}
        class:py-2={!collapsed}
      >
        <div
          class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-muted text-2xs font-semibold text-accent"
          title={collapsed
            ? `${auth.user.name}${auth.user.permissionSetName ? ` (${auth.user.permissionSetName})` : ''}`
            : undefined}
        >
          {auth.user.name.charAt(0).toUpperCase()}
        </div>
        {#if !collapsed}
          <div class="min-w-0 flex-1">
            <div class="truncate text-2xs font-medium text-text-primary">
              {auth.user.name}
            </div>
            <div class="truncate text-2xs text-text-tertiary">
              {auth.user.permissionSetName || auth.user.email}
            </div>
          </div>
          <button
            onclick={handleLogout}
            title="Sign out"
            aria-label="Log out"
            class="shrink-0 rounded p-1 text-text-tertiary transition-colors hover:bg-sidebar-hover hover:text-text-primary"
          >
            <LogOut size={14} strokeWidth={1.75} />
          </button>
        {/if}
      </div>
    {/if}
  </div>
</aside>
```

---

## 2. Create Placeholder Routes

Create placeholder pages for routes that aren't fully implemented yet:

**`src/routes/tests/+page.svelte`:**
```svelte
<script>
  import PageHeader from '$lib/components/ui/page-header.svelte';
</script>

<div class="animate-fade-in">
  <PageHeader title="Tests" description="Coming in a future tier." />
  <div class="mt-6 rounded-xl border border-border bg-surface-1 p-6">
    <p class="text-sm text-text-tertiary">This page is a placeholder.</p>
  </div>
</div>
```

Create similar files for:
- `/deployments`
- `/nodes`
- `/results`
- `/logs`
- `/statistics`
- `/users`
- `/permission-sets`
- `/inventory`
- `/codebases`
- `/products`
- `/history`
- `/guides`
- `/system`

---

## Verification

1. `npm run dev` starts without errors
2. All sidebar navigation links render
3. Active link is highlighted with accent color and left indicator
4. Mode toggle switches between Manufacturing/Validation
5. Mode persists on page refresh
6. Sidebar collapses/expands correctly
7. Double-click on any link toggles sidebar collapse
8. Admin section shows only if user has relevant permissions
9. User avatar shows first initial
10. Logout button works
11. Visual comparison to React app shows identical styling

---

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `src/lib/components/sidebar.svelte` | Replace | Full sidebar implementation |
| `src/routes/*/+page.svelte` | Create | Placeholder pages for all routes |

---

## Next Phase

Phase 6 will implement the remaining UI components (status-badge, error-alert, etc.).
