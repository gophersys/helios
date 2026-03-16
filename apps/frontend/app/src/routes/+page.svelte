<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { browser } from '$app/environment';
  import { PageHeader, LoadingState, ErrorAlert } from '$lib/components/ui';
  import DashboardSummary from '$lib/components/dashboard/dashboard-summary.svelte';
  import DashboardFixtureCard from '$lib/components/dashboard/dashboard-fixture-card.svelte';
  import { apiFetch } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { DashboardFixture } from '$lib/types/models';

  let fixtures = $state<DashboardFixture[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let pollTimer: ReturnType<typeof setInterval> | undefined;

  // Read mode from localStorage (shared with sidebar)
  const mode = $derived.by(() => {
    if (!browser) return 'MANUFACTURING';
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

  async function fetchOverview() {
    try {
      const res = await apiFetch<ApiResponse<DashboardFixture[]>>('/v2/dashboard/overview');
      fixtures = res.data;
      error = null;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load dashboard';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    fetchOverview();
    pollTimer = setInterval(fetchOverview, 15000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });

  function handleFixtureClick(fixtureId: string) {
    goto(`/fixtures?selected=${fixtureId}`);
  }
</script>

<svelte:head>
  <title>Dashboard — Concord</title>
</svelte:head>

<div class="animate-fade-in space-y-6">
  <PageHeader
    title="Dashboard"
    description="Overview of your Concord system."
  />

  {#if loading}
    <LoadingState message="Loading dashboard..." />
  {:else if error}
    <ErrorAlert message={error} />
  {:else if fixtures.length === 0}
    <div class="rounded-xl border border-dashed border-border bg-surface-1 p-16">
      <p class="text-center text-sm text-text-tertiary">
        No fixtures configured yet. Create fixtures in the Fixtures page to get started.
      </p>
    </div>
  {:else}
    <DashboardSummary fixtures={filteredFixtures} />

    {#if filteredFixtures.length === 0}
      <div class="rounded-xl border border-dashed border-border bg-surface-1 p-12">
        <p class="text-center text-sm text-text-tertiary">
          No {mode.toLowerCase()} fixtures found. Switch modes or create fixtures to see them here.
        </p>
      </div>
    {:else}
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {#each filteredFixtures as fixture (fixture.id)}
          <DashboardFixtureCard
            {fixture}
            onclick={() => handleFixtureClick(fixture.id)}
          />
        {/each}
      </div>
    {/if}
  {/if}
</div>
