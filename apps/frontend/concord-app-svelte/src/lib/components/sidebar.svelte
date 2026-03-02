<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { browser } from '$app/environment';
  import {
    LayoutDashboard,
    FlaskConical,
    Warehouse,
    Wrench,
    Settings,
    Users,
    Cpu,
    Package,
    GitBranch,
    History,
    LogOut,
    PanelLeftClose,
    Monitor,
    Rocket
  } from 'lucide-svelte';
  import { PUBLIC_APP_VERSION } from '$env/static/public';
  import { getTheme } from '$lib/stores/theme.svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import ConcordLogo from '$lib/components/concord-logo.svelte';
  import KubernetesIcon from '$lib/components/icons/kubernetes-icon.svelte';

  interface NavItem {
    to: string;
    icon: typeof LayoutDashboard;
    label: string;
    permission?: string;
  }

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

  const navItems = $derived.by(() => {
    const items: NavItem[] = [
      { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
      { to: '/fixtures', icon: Wrench, label: 'Fixtures' },
    ];
    if (mode === 'validation') {
      items.push({ to: '/racks', icon: Monitor, label: 'Racks' });
    }
    items.push({ to: '/tests', icon: FlaskConical, label: 'Tests' });
    return items;
  });

  const adminItems: NavItem[] = [
    { to: '/mtib', icon: Cpu, label: 'MTIB', permission: 'Concord.Admin.Nodes.View' },
    { to: '/kubernetes', icon: KubernetesIcon, label: 'Kubernetes', permission: 'Concord.Admin.System.View' },
    { to: '/deployments', icon: Rocket, label: 'Deployments', permission: 'Concord.Admin.Deployments.View' },
    { to: '/inventory', icon: Warehouse, label: 'Inventory', permission: 'Concord.Admin.Inventory.View' },
    { to: '/catalog', icon: Package, label: 'Catalog', permission: 'Concord.Admin.Catalog.View' },
    { to: '/fixtures', icon: Wrench, label: 'Fixtures', permission: 'Concord.Admin.Fixtures.View' },
    { to: '/codebases', icon: GitBranch, label: 'Codebases', permission: 'Concord.Admin.Codebases.View' },
    { to: '/validation/runs', icon: FlaskConical, label: 'Validation', permission: 'Concord.Admin.Validation.View' },
    { to: '/history', icon: History, label: 'History', permission: 'Concord.Admin.History.View' },
    { to: '/users', icon: Users, label: 'Users', permission: 'Concord.Admin.Users.View' },
  ];

  const visibleAdminItems = $derived(
    adminItems.filter(item => !item.permission || auth.hasPermission(item.permission))
  );

  const isAdmin = $derived(visibleAdminItems.length > 0);

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

{#snippet navLink(item: NavItem, exactMatch?: boolean)}
  {@const active = isActive(item.to, exactMatch)}
  <a
    href={item.to}
    ondblclick={onToggle}
    title={collapsed ? item.label : undefined}
    class="group relative flex items-center rounded-lg text-sm font-medium transition-all"
    class:justify-center={collapsed}
    class:px-0={collapsed}
    class:py-2={true}
    class:gap-3={!collapsed}
    class:px-3={!collapsed}
    class:bg-sidebar-active={active}
    class:text-accent={active}
    class:text-text-secondary={!active}
    class:hover:bg-sidebar-hover={!active}
    class:hover:text-text-primary={!active}
  >
    {#if active}
      <div class="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r bg-accent"></div>
    {/if}
    <item.icon size={18} strokeWidth={1.75} class="shrink-0" />
    {#if !collapsed}
      <span class="truncate">{item.label}</span>
    {/if}
  </a>
{/snippet}

<aside
  class="fixed inset-y-0 left-0 z-fixed flex flex-col border-r border-border bg-sidebar-bg transition-[width] duration-200 ease-out"
  style:width={collapsed ? 'var(--sidebar-collapsed-width)' : 'var(--sidebar-width)'}
>
  <div
    class="flex h-16 items-center"
    class:justify-center={collapsed}
    class:px-3={collapsed}
    class:justify-between={!collapsed}
    class:px-5={!collapsed}
  >
    {#if collapsed}
      <button
        onclick={onToggle}
        title="Expand sidebar"
        aria-label="Expand sidebar"
        class="flex flex-col items-center justify-center gap-1"
      >
        <ConcordLogo size={24} class="text-accent" />
        <img
          src={theme.theme === 'dark' ? '/assets/ck-logo.png' : '/assets/ck-logo-dark.png'}
          alt="CK"
          class="h-3 opacity-60"
        />
      </button>
    {:else}
      <div class="flex items-center gap-2.5">
        <ConcordLogo size={32} class="text-accent" />
        <div class="flex flex-col">
          <img
            src={theme.theme === 'dark' ? '/assets/corekinect-logo.png' : '/assets/corekinect-logo-dark.png'}
            alt="CoreKinect"
            class="h-4"
          />
        </div>
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

  <div class="border-t border-border" class:mx-2={collapsed} class:mx-4={!collapsed}></div>

  <div
    class="flex overflow-hidden rounded-lg bg-surface-2 p-0.5"
    class:mx-2={collapsed}
    class:mt-3={true}
    class:mx-4={!collapsed}
  >
    <button
      onclick={() => handleModeChange('manufacturing')}
      class="flex-1 min-w-0 truncate rounded-md text-center text-2xs font-medium transition-all"
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
      class="flex-1 min-w-0 truncate rounded-md text-center text-2xs font-medium transition-all"
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

  <nav
    class="flex-1 space-y-1 pt-4 pb-2"
    class:px-2={collapsed}
    class:px-3={!collapsed}
  >
    {#each navItems as item}
      {@render navLink(item, item.to === '/')}
    {/each}

    {#if isAdmin}
      <div class="pt-4">
        <div class="border-t border-border" class:mx-0={collapsed} class:mx-1={!collapsed}></div>
        <div class="pt-4">
          {#if !collapsed}
            <span class="mb-2 block px-3 text-2xs font-medium uppercase tracking-widest text-text-tertiary">
              Admin
            </span>
          {/if}

          {#each visibleAdminItems as item}
            {@render navLink(item)}
          {/each}
        </div>
      </div>
    {/if}
  </nav>

  <div
    class="border-t border-border space-y-1"
    class:p-2={collapsed}
    class:p-3={!collapsed}
  >
    <button
      onclick={onSettingsClick}
      ondblclick={onToggle}
      title={collapsed ? 'Settings' : undefined}
      class="group relative flex w-full items-center rounded-lg text-sm font-medium transition-all text-text-secondary hover:bg-sidebar-hover hover:text-text-primary"
      class:justify-center={collapsed}
      class:px-0={collapsed}
      class:py-2={true}
      class:gap-3={!collapsed}
      class:px-3={!collapsed}
    >
      <Settings size={18} strokeWidth={1.75} class="shrink-0" />
      {#if !collapsed}<span class="truncate">Settings</span>{/if}
    </button>

    {#if auth.user}
      <div
        class="mt-1 flex items-center rounded-lg"
        class:justify-center={collapsed}
        class:py-2={collapsed}
        class:gap-2={!collapsed}
        class:px-3={!collapsed}
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
            <LogOut size={16} strokeWidth={1.75} />
          </button>
        {/if}
      </div>
    {/if}

    {#if !collapsed && PUBLIC_APP_VERSION}
      <div class="px-3 pt-1 text-center">
        <span class="text-2xs text-text-tertiary opacity-50">v{PUBLIC_APP_VERSION}</span>
      </div>
    {/if}
  </div>
</aside>
