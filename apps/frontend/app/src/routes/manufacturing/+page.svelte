<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { Plus, RefreshCw } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch } from '$lib/api';
  import type { ManufacturingSession, Product, Pagination } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import PageHeader from '$lib/components/ui/page-header.svelte';
  import FilterBar from '$lib/components/ui/filter-bar.svelte';
  import FilterSelect from '$lib/components/ui/filter-select.svelte';
  import FilterSearch from '$lib/components/ui/filter-search.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import EmptyState from '$lib/components/ui/empty-state.svelte';
  import PaginationNav from '$lib/components/ui/pagination.svelte';
  import SessionCard from '$lib/components/manufacturing/session-card.svelte';
  import SessionCreateWizard from '$lib/components/manufacturing/session-create-wizard.svelte';

  const auth = getAuth();
  const canRun = $derived(auth.hasPermission('manufacturing:run'));

  // Data
  let sessions = $state<ManufacturingSession[]>([]);
  let pagination = $state<Pagination>({ page: 1, limit: 25, total: 0, pages: 0 });
  let loading = $state(true);
  let error = $state<string | null>(null);
  let currentPage = $state(1);
  let refreshing = $state(false);

  // Filters
  let productFilter = $state('');
  let statusFilter = $state('');
  let searchQuery = $state('');
  let productOptions = $state<{ value: string; label: string }[]>([]);

  // Create wizard
  let showCreateWizard = $state(false);

  // Auto-refresh
  let refreshInterval: ReturnType<typeof setInterval> | null = null;

  // Client-side search filtering
  const filteredSessions = $derived.by(() => {
    if (!searchQuery.trim()) return sessions;
    const q = searchQuery.toLowerCase();
    return sessions.filter(s =>
      s.product?.name?.toLowerCase().includes(q) ||
      s.fixture?.name?.toLowerCase().includes(q) ||
      s.operator?.name?.toLowerCase().includes(q)
    );
  });

  const STATUS_OPTIONS = [
    { value: 'ACTIVE', label: 'Active' },
    { value: 'COMPLETED', label: 'Completed' },
    { value: 'CANCELLED', label: 'Cancelled' },
  ];

  async function fetchSessions(): Promise<void> {
    try {
      const params = new URLSearchParams();
      params.set('page', String(currentPage));
      params.set('limit', '25');
      if (productFilter) params.set('productId', productFilter);
      if (statusFilter) params.set('status', statusFilter);

      const res = await apiFetch<ApiResponse<{ data: ManufacturingSession[]; pagination: Pagination }>>(
        `/v2/manufacturing/sessions?${params.toString()}`
      );

      const payload = res.data;
      sessions = Array.isArray(payload) ? payload : (payload as any)?.data || [];
      if ((payload as any)?.pagination) {
        pagination = (payload as any).pagination;
      }

      // Extract unique products for filter dropdown
      if (productOptions.length === 0 && sessions.length > 0) {
        const prods = new Map<string, string>();
        sessions.forEach(s => {
          if (s.product?.id && s.product?.name) prods.set(s.product.id, s.product.name);
        });
        productOptions = Array.from(prods.entries())
          .sort((a, b) => a[1].localeCompare(b[1]))
          .map(([id, name]) => ({ value: id, label: name }));
      }
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load manufacturing sessions';
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  async function fetchProducts(): Promise<void> {
    try {
      const res = await apiFetch<ApiResponse<{ data: Product[] }>>('/v2/products');
      const payload = res.data;
      const prodList = Array.isArray(payload) ? payload : (payload as any)?.data || [];
      productOptions = prodList.map((p: Product) => ({ value: p.id, label: p.name }));
    } catch {
      /* non-critical */
    }
  }

  function refresh(): void {
    refreshing = true;
    fetchSessions();
  }

  onMount(() => {
    if (!auth.hasPermission('manufacturing:view')) {
      goto('/');
      return;
    }
    fetchSessions();
    fetchProducts();
    refreshInterval = setInterval(() => fetchSessions(), 10000);
  });

  onDestroy(() => {
    if (refreshInterval) clearInterval(refreshInterval);
  });

  $effect(() => { const _p = currentPage; fetchSessions(); });
  $effect(() => {
    const _pf = productFilter;
    const _sf = statusFilter;
    currentPage = 1;
  });
</script>

<svelte:head>
  <title>Manufacturing — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6 flex items-start justify-between">
    <PageHeader
      title="Manufacturing"
      description="Track and manage manufacturing runs across your products."
    />
    <div class="flex items-center gap-2">
      <button onclick={refresh} disabled={refreshing} class="btn btn-sm flex items-center gap-1.5" title="Refresh">
        <RefreshCw size={14} class={refreshing ? 'animate-spin' : ''} />
      </button>
      {#if canRun}
        <button onclick={() => showCreateWizard = true} class="btn btn-sm btn-primary">
          <Plus size={16} /> New Session
        </button>
      {/if}
    </div>
  </div>

  <ErrorAlert message={error} />

  <!-- Filter bar -->
  <FilterBar class="mb-4">
    {#snippet filters()}
      <FilterSelect label="Product" value={productFilter} onchange={(v) => { productFilter = v; }} options={productOptions} />
      <FilterSelect label="Status" value={statusFilter} onchange={(v) => { statusFilter = v; }} options={STATUS_OPTIONS} />
      <FilterSearch bind:value={searchQuery} placeholder="Search sessions..." class="w-56" />
    {/snippet}
    <span class="ml-auto text-2xs text-text-tertiary shrink-0">
      {pagination.total} sessions
    </span>
  </FilterBar>

  <!-- Session list -->
  {#if loading}
    <LoadingState message="Loading manufacturing sessions..." />
  {:else if filteredSessions.length === 0}
    {@const hasFilters = searchQuery || productFilter || statusFilter}
    <EmptyState message={hasFilters ? 'No sessions match your filters.' : 'No manufacturing sessions yet.'}>
      {#if !hasFilters}
        <p class="text-2xs text-text-tertiary mt-1">Start a new session to begin manufacturing.</p>
      {/if}
    </EmptyState>
  {:else}
    <div class="divide-y divide-border-subtle rounded-lg border border-border bg-surface-0">
      {#each filteredSessions as session (session.id)}
        <SessionCard {session} />
      {/each}
    </div>
  {/if}

  <!-- Pagination -->
  {#if pagination.pages > 1}
    <div class="mt-4 flex items-center justify-between">
      <span class="text-2xs text-text-tertiary">
        Page {pagination.page} of {pagination.pages}
      </span>
      <PaginationNav
        page={pagination.page}
        totalPages={pagination.pages}
        onPageChange={(p) => { currentPage = p; }}
      />
    </div>
  {/if}
</div>

<SessionCreateWizard
  open={showCreateWizard}
  onClose={() => showCreateWizard = false}
  onStarted={(id) => {
    showCreateWizard = false;
    goto(`/manufacturing/session/${id}`);
  }}
/>
