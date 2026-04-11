<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    Package, Hammer, FlaskConical, Factory, Wrench,
    Wifi, AlertTriangle, ArrowRight, Activity,
  } from 'lucide-svelte';
  import { PageHeader, LoadingState, ErrorAlert } from '$lib/components/ui';
  import DashboardFixtureCard from '$lib/components/dashboard/dashboard-fixture-card.svelte';
  import RecentActivity from '$lib/components/dashboard/recent-activity.svelte';
  import { apiFetch } from '$lib/api';
  import { getAuth } from '$lib/stores/auth.svelte';
  import type { ApiResponse } from '$lib/types';
  import type { AuditEntry, DashboardData, DashboardFixture, DashboardStats } from '$lib/types/models';

  const auth = getAuth();

  let data = $state<DashboardData | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let pollTimer: ReturnType<typeof setInterval> | undefined;
  let activityEntries = $state<AuditEntry[]>([]);
  let activityLoading = $state(true);

  const stats = $derived(data?.stats ?? {});
  const fixtures = $derived(data?.fixtures ?? []);
  const role = $derived(auth.effectiveRole);

  // Filter fixtures by mode toggle (manufacturing vs validation)
  const mode = $derived.by(() => {
    if (typeof localStorage === 'undefined') return 'MANUFACTURING';
    const stored = localStorage.getItem('concord-mode');
    return stored === 'validation' ? 'VALIDATION' : 'MANUFACTURING';
  });

  const filteredFixtures = $derived(
    fixtures
      .filter(f => f.type === mode)
      .sort((a, b) => {
        const pa = a.productName || '';
        const pb = b.productName || '';
        if (pa !== pb) return pa.localeCompare(pb);
        return a.name.localeCompare(b.name);
      })
  );

  async function fetchDashboard() {
    try {
      const res = await apiFetch<ApiResponse<DashboardData>>('/v2/dashboard/overview');
      data = res.data;
      error = null;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load dashboard';
    } finally {
      loading = false;
    }

    if (auth.hasPermission('system:view')) {
      try {
        const histRes = await apiFetch<ApiResponse<{ data: AuditEntry[] }>>('/v2/system/history?limit=10');
        activityEntries = histRes.data.data ?? [];
      } catch { /* non-critical */ }
      activityLoading = false;
    } else {
      activityLoading = false;
    }
  }

  onMount(() => {
    fetchDashboard();
    pollTimer = setInterval(fetchDashboard, 15000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });

  function handleFixtureClick(fixtureId: string) {
    goto(`/fixtures?selected=${fixtureId}`);
  }

  // Pipeline section config — which sections exist and what they link to
  const sections = $derived.by(() => {
    const p = stats as DashboardStats;
    const items: Array<{
      key: string;
      label: string;
      icon: typeof Package;
      href: string;
      stat: string;
      detail: string;
      color: string;
      visible: boolean;
    }> = [
      {
        key: 'products',
        label: 'Products',
        icon: Package,
        href: '/products',
        stat: p.products ? String(p.products.total) : '—',
        detail: p.products ? `${p.products.active} active` : '',
        color: 'text-accent',
        visible: !!p.products,
      },
      {
        key: 'builds',
        label: 'Builds',
        icon: Hammer,
        href: '/builds',
        stat: p.builds ? String(p.builds.total) : '—',
        detail: p.builds?.active ? `${p.builds.active} running` : p.builds?.failed ? `${p.builds.failed} failed` : 'none running',
        color: 'text-accent',
        visible: !!p.builds,
      },
      {
        key: 'validation',
        label: 'Validation',
        icon: FlaskConical,
        href: '/validation',
        stat: p.validation ? String(p.validation.total) : '—',
        detail: p.validation?.passRate != null ? `${p.validation.passRate}% pass rate` : p.validation?.active ? `${p.validation.active} active` : 'no runs yet',
        color: 'text-accent',
        visible: !!p.validation,
      },
      {
        key: 'manufacturing',
        label: 'Manufacturing',
        icon: Factory,
        href: '/manufacturing',
        stat: p.manufacturing ? String(p.manufacturing.total) : '—',
        detail: p.manufacturing?.active ? `${p.manufacturing.active} active` : 'none',
        color: 'text-accent',
        visible: !!p.manufacturing,
      },
      {
        key: 'fixtures',
        label: 'Fixtures',
        icon: Wrench,
        href: '/fixtures',
        stat: p.fixtures ? String(p.fixtures.total) : '—',
        detail: p.fixtures?.online ? `${p.fixtures.online} online` : p.fixtures ? 'none online' : '',
        color: 'text-accent',
        visible: !!p.fixtures,
      },
    ];
    return items.filter(i => i.visible);
  });

  // Empty state: what the user should do next (gated by manage permissions, not just view)
  const hasProducts = $derived((stats as DashboardStats).products?.total ?? 0 > 0);

  const setupSteps = $derived.by(() => {
    const p = stats as DashboardStats;
    const can = (perm: string) => auth.hasPermission(perm);
    const productsDone = (p.products?.total ?? 0) > 0;
    const steps: Array<{ label: string; done: boolean; href: string; visible: boolean; locked: boolean }> = [
      { label: 'Create your first product', done: productsDone, href: '/products', visible: can('products:manage'), locked: false },
      { label: 'Configure build stages', done: (p.builds?.total ?? 0) > 0, href: '/builds', visible: can('builds:manage'), locked: !productsDone },
      { label: 'Run validation', done: (p.validation?.total ?? 0) > 0, href: '/validation', visible: can('validation:run') || can('validation:manage'), locked: !productsDone },
      { label: 'Register test fixtures', done: (p.fixtures?.total ?? 0) > 0, href: '/fixtures', visible: can('fixtures:manage'), locked: !productsDone },
      { label: 'Set up manufacturing', done: (p.manufacturing?.total ?? 0) > 0, href: '/manufacturing', visible: can('manufacturing:manage'), locked: !productsDone },
    ];
    return steps.filter(s => s.visible);
  });

  const allSetUp = $derived(setupSteps.length > 0 && setupSteps.every(s => s.done));
  const nothingConfigured = $derived(setupSteps.length > 0 && setupSteps.every(s => !s.done));
</script>

<svelte:head>
  <title>Dashboard — Concord</title>
</svelte:head>

<div class="animate-fade-in space-y-6">
  <PageHeader
    title="Dashboard"
    description={role === 'OPERATOR'
      ? 'Manufacturing overview.'
      : role === 'DEVELOPER'
        ? 'Build and validation overview.'
        : 'Concord platform overview.'}
  />

  {#if loading}
    <LoadingState message="Loading dashboard..." />
  {:else if error}
    <ErrorAlert message={error} />
  {:else}
    <!-- Pipeline stat cards -->
    {#if sections.length > 0}
      <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-5">
        {#each sections as section}
          <a
            href={section.href}
            class="card card-sm flex items-center gap-3 transition-colors hover:border-accent/40"
          >
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent-muted">
              <svelte:component this={section.icon} size={20} class="text-accent" />
            </div>
            <div class="min-w-0">
              <p class="text-2xl font-semibold text-text-primary">{section.stat}</p>
              <p class="truncate text-2xs text-text-tertiary">{section.label} · {section.detail}</p>
            </div>
          </a>
        {/each}
      </div>
    {/if}

    <!-- Setup checklist (when platform is mostly empty) -->
    {#if nothingConfigured}
      <div class="card card-lg">
        <div class="mb-4 flex items-center gap-2">
          <Activity size={18} class="text-accent" />
          <h2 class="text-sm font-semibold text-text-primary">Get started</h2>
        </div>
        {#if role === 'OPERATOR'}
          <p class="text-sm text-text-secondary">
            No manufacturing stations are configured yet. Contact your administrator to set up products, fixtures, and manufacturing stages.
          </p>
        {:else}
          <div class="space-y-1">
            {#each setupSteps as step}
              {#if step.locked}
                <div
                  class="flex items-center gap-3 rounded-lg px-3 py-2 text-sm opacity-40 cursor-not-allowed"
                  title="Create a product first"
                >
                  <div class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-border">
                  </div>
                  <span class="text-text-tertiary">{step.label}</span>
                </div>
              {:else}
                <a
                  href={step.href}
                  class="flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors hover:bg-surface-2"
                >
                  <div class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border {step.done ? 'border-success bg-success-muted' : 'border-accent bg-accent-muted'}">
                    {#if step.done}
                      <span class="text-2xs text-success">✓</span>
                    {:else}
                      <span class="text-2xs text-accent">→</span>
                    {/if}
                  </div>
                  <span class="text-text-secondary">{step.label}</span>
                  <ArrowRight size={14} class="ml-auto text-text-tertiary" />
                </a>
              {/if}
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    <!-- Fixture grid (when there are fixtures to show) -->
    {#if filteredFixtures.length > 0}
      <div>
        <h2 class="mb-3 text-sm font-semibold text-text-primary">
          {mode === 'MANUFACTURING' ? 'Manufacturing' : 'Validation'} Fixtures
        </h2>
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {#each filteredFixtures as fixture (fixture.id)}
            <DashboardFixtureCard
              {fixture}
              onclick={() => handleFixtureClick(fixture.id)}
            />
          {/each}
        </div>
      </div>
    {/if}

    {#if auth.hasPermission('system:view')}
      <div>
        <RecentActivity entries={activityEntries} loading={activityLoading} />
      </div>
    {/if}
  {/if}
</div>
