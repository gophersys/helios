<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { Plus, Wrench, Search, Loader2, Wifi, WifiOff, AlertTriangle, Lock, Settings as SettingsIcon } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import { PageHeader, ErrorAlert, LoadingState } from '$lib/components/ui';
  import FilterBar from '$lib/components/ui/filter-bar.svelte';
  import FilterSelect from '$lib/components/ui/filter-select.svelte';
  import FilterSearch from '$lib/components/ui/filter-search.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import FixtureDetail from '$lib/components/fixtures/fixture-detail.svelte';
  import type { Fixture, Product, Board, FixtureDesign } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('fixtures:manage'));

  // Data
  let fixtures = $state<Fixture[]>([]);
  let products = $state<Product[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Filters
  let filterProduct = $state('');
  let filterType = $state('');
  let filterStatus = $state('');
  let searchQuery = $state('');

  // Detail
  let selectedFixture = $state<Fixture | null>(null);

  // Create form
  let showCreate = $state(false);
  let boards = $state<Board[]>([]);
  let availableDesigns = $state<FixtureDesign[]>([]);
  let formName = $state('');
  let formProductId = $state('');
  let formBoardRevisionId = $state('');
  let formDesignId = $state('');
  let formType = $state('VALIDATION');
  let formDescription = $state('');
  let submitting = $state(false);

  const boardRevisions = $derived.by(() => {
    const revs: { id: string; label: string }[] = [];
    for (const board of boards) {
      for (const rev of board.revisions ?? []) {
        revs.push({ id: rev.id, label: `${rev.version} (${rev.ckBoardsName || board.name})` });
      }
    }
    return revs;
  });

  const designOptions = $derived(
    availableDesigns.map(d => ({ value: d.id, label: `${d.name} (${d.revision})` }))
  );

  const filtered = $derived(
    fixtures.filter(f => {
      if (filterProduct && f.productId !== filterProduct) return false;
      if (filterType && f.type !== filterType) return false;
      if (filterStatus) {
        const slots = f.slots || [];
        const assigned = slots.filter(s => s.nodeId).length;
        if (filterStatus === 'AVAILABLE' && (assigned === 0 || slots.length === 0)) return false;
        if (filterStatus === 'UNASSIGNED' && assigned > 0) return false;
      }
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        if (!f.name.toLowerCase().includes(q) && !(f.productName || '').toLowerCase().includes(q)) return false;
      }
      return true;
    })
  );

  async function fetchFixtures() {
    try {
      const res = await apiFetch<ApiResponse<{ data: Fixture[] }>>('/v2/fixtures?limit=200');
      const payload = res.data;
      fixtures = Array.isArray(payload) ? payload : (payload as any)?.data || [];
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load fixtures';
    } finally {
      loading = false;
    }
  }

  async function fetchProducts() {
    try {
      const res = await apiFetch<ApiResponse<{ data: Product[] }>>('/v2/products');
      const payload = res.data;
      products = Array.isArray(payload) ? payload : (payload as any)?.data || [];
    } catch { /* non-critical */ }
  }

  async function fetchBoardsForProduct(pid: string) {
    if (!pid) { boards = []; return; }
    try {
      const res = await apiFetch<ApiResponse<Product>>(`/v2/products/${pid}`);
      boards = res.data.boards ?? [];
    } catch { boards = []; }
  }

  async function fetchDesignsForRevision(revId: string) {
    if (!revId) { availableDesigns = []; return; }
    try {
      const res = await apiFetch<ApiResponse<{ data: FixtureDesign[] }>>(`/v2/fixtures/designs?boardRevisionId=${revId}`);
      const payload = res.data;
      availableDesigns = Array.isArray(payload) ? payload : (payload as any)?.data || [];
    } catch { availableDesigns = []; }
  }

  $effect(() => { if (formProductId) fetchBoardsForProduct(formProductId); else boards = []; });
  $effect(() => { if (formBoardRevisionId) fetchDesignsForRevision(formBoardRevisionId); else { availableDesigns = []; formDesignId = ''; } });

  async function fetchDetail(id: string) {
    try {
      const res = await apiFetch<ApiResponse<Fixture>>(`/v2/fixtures/${id}`);
      selectedFixture = res.data;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load fixture';
    }
  }

  async function handleCreate(e: Event) {
    e.preventDefault();
    if (!formDesignId) { error = 'Fixture design is required'; return; }
    submitting = true;
    error = null;
    try {
      await api.post('/v2/fixtures', {
        name: formName,
        productId: formProductId,
        boardRevisionId: formBoardRevisionId || null,
        designId: formDesignId,
        type: formType,
        description: formDescription || null,
      });
      showCreate = false;
      formName = ''; formProductId = ''; formBoardRevisionId = ''; formDesignId = ''; formDescription = '';
      await fetchFixtures();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to create fixture';
    } finally {
      submitting = false;
    }
  }

  function slotSummary(f: Fixture): string {
    if (f.slots) {
      const assigned = f.slots.filter(s => s.nodeId).length;
      return `${assigned}/${f.slots.length}`;
    }
    if (f.assignedCount !== undefined && f.slotCount !== undefined) {
      return `${f.assignedCount}/${f.slotCount}`;
    }
    return `${f.slotCount ?? 0}`;
  }

  function healthIcon(f: Fixture) {
    const slots = f.slots || [];
    if (slots.length === 0 && !f.slotCount) return { icon: WifiOff, color: 'text-text-tertiary' };
    if (slots.length === 0) return { icon: WifiOff, color: 'text-text-tertiary' };
    const assigned = slots.filter(s => s.nodeId);
    if (assigned.length === 0) return { icon: WifiOff, color: 'text-text-tertiary' };
    const online = assigned.filter(s => s.node?.status === 'ONLINE').length;
    if (online === assigned.length) return { icon: Wifi, color: 'text-success' };
    if (online > 0) return { icon: AlertTriangle, color: 'text-warning' };
    return { icon: WifiOff, color: 'text-error' };
  }

  onMount(() => {
    if (!auth.hasPermission('fixtures:view') && !auth.hasPermission('manufacturing:view')) {
      goto('/');
      return;
    }
    fetchFixtures();
    fetchProducts();

    // Auto-open detail panel if ?selected=<id> is in the URL (e.g. from dashboard)
    const selectedId = $page.url.searchParams.get('selected');
    if (selectedId) {
      fetchDetail(selectedId);
    }
  });
