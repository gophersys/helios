<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    ChevronDown,
    ChevronRight,
    ChevronLeft,
    ChevronsLeft,
    ChevronsRight,
    GitCompareArrows,
    Plus,
    Package,
    CheckCircle2,
    XCircle,
    Clock,
    Loader2,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import type { ValidationRun, Product, Pagination } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import { formatTimeAgo, formatDateTime, formatDuration } from '$lib/utils/formatting';
  import EmptyState from '$lib/components/ui/empty-state.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import FormCard from '$lib/components/ui/form-card.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import TextInput from '$lib/components/ui/text-input.svelte';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('Concord.Admin.Validation.Manage'));

  const STATUS_OPTIONS = [
    { value: 'ACTIVE', label: 'Active' },
    { value: 'COMPLETED', label: 'Completed' },
    { value: 'CANCELLED', label: 'Cancelled' },
    { value: 'PAUSED', label: 'Paused' },
  ];

  const VARIANT_OPTIONS = [
    { value: 'debug', label: 'Debug' },
    { value: 'release', label: 'Release' },
    { value: 'mfg', label: 'Manufacturing' },
  ];

  // List state
  let runs = $state<ValidationRun[]>([]);
  let pagination = $state<Pagination>({ page: 1, limit: 100, total: 0, pages: 0 });
  let loading = $state(true);
  let error = $state<string | null>(null);
  let statusFilter = $state('');
  let page = $state(1);
  let selectedRuns = $state<string[]>([]);
  let expandedProducts = $state<Set<string>>(new Set());

  // Create form state
  let showForm = $state(false);
  let formName = $state('');
  let formProductId = $state('');
  let formNodeId = $state('');
  let formSerialNumber = $state('');
  let formVariant = $state('');
  let formNotes = $state('');
  let submitting = $state(false);

  // Dropdown options
  let products = $state<{ value: string; label: string }[]>([]);
  let nodes = $state<{ value: string; label: string }[]>([]);

  // Group runs by product
  interface ProductGroup {
    productId: string;
    productName: string;
    runs: ValidationRun[];
    totalPassed: number;
    totalFailed: number;
    latestRun: ValidationRun | null;
  }

  const groupedRuns = $derived.by(() => {
    const groups: Map<string, ProductGroup> = new Map();

    for (const run of runs) {
      const productId = run.product?.id ?? 'unknown';
      const productName = run.product?.name ?? 'Unknown Product';

      if (!groups.has(productId)) {
        groups.set(productId, {
          productId,
          productName,
          runs: [],
          totalPassed: 0,
          totalFailed: 0,
          latestRun: null,
        });
      }

      const group = groups.get(productId)!;
      group.runs.push(run);
      group.totalPassed += run.passedCount ?? 0;
      group.totalFailed += run.failedCount ?? 0;

      if (!group.latestRun || new Date(run.createdAt) > new Date(group.latestRun.createdAt)) {
        group.latestRun = run;
      }
    }

    // Sort by latest activity
    return Array.from(groups.values()).sort((a, b) => {
      if (!a.latestRun || !b.latestRun) return 0;
      return new Date(b.latestRun.createdAt).getTime() - new Date(a.latestRun.createdAt).getTime();
    });
  });

  function toggleProduct(productId: string): void {
    const newSet = new Set(expandedProducts);
    if (newSet.has(productId)) {
      newSet.delete(productId);
    } else {
      newSet.add(productId);
    }
    expandedProducts = newSet;
  }

  function toggleSelect(id: string): void {
    if (selectedRuns.includes(id)) {
      selectedRuns = selectedRuns.filter(r => r !== id);
    } else if (selectedRuns.length < 2) {
      selectedRuns = [...selectedRuns, id];
    }
  }

  function compareSelected(): void {
    if (selectedRuns.length === 2) {
      goto(`/validation/runs/compare?a=${selectedRuns[0]}&b=${selectedRuns[1]}`);
    }
  }

  async function fetchRuns(): Promise<void> {
    loading = true;
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('limit', '100');
      if (statusFilter) params.set('status', statusFilter);

      const res = await apiFetch<ApiResponse<{ data: ValidationRun[]; pagination: Pagination }>>(
        '/v2/validation/runs?' + params.toString()
      );

      runs = res.data.data;
      pagination = res.data.pagination;

      // Auto-expand first product with active runs, or first product
      if (expandedProducts.size === 0 && groupedRuns.length > 0) {
        const activeGroup = groupedRuns.find(g => g.runs.some(r => r.status === 'ACTIVE'));
        expandedProducts = new Set([activeGroup?.productId ?? groupedRuns[0].productId]);
      }
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load validation runs';
    } finally {
      loading = false;
    }
  }

  async function fetchDropdowns(): Promise<void> {
    try {
      const [prodRes, nodeRes] = await Promise.all([
        apiFetch<ApiResponse<{ data: Product[] }>>('/v2/products'),
        apiFetch<ApiResponse<{ data: { id: string; name: string }[] }>>('/v2/devices/mtibs'),
      ]);

      const prodList = Array.isArray(prodRes.data) ? prodRes.data : prodRes.data.data || [];
      products = prodList.map(p => ({ value: p.id, label: p.name }));

      const nodeList = Array.isArray(nodeRes.data) ? nodeRes.data : nodeRes.data.data || [];
      nodes = nodeList.map(n => ({ value: n.id, label: n.name }));
    } catch {
      // Dropdowns fail silently
    }
  }

  function resetForm(): void {
    formName = '';
    formProductId = '';
    formNodeId = '';
    formSerialNumber = '';
    formVariant = '';
    formNotes = '';
    showForm = false;
  }

  async function handleSubmit(e: Event): Promise<void> {
    e.preventDefault();
    error = null;
    submitting = true;

    const body: Record<string, unknown> = {
      name: formName,
      productId: formProductId,
      nodeId: formNodeId,
      serialNumber: formSerialNumber,
    };
    if (formVariant) body.firmwareVariant = formVariant;
    if (formNotes.trim()) body.notes = formNotes.trim();

    try {
      const res = await api.post<ApiResponse<ValidationRun>>('/v2/validation/runs', body);
      resetForm();
      await fetchRuns();
      if (res.data?.id) {
        goto(`/validation/runs/${res.data.id}`);
      }
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to create run';
    } finally {
      submitting = false;
    }
  }

  function getRunStatus(run: ValidationRun): 'running' | 'passed' | 'failed' | 'cancelled' {
    if (run.status === 'ACTIVE') return 'running';
    if (run.status === 'CANCELLED') return 'cancelled';
    if ((run.failedCount ?? 0) > 0) return 'failed';
    return 'passed';
  }

  function getRunDuration(run: ValidationRun): string | null {
    if (!run.startedAt) return null;
    const start = new Date(run.startedAt).getTime();
    const end = run.finishedAt ? new Date(run.finishedAt).getTime() : Date.now();
    return formatDuration(end - start);
  }

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.Validation.View')) {
      goto('/');
      return;
    }
    fetchRuns();
  });

  $effect(() => {
    const _p = page;
    fetchRuns();
  });

  $effect(() => {
    const _s = statusFilter;
    page = 1;
  });
