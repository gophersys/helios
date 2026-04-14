<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import {
    LayoutDashboard,
    FlaskConical,
    Hammer,
    Settings,
    Users,
    Cpu,
    Package,
    LogOut,
    PanelLeftClose,
    ChevronUp,
    Shield,
    Factory,
    ScanEye,
    History,
    BookOpen,
    Bug,
  } from 'lucide-svelte';
  import { PUBLIC_APP_VERSION, PUBLIC_APP_ENVIRONMENT } from '$env/static/public';
  import { getTheme } from '$lib/stores/theme.svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { getDocsUrl } from '$lib/docs';
  import { reportUserIssue } from '$lib/stores/error-reporter.svelte';

  import ConcordLogo from '$lib/components/concord-logo.svelte';
  import KubernetesIcon from '$lib/components/icons/kubernetes-icon.svelte';

  // Environment display
  const appEnv = PUBLIC_APP_ENVIRONMENT || 'development';
  const isProduction = appEnv === 'production';
  const isDev = appEnv === 'development' || appEnv === 'local' || !appEnv;
  const envConfig = (() => {
    if (appEnv === 'staging') return { label: 'STAGING', text: 'text-accent', bg: 'bg-accent-muted', dot: 'bg-accent' };
    if (isDev) return { label: 'DEV', text: 'text-warning', bg: 'bg-warning-muted', dot: 'bg-warning' };
    return { label: appEnv.toUpperCase(), text: 'text-warning', bg: 'bg-warning-muted', dot: 'bg-warning' };
  })();

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
  let viewAsOpen = $state(false);

  const VIEW_AS_ROLES = [
    { value: null,          label: 'Your View' },
    { value: 'MAINTAINER',  label: 'Maintainer' },
    { value: 'DEVELOPER',   label: 'Developer' },
    { value: 'OPERATOR',    label: 'Operator' },
  ] as const;

  // Primary navigation items
  const primaryItems: NavItem[] = [
    { to: '/products', icon: Package, label: 'Products', permission: 'products:view' },
    { to: '/builds', icon: Hammer, label: 'Builds', permission: 'builds:view' },
    { to: '/validation', icon: FlaskConical, label: 'Validation', permission: 'validation:view' },
    { to: '/manufacturing', icon: Factory, label: 'Manufacturing', permission: 'manufacturing:view' },
    { to: '/fixtures', icon: Cpu, label: 'Fixtures', permission: 'fixtures:view' },
  ];

  const visiblePrimaryItems = $derived(
    primaryItems.filter(item => !item.permission || auth.hasPermission(item.permission))
  );

  // Admin items
  const adminItems: NavItem[] = [
    { to: '/users', icon: Users, label: 'Users', permission: 'users:view' },
  ];

  const visibleAdminItems = $derived(
    adminItems.filter(item => !item.permission || auth.hasPermission(item.permission))
  );

  const hasAdmin = $derived(visibleAdminItems.length > 0);

  // System items
  const systemItems: NavItem[] = [
    { to: '/kubernetes', icon: KubernetesIcon, label: 'Kubernetes', permission: 'system:view' },
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

    <!-- Documentation -->
    <a
      href={getDocsUrl($page.url.pathname)}
      target="_blank"
      rel="noopener noreferrer"
      title={collapsed ? 'Documentation' : undefined}
      class="group relative flex w-full items-center rounded-lg text-sm font-medium transition-all text-text-secondary hover:bg-sidebar-hover hover:text-text-primary"
      class:justify-center={collapsed}
      class:px-0={collapsed}
      class:py-2={true}
      class:gap-3={!collapsed}
      class:px-3={!collapsed}
    >
      <BookOpen size={18} strokeWidth={1.75} class="shrink-0" />
      {#if !collapsed}<span class="truncate">Documentation</span>{/if}
    </a>

    <!-- Report Bug -->
    <button
      onclick={() => reportUserIssue({ message: 'User-reported issue', userNotes: '' })}
      title={collapsed ? 'Report Bug' : undefined}
      class="group relative flex w-full items-center rounded-lg text-sm font-medium transition-all text-text-secondary hover:bg-sidebar-hover hover:text-text-primary"
      class:justify-center={collapsed}
      class:px-0={collapsed}
      class:py-2={true}
      class:gap-3={!collapsed}
      class:px-3={!collapsed}
    >
      <Bug size={18} strokeWidth={1.75} class="shrink-0" />
      {#if !collapsed}<span class="truncate">Report Bug</span>{/if}
    </button>

    <!-- View As (Admin/Maintainer only, dev environment only) -->
    {#if isDev && auth.canViewAs && !collapsed}
      <div class="relative">
        <button
          onclick={() => (viewAsOpen = !viewAsOpen)}
          title="View as another role"
          class="group flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all text-text-secondary hover:bg-sidebar-hover hover:text-text-primary"
          class:bg-sidebar-active={auth.viewAsRole !== null}
          class:text-warning={auth.viewAsRole !== null}
        >
          <ScanEye size={18} strokeWidth={1.75} class="shrink-0" />
          <span class="flex-1 truncate text-left">
            {auth.viewAsRole ? `Viewing as ${auth.viewAsRole.charAt(0) + auth.viewAsRole.slice(1).toLowerCase()}` : 'View as...'}
          </span>
        </button>
        {#if viewAsOpen}
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div class="absolute bottom-full left-0 mb-1 w-full rounded-lg border border-border bg-surface-1 shadow-lg overflow-hidden z-50"
               onclick={() => (viewAsOpen = false)}>
            {#each VIEW_AS_ROLES as option}
              <button
                onclick={() => { auth.setViewAs(option.value); viewAsOpen = false; window.location.reload(); }}
                class="flex w-full items-center gap-2 px-3 py-2 text-sm text-left transition-colors hover:bg-surface-2"
                class:text-accent={auth.viewAsRole === option.value}
                class:font-medium={auth.viewAsRole === option.value}
                class:text-text-secondary={auth.viewAsRole !== option.value}
              >
                {#if auth.viewAsRole === option.value}
                  <span class="text-accent">&#10003;</span>
                {:else}
                  <span class="w-4"></span>
                {/if}
                {option.label}{#if option.value === null && auth.user} ({auth.user.role?.charAt(0)}{auth.user.role?.slice(1).toLowerCase()}){/if}
              </button>
            {/each}
          </div>
        {/if}
      </div>
    {/if}

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

    {#if !collapsed}
      <div class="px-3 pt-1 flex items-center justify-center gap-2">
        {#if !isProduction}
          <span class="inline-flex items-center gap-1.5 rounded-full {envConfig.bg} px-2 py-0.5 text-2xs font-medium {envConfig.text}">
            <span class="h-1.5 w-1.5 rounded-full {envConfig.dot}"></span>
            {envConfig.label}
          </span>
        {/if}
        {#if PUBLIC_APP_VERSION}
          <span class="text-2xs text-text-tertiary opacity-50">v{PUBLIC_APP_VERSION}</span>
        {/if}
      </div>
    {:else if !isProduction}
      <div class="flex justify-center pt-1 pb-1">
        <span class="h-2 w-2 rounded-full {envConfig.dot}" title="{envConfig.label}"></span>
      </div>
    {/if}
  </div>
</aside>
