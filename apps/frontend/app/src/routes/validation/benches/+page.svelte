<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    ChevronLeft,
    ChevronRight,
    ChevronsLeft,
    ChevronsRight,
    Plus,
    Pencil,
    Trash2,
    Cpu,
    RefreshCw,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import type { TestBench, Pagination } from '$lib/types/models';
  import { formatTimeAgo } from '$lib/utils/formatting';
  import EmptyState from '$lib/components/ui/empty-state.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import FormCard from '$lib/components/ui/form-card.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import TextInput from '$lib/components/ui/text-input.svelte';
  import { fetchBenches, updateBench, deleteBench } from '$lib/services/validation';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('validation:manage'));

  const STATUS_OPTIONS = [
    { value: 'AVAILABLE', label: 'Available' },
    { value: 'LOCKED', label: 'Locked' },
    { value: 'OFFLINE', label: 'Offline' },
    { value: 'MAINTENANCE', label: 'Maintenance' },
  ];

  // List state
  let benches = $state<TestBench[]>([]);
  let pagination = $state<Pagination>({ page: 1, limit: 50, total: 0, pages: 0 });
  let loading = $state(true);
  let error = $state<string | null>(null);
  let page = $state(1);
  let statusFilter = $state('');
  let productFilter = $state('');

  // Edit form state
  let showForm = $state(false);
  let editingBench = $state<TestBench | null>(null);
  let formName = $state('');
  let formMtibRevision = $state('');
  let formCapabilities = $state('');
  let formStatus = $state('AVAILABLE');
  let formDutDeviceId = $state('');
  let formDutSnr = $state('');
  let formDutImei = $state('');
  let formDutIccids = $state('');
  let formJlinkAppSerial = $state('');
  let formJlinkCommsSerial = $state('');
  let formUartAppPath = $state('');
  let formUartCommsPath = $state('');
  let submitting = $state(false);

  // Delete confirmation
  let deleteTarget = $state<TestBench | null>(null);
  let deleting = $state(false);

  async function loadBenches(): Promise<void> {
    loading = true;
    error = null;
    try {
      const result = await fetchBenches({
        page,
        limit: 50,
        status: statusFilter || undefined,
        product: productFilter || undefined,
      });
      benches = result.data;
      pagination = result.pagination;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load test benches';
    } finally {
      loading = false;
    }
  }

  function resetForm(): void {
    showForm = false;
    editingBench = null;
    formName = '';
    formMtibRevision = '';
    formCapabilities = '';
    formStatus = 'AVAILABLE';
    formDutDeviceId = '';
    formDutSnr = '';
    formDutImei = '';
    formDutIccids = '';
    formJlinkAppSerial = '';
    formJlinkCommsSerial = '';
    formUartAppPath = '';
    formUartCommsPath = '';
  }

  function openEditForm(bench: TestBench): void {
    editingBench = bench;
    formName = bench.name;
    formMtibRevision = bench.mtibRevision || '';
    formCapabilities = bench.capabilities.join(', ');
    formStatus = bench.status;
    formDutDeviceId = bench.dutDeviceId || '';
    formDutSnr = bench.dutSnr || '';
    formDutImei = bench.dutImei || '';
    formDutIccids = bench.dutIccids.join(', ');
    formJlinkAppSerial = bench.jlinkAppSerial || '';
    formJlinkCommsSerial = bench.jlinkCommsSerial || '';
    formUartAppPath = bench.uartAppPath || '';
    formUartCommsPath = bench.uartCommsPath || '';
    showForm = true;
  }

  async function handleSubmit(e: Event): Promise<void> {
    e.preventDefault();
    if (!editingBench) return;
    error = null;
    submitting = true;

    const capabilities = formCapabilities
      .split(',')
      .map((c) => c.trim())
      .filter((c) => c.length > 0);

    const iccids = formDutIccids
      .split(',')
      .map((c) => c.trim())
      .filter((c) => c.length > 0);

    const data = {
      name: formName,
      mtibRevision: formMtibRevision || undefined,
      capabilities,
      status: formStatus,
      dutDeviceId: formDutDeviceId || undefined,
      dutSnr: formDutSnr || undefined,
      dutImei: formDutImei || undefined,
      dutIccids: iccids,
      jlinkAppSerial: formJlinkAppSerial || undefined,
      jlinkCommsSerial: formJlinkCommsSerial || undefined,
      uartAppPath: formUartAppPath || undefined,
      uartCommsPath: formUartCommsPath || undefined,
    };

    try {
      await updateBench(editingBench.id, data);
      resetForm();
      await loadBenches();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to update bench';
    } finally {
      submitting = false;
    }
  }

  async function handleDelete(): Promise<void> {
    if (!deleteTarget) return;
    deleting = true;
    error = null;
    try {
      await deleteBench(deleteTarget.id);
      deleteTarget = null;
      await loadBenches();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to delete bench';
    } finally {
      deleting = false;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('validation:view')) {
      goto('/');
      return;
    }
    loadBenches();
  });

  $effect(() => {
    const _p = page;
    loadBenches();
  });

  $effect(() => {
    const _s = statusFilter;
    const _f = productFilter;
    page = 1;
  });
</script>

