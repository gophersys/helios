<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    ChevronLeft,
    ChevronRight,
    ChevronsLeft,
    ChevronsRight,
    GitCompareArrows,
    Plus,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import type { ValidationRun, Product, Pagination } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import { formatTimeAgo, formatDateTime } from '$lib/utils/formatting';
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
  let pagination = $state<Pagination>({ page: 1, limit: 50, total: 0, pages: 0 });
  let loading = $state(true);
  let error = $state<string | null>(null);
  let statusFilter = $state('');
  let page = $state(1);
  let selectedRuns = $state<string[]>([]);

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
      params.set('limit', '50');
      if (statusFilter) params.set('status', statusFilter);

      const res = await apiFetch<ApiResponse<{ data: ValidationRun[]; pagination: Pagination }>>(
        '/v2/validation/runs?' + params.toString()
      );

      runs = res.data.data;
      pagination = res.data.pagination;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load validation runs';
    } finally {
      loading = false;
    }
  }

  async function fetchDropdowns(): Promise<void> {
    try {
      const [prodRes, nodeRes] = await Promise.all([
        apiFetch<ApiResponse<{ data: Product[] }>>('/v2/catalog'),
        apiFetch<ApiResponse<{ data: { id: string; name: string }[] }>>('/v2/mtibs'),
      ]);

      const prodList = Array.isArray(prodRes.data) ? prodRes.data : prodRes.data.data || [];
      products = prodList.map(p => ({ value: p.id, label: p.name }));

      const nodeList = Array.isArray(nodeRes.data) ? nodeRes.data : nodeRes.data.data || [];
      nodes = nodeList.map(n => ({ value: n.id, label: n.name }));
    } catch {
      // Dropdowns fail silently — user can still type IDs manually
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
      // Navigate to the newly created run
      if (res.data?.id) {
        goto(`/validation/runs/${res.data.id}`);
      }
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to create run';
    } finally {
      submitting = false;
    }
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

  function progressText(run: ValidationRun): string {
    const completed = run.completedCount ?? 0;
    const target = run.targetCount ?? 0;
    const passed = run.passedCount ?? 0;
    const failed = run.failedCount ?? 0;
    if (target === 0) return '—';
    return `${passed}P ${failed}F / ${completed} of ${target}`;
  }
</script>

<svelte:head>
  <title>Validation Runs — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="Validation Runs"
      description="Product validation test sessions — firmware variants, test results, and power measurements."
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

  <div class="mb-4 flex flex-wrap items-center gap-3">
    <Select
      bind:value={statusFilter}
      placeholder="All statuses"
      options={STATUS_OPTIONS}
    />
    <span class="ml-auto text-2xs text-text-tertiary">
      {pagination.total} runs
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
  {:else if runs.length === 0}
    <EmptyState message="No validation runs found." />
  {:else}
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr class="border-b border-border">
            <th class="table-header w-8"></th>
            <th class="table-header">Name</th>
            <th class="table-header">Product</th>
            <th class="table-header">Status</th>
            <th class="table-header">Progress</th>
            <th class="table-header">Created By</th>
            <th class="table-header text-right">Started</th>
          </tr>
        </thead>
        <tbody>
          {#each runs as run (run.id)}
            <tr
              class="table-row table-row-interactive"
              onclick={() => goto(`/validation/runs/${run.id}`)}
            >
              <td class="table-cell" onclick={(e: MouseEvent) => e.stopPropagation()}>
                <input
                  type="checkbox"
                  checked={selectedRuns.includes(run.id)}
                  disabled={!selectedRuns.includes(run.id) && selectedRuns.length >= 2}
                  onchange={() => toggleSelect(run.id)}
                  class="rounded border-border"
                />
              </td>
              <td class="table-cell font-medium text-text-primary">{run.name}</td>
              <td class="table-cell text-text-secondary">{run.product?.name ?? '—'}</td>
              <td class="table-cell"><StatusBadge status={run.status} /></td>
              <td class="table-cell text-text-secondary tabular-nums text-xs">
                {progressText(run)}
              </td>
              <td class="table-cell text-text-secondary">
                {run.createdBy?.name ?? '—'}
              </td>
              <td class="table-cell text-right text-text-tertiary" title={formatDateTime(run.createdAt)}>
                {formatTimeAgo(run.createdAt)}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

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
