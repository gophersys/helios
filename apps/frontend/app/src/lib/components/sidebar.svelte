<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import {
    LayoutDashboard,
    FlaskConical,
    Hammer,
    Wrench,
    Settings,
    Users,
    Cpu,
    Package,
    History,
    LogOut,
    PanelLeftClose,
    ChevronUp,
    Shield,
    LineChart,
  } from 'lucide-svelte';
  import { PUBLIC_APP_VERSION } from '$env/static/public';
  import { getTheme } from '$lib/stores/theme.svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import ConcordLogo from '$lib/components/concord-logo.svelte';
  import KubernetesIcon from '$lib/components/icons/kubernetes-icon.svelte';

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  type IconComponent = any;

  interface NavItem {
    to: string;
    icon: IconComponent;
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

  let adminExpanded = $state(false);
  let systemExpanded = $state(false);

  // Primary navigation items
  const primaryItems: NavItem[] = [
    { to: '/products', icon: Package, label: 'Products', permission: 'products:view' },
    { to: '/builds', icon: Hammer, label: 'Builds', permission: 'builds:view' },
    { to: '/validation', icon: FlaskConical, label: 'Validation' },
    { to: '/mtib', icon: Cpu, label: 'Hardware', permission: 'devices:view' },
  ];

  const visiblePrimaryItems = $derived(
    primaryItems.filter(item => !item.permission || auth.hasPermission(item.permission))
  );

  // Admin items
  const adminItems: NavItem[] = [
    { to: '/fixtures', icon: Wrench, label: 'Fixtures' },
    { to: '/users', icon: Users, label: 'Users & Permissions', permission: 'users:view' },
    { to: '/case-study', icon: LineChart, label: 'Case Study', permission: 'system:view' },
  ];

  const visibleAdminItems = $derived(
    adminItems.filter(item => !item.permission || auth.hasPermission(item.permission))
  );

  const hasAdmin = $derived(visibleAdminItems.length > 0);

  // System items
  const systemItems: NavItem[] = [
    { to: '/kubernetes', icon: KubernetesIcon, label: 'Cluster', permission: 'system:view' },
    { to: '/history', icon: History, label: 'History', permission: 'system:view' },
  ];

  const visibleSystemItems = $derived(
    systemItems.filter(item => !item.permission || auth.hasPermission(item.permission))
  );

  const hasSystem = $derived(visibleSystemItems.length > 0);

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
      <span class="flex-1 truncate">{item.label}</span>
    {/if}
  </a>
{/snippet}

{#snippet sectionToggle(label: string, icon: IconComponent, expanded: boolean, toggle: () => void)}
  <button
    onclick={toggle}
    title={collapsed ? (expanded ? `Hide ${label}` : `Show ${label}`) : undefined}
    class="group relative flex w-full items-center rounded-lg text-sm font-medium transition-all"
    class:justify-center={collapsed}
    class:px-0={collapsed}
    class:py-2={true}
    class:gap-3={!collapsed}
    class:px-3={!collapsed}
    class:bg-sidebar-active={expanded}
    class:text-accent={expanded}
    class:text-text-secondary={!expanded}
    class:hover:bg-sidebar-hover={!expanded}
    class:hover:text-text-primary={!expanded}
  >
    {#if expanded}
      <div class="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r bg-accent"></div>
    {/if}
    {#if true}{@const Icon = icon}<Icon size={18} strokeWidth={1.75} class="shrink-0" />{/if}
    {#if !collapsed}
      <span class="flex-1 truncate">{label}</span>
      <ChevronUp
        size={14}
        class="shrink-0 transition-transform duration-200 {expanded ? '' : 'rotate-180'}"
      />
    {/if}
  </button>
{/snippet}

<aside
  class="fixed inset-y-0 left-0 z-fixed flex flex-col border-r border-border bg-sidebar-bg transition-[width] duration-200 ease-out"
  style:width={collapsed ? 'var(--sidebar-collapsed-width)' : 'var(--sidebar-width)'}
>
  <!-- Logo -->
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

  <!-- Primary Navigation -->
  <nav
    class="space-y-1 pt-4"
    class:px-2={collapsed}
    class:px-3={!collapsed}
  >
    <!-- Dashboard always visible -->
    {@render navLink({ to: '/', icon: LayoutDashboard, label: 'Dashboard' }, true)}

    <!-- Primary items -->
    {#each visiblePrimaryItems as item}
      {@render navLink(item)}
    {/each}
  </nav>

  <!-- Spacer -->
  <div class="flex-1"></div>

  <!-- System Section (expands upward) -->
  {#if hasSystem && systemExpanded}
    <div
      class="border-t border-border space-y-1 overflow-hidden transition-all duration-200"
      class:px-2={collapsed}
      class:px-3={!collapsed}
      class:py-3={true}
    >
      {#if !collapsed}
        <span class="px-3 pb-1 block text-2xs font-medium uppercase tracking-widest text-text-tertiary">
          System
        </span>
      {/if}
      {#each visibleSystemItems as item}
        {@render navLink(item)}
      {/each}
    </div>
  {/if}

  <!-- Admin Section (expands upward) -->
  {#if hasAdmin && adminExpanded}
    <div
      class="border-t border-border space-y-1 overflow-hidden transition-all duration-200"
      class:px-2={collapsed}
      class:px-3={!collapsed}
      class:py-3={true}
    >
      {#if !collapsed}
        <span class="px-3 pb-1 block text-2xs font-medium uppercase tracking-widest text-text-tertiary">
          Admin
        </span>
      {/if}
      {#each visibleAdminItems as item}
        {@render navLink(item)}
      {/each}
    </div>
  {/if}

  <!-- Footer: Section toggles, Settings, User -->
  <div
    class="border-t border-border space-y-1"
    class:p-2={collapsed}
    class:p-3={!collapsed}
  >
    <!-- System Toggle Button -->
    {#if hasSystem}
      {@render sectionToggle('System', KubernetesIcon, systemExpanded, () => (systemExpanded = !systemExpanded))}
    {/if}

    <!-- Admin Toggle Button -->
    {#if hasAdmin}
      {@render sectionToggle('Admin', Shield, adminExpanded, () => (adminExpanded = !adminExpanded))}
    {/if}

    <!-- Settings -->
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

    <!-- User -->
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