<svelte:head>
  <title>Test Benches - Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="Test Benches"
      description="Registered validation test benches with DUT info and hardware configuration."
    />
  </div>

  <ErrorAlert message={error} />

  <!-- Delete confirmation -->
  {#if deleteTarget}
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div class="w-full max-w-md rounded-lg bg-surface-1 p-6 shadow-xl">
        <h3 class="mb-2 text-lg font-semibold text-text-primary">Delete Test Bench</h3>
        <p class="mb-4 text-sm text-text-secondary">
          Are you sure you want to delete <span class="font-medium">{deleteTarget.name}</span>? This
          action cannot be undone.
        </p>
        <div class="flex justify-end gap-2">
          <button onclick={() => (deleteTarget = null)} class="btn btn-sm">Cancel</button>
          <button onclick={handleDelete} disabled={deleting} class="btn btn-sm btn-danger">
            {deleting ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  {/if}

  <!-- Edit form -->
  {#if showForm && editingBench}
    <FormCard title="Edit Test Bench" onClose={resetForm}>
      <form onsubmit={handleSubmit} class="space-y-3">
        <TextInput
          bind:value={formName}
          label="Name"
          placeholder="e.g. Alpha B0 Bench 1"
          required
        />

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextInput
            bind:value={formMtibRevision}
            label="MTIB Revision"
            placeholder="e.g. REV1.2"
          />
          <Select
            bind:value={formStatus}
            label="Status"
            options={STATUS_OPTIONS}
          />
        </div>

        <TextInput
          bind:value={formCapabilities}
          label="Capabilities"
          placeholder="button, peltier, charger_relay (comma-separated)"
        />

        <div class="border-t border-border pt-3">
          <span class="mb-2 block text-2xs font-medium uppercase text-text-tertiary">DUT Info</span>
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <TextInput
              bind:value={formDutDeviceId}
              label="Device ID"
              placeholder="e.g. 70B3D584C01E1FCC"
            />
            <TextInput bind:value={formDutSnr} label="SNR" placeholder="e.g. 0964" />
          </div>
          <div class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <TextInput bind:value={formDutImei} label="IMEI" placeholder="e.g. 355025931735979" />
            <TextInput
              bind:value={formDutIccids}
              label="ICCIDs"
              placeholder="ICCID1, ICCID2 (comma-separated)"
            />
          </div>
        </div>

        <div class="border-t border-border pt-3">
          <span class="mb-2 block text-2xs font-medium uppercase text-text-tertiary">Hardware</span>
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <TextInput
              bind:value={formJlinkAppSerial}
              label="J-Link App Serial"
              placeholder="e.g. 821009546"
            />
            <TextInput
              bind:value={formJlinkCommsSerial}
              label="J-Link Comms Serial"
              placeholder="e.g. 821009537"
            />
          </div>
          <div class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <TextInput
              bind:value={formUartAppPath}
              label="UART App Path"
              placeholder="e.g. /dev/verdin-uart2"
            />
            <TextInput
              bind:value={formUartCommsPath}
              label="UART Comms Path"
              placeholder="e.g. /dev/verdin-uart1"
            />
          </div>
        </div>

        <div class="flex justify-end gap-2 pt-1">
          <button type="button" onclick={resetForm} class="btn btn-sm">Cancel</button>
          <button type="submit" disabled={submitting} class="btn btn-sm btn-primary">
            {submitting ? 'Saving...' : 'Update'}
          </button>
        </div>
      </form>
    </FormCard>
  {/if}

  <div class="mb-4 flex flex-wrap items-center gap-3">
    <Select bind:value={statusFilter} placeholder="All statuses" options={STATUS_OPTIONS} />
    <TextInput bind:value={productFilter} placeholder="Filter by product..." class="w-36" />
    <button
      onclick={() => loadBenches()}
      class="rounded-lg p-2 text-text-secondary hover:bg-surface-1"
      title="Refresh"
    >
      <RefreshCw size={16} />
    </button>
    <span class="ml-auto text-2xs text-text-tertiary">{pagination.total} benches</span>
    {#if canManage}
      <button
        onclick={() => goto('/validation/benches/register')}
        class="btn btn-sm btn-primary flex items-center gap-1.5"
      >
        <Plus size={14} />
        Register MTIB
      </button>
    {/if}
  </div>

  {#if loading}
    <LoadingState message="Loading test benches..." />
  {:else if benches.length === 0}
    <EmptyState message="No test benches found." icon={Cpu} />
  {:else}
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr class="border-b border-border">
            <th class="table-header">Station</th>
            <th class="table-header">Name</th>
            <th class="table-header">Product</th>
            <th class="table-header">Status</th>
            <th class="table-header">DUT SNR</th>
            <th class="table-header">Fixture Design</th>
            <th class="table-header text-right">Updated</th>
            {#if canManage}
              <th class="table-header w-20"></th>
            {/if}
          </tr>
        </thead>
        <tbody>
          {#each benches as bench (bench.id)}
            <tr class="table-row">
              <td class="table-cell font-mono text-sm text-text-secondary">{bench.stationId}</td>
              <td class="table-cell font-medium text-text-primary">{bench.name}</td>
              <td class="table-cell">
                <span class="rounded bg-surface-2 px-2 py-0.5 text-xs text-text-secondary">
                  {bench.dutProduct} {bench.dutRevision}
                </span>
              </td>
              <td class="table-cell">
                <StatusBadge status={bench.status} />
              </td>
              <td class="table-cell font-mono text-sm text-text-secondary">
                {bench.dutSnr || '-'}
              </td>
              <td class="table-cell text-text-secondary">
                {bench.fixtureDesign?.name || '-'}
              </td>
              <td class="table-cell text-right text-text-tertiary">
                {formatTimeAgo(bench.updatedAt)}
              </td>
              {#if canManage}
                <td class="table-cell">
                  <div class="flex justify-end gap-1">
                    <button
                      onclick={() => openEditForm(bench)}
                      title="Edit"
                      class="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      onclick={() => (deleteTarget = bench)}
                      title="Delete"
                      class="rounded p-1 text-text-tertiary hover:bg-error/10 hover:text-error"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              {/if}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  {#if pagination.pages > 1}
    <div class="mt-4 flex items-center justify-between">
      <span class="text-2xs text-text-tertiary">Page {pagination.page} of {pagination.pages}</span>
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