</script>

<svelte:head>
  <title>Fixtures — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <PageHeader title="Fixtures" description="Physical test stations and MTIB assignments.">
    {#snippet actions()}
      {#if canManage}
        <button
          onclick={() => showCreate = !showCreate}
          class="btn btn-sm btn-primary"
        >
          {#if showCreate}Cancel{:else}<Plus size={16} /> New Fixture{/if}
        </button>
      {/if}
    {/snippet}
  </PageHeader>

  <ErrorAlert message={error} />

  <!-- Create form -->
  {#if showCreate}
    <form onsubmit={handleCreate} class="mb-6 card card-sm space-y-3">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <label class="block">
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Name</span>
          <input type="text" required bind:value={formName} placeholder="Alpha B0 Bench 1" class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary" />
        </label>
        <label class="block">
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Product</span>
          <Select bind:value={formProductId} placeholder="Select product" options={products.map(p => ({ value: p.id, label: p.name }))} />
        </label>
        <label class="block">
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Board Revision</span>
          <Select bind:value={formBoardRevisionId} placeholder="Select revision" options={boardRevisions.map(r => ({ value: r.id, label: r.label }))} />
        </label>
        <label class="block">
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Fixture Design</span>
          <Select bind:value={formDesignId} placeholder="Select design (required)" options={designOptions} />
        </label>
        <label class="block">
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Type</span>
          <Select bind:value={formType} options={[{ value: 'VALIDATION', label: 'Validation' }, { value: 'MANUFACTURING', label: 'Manufacturing' }]} />
        </label>
        <div class="flex items-end">
          <button type="submit" disabled={submitting || !formDesignId} class="btn btn-sm btn-primary">
            {submitting ? 'Creating...' : 'Create'}
          </button>
        </div>
      </div>
    </form>
  {/if}

  <!-- Filters -->
  <FilterBar class="mb-4">
    {#snippet filters()}
      <FilterSearch bind:value={searchQuery} placeholder="Search fixtures..." class="w-56" />
      {#if products.length > 0}
        <FilterSelect label="Product" value={filterProduct} onchange={(v) => { filterProduct = v; }} options={products.map(p => ({ value: p.id, label: p.name }))} />
      {/if}
      <FilterSelect label="Type" value={filterType} onchange={(v) => { filterType = v; }} options={[{ value: 'VALIDATION', label: 'Validation' }, { value: 'MANUFACTURING', label: 'Manufacturing' }]} />
    {/snippet}
  </FilterBar>

  <!-- Fixture list -->
  {#if loading}
    <LoadingState message="Loading fixtures..." />
  {:else if filtered.length === 0}
    <div class="rounded-lg border border-dashed border-border bg-surface-1 p-12 text-center">
      <Wrench size={32} class="mx-auto mb-3 text-text-tertiary opacity-30" />
      <p class="text-sm text-text-secondary">
        {fixtures.length === 0 ? 'No fixtures registered' : 'No fixtures match your filters'}
      </p>
    </div>
  {:else}
    <div class="rounded-lg border border-border overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-border bg-surface-0/50">
            <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Name</th>
            <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Product</th>
            <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Type</th>
            <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Design</th>
            <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Slots</th>
            <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Health</th>
            <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Revision</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-border-subtle">
          {#each filtered as fixture}
            {@const health = healthIcon(fixture)}
            <tr
              class="hover:bg-surface-0/50 cursor-pointer transition-colors"
              onclick={() => fetchDetail(fixture.id)}
            >
              <td class="px-4 py-2.5">
                <span class="font-medium text-text-primary">{fixture.name}</span>
              </td>
              <td class="px-4 py-2.5 text-text-secondary">{fixture.productName || '—'}</td>
              <td class="px-4 py-2.5">
                <StatusBadge status={fixture.type} />
              </td>
              <td class="px-4 py-2.5 text-2xs text-text-tertiary">
                {fixture.design?.name || '—'}
              </td>
              <td class="px-4 py-2.5">
                <span class="font-mono text-text-secondary">{slotSummary(fixture)}</span>
                <span class="text-2xs text-text-tertiary ml-1">assigned</span>
              </td>
              <td class="px-4 py-2.5">
                <svelte:component this={health.icon} size={14} class={health.color} />
              </td>
              <td class="px-4 py-2.5 text-2xs text-text-tertiary">
                {fixture.boardRevision?.version || '—'}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  <!-- Detail panel -->
  {#if selectedFixture}
    <div class="fixed inset-0 z-50 flex">
      <button onclick={() => selectedFixture = null} class="absolute inset-0 bg-black/30"></button>
      <div class="relative ml-auto w-full max-w-2xl bg-surface-1 border-l border-border overflow-y-auto p-6">
        <button onclick={() => selectedFixture = null} class="absolute top-4 right-4 text-text-tertiary hover:text-text-primary">✕</button>
        <FixtureDetail
          fixture={selectedFixture}
          {canManage}
          onRefresh={() => { fetchDetail(selectedFixture!.id); fetchFixtures(); }}
        />
      </div>
    </div>
  {/if}
</div>