</script>

<svelte:head>
  <title>Validation Runs — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="Validation Runs"
      description="Product validation test sessions grouped by product."
    />
  </div>

  <ErrorAlert message={error} />

  <!-- Create form -->
  {#if showForm}
    <FormCard title="New Validation Run" onClose={resetForm}>
      <form onsubmit={handleSubmit} class="space-y-3">
        <TextInput bind:value={formName} label="Name" placeholder="e.g. Alpha REV1.2 Debug v0.1.12" required />

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Select
            bind:value={formProductId}
            label="Product"
            placeholder="Select product"
            options={products}
            required
          />
          <Select
            bind:value={formNodeId}
            label="MTIB Node"
            placeholder="Select node"
            options={nodes}
            required
          />
        </div>

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextInput bind:value={formSerialNumber} label="Serial Number" placeholder="e.g. 70B3D584C01E1FCC" required />
          <Select
            bind:value={formVariant}
            label="Firmware Variant"
            placeholder="Any variant"
            options={VARIANT_OPTIONS}
          />
        </div>

        <div>
          <label for="notes" class="mb-1 block text-2xs font-medium text-text-tertiary">Notes</label>
          <textarea
            id="notes"
            bind:value={formNotes}
            rows={2}
            placeholder="Optional notes about this run..."
            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          ></textarea>
        </div>

        <div class="flex justify-end gap-2 pt-1">
          <button type="button" onclick={resetForm} class="btn btn-sm">Cancel</button>
          <button type="submit" disabled={submitting} class="btn btn-sm btn-primary">
            {submitting ? 'Creating...' : 'Create Run'}
          </button>
        </div>
      </form>
    </FormCard>
  {/if}

  <!-- Toolbar -->
  <div class="mb-4 flex flex-wrap items-center gap-3">
    <Select
      bind:value={statusFilter}
      placeholder="All statuses"
      options={STATUS_OPTIONS}
    />
    <span class="ml-auto text-2xs text-text-tertiary">
      {pagination.total} runs across {groupedRuns.length} products
    </span>
    {#if selectedRuns.length === 2}
      <button
        onclick={compareSelected}
        class="btn btn-sm flex items-center gap-1.5"
      >
        <GitCompareArrows size={14} />
        Compare Selected
      </button>
    {/if}
    {#if canManage}
      <button
        onclick={() => { showForm = true; fetchDropdowns(); }}
        class="btn btn-sm btn-primary flex items-center gap-1.5"
      >
        <Plus size={14} />
        New Run
      </button>
    {/if}
  </div>

  {#if loading}
    <LoadingState message="Loading validation runs..." />
  {:else if groupedRuns.length === 0}
    <EmptyState message="No validation runs found." />
  {:else}
    <!-- Product groups -->
    <div class="space-y-3">
      {#each groupedRuns as group (group.productId)}
        {@const isExpanded = expandedProducts.has(group.productId)}
        {@const hasActive = group.runs.some(r => r.status === 'ACTIVE')}
        {@const hasFailed = group.totalFailed > 0}

        <div class="rounded-xl border border-border bg-surface-1 overflow-hidden">
          <!-- Product header -->
          <button
            onclick={() => toggleProduct(group.productId)}
            class="w-full flex items-center gap-4 px-4 py-3 hover:bg-surface-0 transition-colors text-left"
          >
            <!-- Expand icon -->
            <div class="flex-shrink-0 text-text-tertiary">
              {#if isExpanded}
                <ChevronDown size={18} />
              {:else}
                <ChevronRight size={18} />
              {/if}
            </div>

            <!-- Product icon -->
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg {hasActive ? 'bg-accent-muted' : hasFailed ? 'bg-error-muted' : 'bg-success-muted'}">
              <Package size={20} class="{hasActive ? 'text-accent' : hasFailed ? 'text-error' : 'text-success'}" />
            </div>

            <!-- Product info -->
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <h3 class="text-sm font-semibold text-text-primary truncate">{group.productName}</h3>
                {#if hasActive}
                  <span class="inline-flex items-center gap-1 rounded-full bg-accent-muted px-2 py-0.5 text-2xs font-medium text-accent">
                    <Loader2 size={10} class="animate-spin" />
                    Active
                  </span>
                {/if}
              </div>
              <div class="flex items-center gap-3 mt-0.5 text-2xs text-text-tertiary">
                <span>{group.runs.length} run{group.runs.length !== 1 ? 's' : ''}</span>
                {#if group.latestRun}
                  <span>Latest: {formatTimeAgo(group.latestRun.createdAt)}</span>
                {/if}
              </div>
            </div>

            <!-- Stats -->
            <div class="flex items-center gap-4 text-sm">
              <div class="flex items-center gap-1.5">
                <CheckCircle2 size={16} class="text-success" />
                <span class="font-medium tabular-nums text-text-primary">{group.totalPassed}</span>
              </div>
              <div class="flex items-center gap-1.5">
                <XCircle size={16} class="{group.totalFailed > 0 ? 'text-error' : 'text-text-tertiary'}" />
                <span class="font-medium tabular-nums text-text-primary">{group.totalFailed}</span>
              </div>
            </div>
          </button>

          <!-- Runs list -->
          {#if isExpanded}
            <div class="border-t border-border">
              {#each group.runs as run, idx (run.id)}
                {@const runStatus = getRunStatus(run)}
                <div
                  class="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-0 cursor-pointer transition-colors {idx !== group.runs.length - 1 ? 'border-b border-border' : ''}"
                  onclick={() => goto(`/validation/runs/${run.id}`)}
                >
                  <!-- Checkbox -->
                  <div onclick={(e: MouseEvent) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selectedRuns.includes(run.id)}
                      disabled={!selectedRuns.includes(run.id) && selectedRuns.length >= 2}
                      onchange={() => toggleSelect(run.id)}
                      class="rounded border-border"
                    />
                  </div>

                  <!-- Status icon -->
                  <div class="flex-shrink-0">
                    {#if runStatus === 'running'}
                      <Loader2 size={16} class="text-accent animate-spin" />
                    {:else if runStatus === 'passed'}
                      <CheckCircle2 size={16} class="text-success" />
                    {:else if runStatus === 'failed'}
                      <XCircle size={16} class="text-error" />
                    {:else}
                      <XCircle size={16} class="text-text-tertiary" />
                    {/if}
                  </div>

                  <!-- Run info -->
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                      <span class="text-sm font-medium text-text-primary truncate">{run.name}</span>
                      <StatusBadge status={run.status} />
                    </div>
                    <div class="flex items-center gap-2 mt-0.5 text-2xs text-text-tertiary">
                      {#if run.createdBy}
                        <span>{run.createdBy.name}</span>
                        <span>·</span>
                      {/if}
                      <span title={formatDateTime(run.createdAt)}>{formatTimeAgo(run.createdAt)}</span>
                    </div>
                  </div>

                  <!-- Progress / Results -->
                  <div class="flex items-center gap-4 text-xs">
                    <div class="flex items-center gap-3 tabular-nums">
                      <span class="text-success">{run.passedCount ?? 0}P</span>
                      <span class="{(run.failedCount ?? 0) > 0 ? 'text-error' : 'text-text-tertiary'}">{run.failedCount ?? 0}F</span>
                      <span class="text-text-tertiary">/ {run.targetCount ?? 0}</span>
                    </div>

                    {#if getRunDuration(run)}
                      <div class="flex items-center gap-1 text-text-tertiary">
                        <Clock size={12} />
                        <span class="tabular-nums">{getRunDuration(run)}</span>
                      </div>
                    {/if}
                  </div>

                  <!-- Arrow -->
                  <ChevronRight size={16} class="text-text-tertiary" />
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}

  <!-- Pagination -->
  {#if pagination.pages > 1}
    <div class="mt-4 flex items-center justify-between">
      <span class="text-2xs text-text-tertiary">
        Page {pagination.page} of {pagination.pages}
      </span>
      <div class="flex items-center gap-1">
        <button
          onclick={() => (page = 1)}
          disabled={page <= 1}
          aria-label="First page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronsLeft size={16} />
        </button>
        <button
          onclick={() => (page = Math.max(1, page - 1))}
          disabled={page <= 1}
          aria-label="Previous page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronLeft size={16} />
        </button>
        <button
          onclick={() => (page = Math.min(pagination.pages, page + 1))}
          disabled={page >= pagination.pages}
          aria-label="Next page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronRight size={16} />
        </button>
        <button
          onclick={() => (page = pagination.pages)}
          disabled={page >= pagination.pages}
          aria-label="Last page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronsRight size={16} />
        </button>
      </div>
    </div>
  {/if}
</div>
