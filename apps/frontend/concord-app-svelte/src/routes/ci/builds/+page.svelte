<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    ChevronLeft,
    ChevronRight,
    ChevronsLeft,
    ChevronsRight,
    Download,
    GitBranch,
    ArrowLeft,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import type { BuildJob } from '$lib/types/ci';
  import type { Pagination } from '$lib/types/models';
  import { fetchBuilds } from '$lib/services/ci';
  import { formatTimeAgo, formatDateTime, formatDuration, formatSize } from '$lib/utils/formatting';
  import EmptyState from '$lib/components/ui/empty-state.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';

  const auth = getAuth();

  const STATUS_OPTIONS = [
    { value: 'QUEUED', label: 'Queued' },
    { value: 'BUILDING', label: 'Building' },
    { value: 'SUCCESS', label: 'Success' },
    { value: 'FAILED', label: 'Failed' },
    { value: 'CANCELLED', label: 'Cancelled' },
  ];

  let builds = $state<BuildJob[]>([]);
  let pagination = $state<Pagination>({ page: 1, limit: 50, total: 0, pages: 0 });
  let loading = $state(true);
  let error = $state<string | null>(null);
  let statusFilter = $state('');
  let currentPage = $state(1);

  async function loadBuilds(): Promise<void> {
    try {
      const res = await fetchBuilds({
        page: currentPage,
        limit: 50,
        status: statusFilter || undefined,
      });
      builds = res.data;
      pagination = res.pagination;
      error = null;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load builds';
    } finally {
      loading = false;
    }
  }

  function artifactTotalSize(build: BuildJob): string {
    if (!build.artifacts || build.artifacts.length === 0) return '--';
    const total = build.artifacts.reduce((sum, a) => sum + a.sizeBytes, 0);
    return formatSize(String(total));
  }

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.CI.View')) {
      goto('/');
      return;
    }
    loadBuilds();
  });

  $effect(() => {
    const _p = currentPage;
    loadBuilds();
  });

  $effect(() => {
    const _s = statusFilter;
    currentPage = 1;
  });
</script>

<svelte:head>
  <title>Builds - CI - Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <button
    onclick={() => goto('/ci')}
    class="flex items-center gap-1 text-xs text-text-tertiary hover:text-text-primary transition-colors mb-3"
  >
    <ArrowLeft size={14} />
    CI / Builds
  </button>

  <div class="mb-6">
    <PageHeader
      title="All Builds"
      description="Individual firmware build jobs with artifacts and logs."
    />
  </div>

  <ErrorAlert message={error} />

  <div class="mb-4 flex flex-wrap items-center gap-3">
    <Select
      bind:value={statusFilter}
      placeholder="All statuses"
      options={STATUS_OPTIONS}
    />
    <span class="ml-auto text-2xs text-text-tertiary">
      {pagination.total} builds
    </span>
  </div>

  {#if loading}
    <LoadingState message="Loading builds..." />
  {:else if builds.length === 0}
    <EmptyState message="No builds found." />
  {:else}
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr class="border-b border-border">
            <th class="table-header">Product</th>
            <th class="table-header">Branch</th>
            <th class="table-header">Variant</th>
            <th class="table-header">Commit</th>
            <th class="table-header">Status</th>
            <th class="table-header text-right">Duration</th>
            <th class="table-header text-right">Artifacts</th>
            <th class="table-header text-right">Created</th>
          </tr>
        </thead>
        <tbody>
          {#each builds as build (build.id)}
            <tr
              class="table-row table-row-interactive"
              onclick={() => goto(`/ci/builds/${build.id}`)}
            >
              <td class="table-cell font-medium text-text-primary">{build.product}</td>
              <td class="table-cell text-text-secondary">
                <span class="inline-flex items-center gap-1">
                  <GitBranch size={12} class="text-text-tertiary" />
                  {build.branch}
                </span>
              </td>
              <td class="table-cell text-text-secondary capitalize">{build.variant}</td>
              <td class="table-cell font-mono text-text-tertiary text-xs">
                {build.commitSha ? build.commitSha.slice(0, 7) : '--'}
              </td>
              <td class="table-cell"><StatusBadge status={build.status} /></td>
              <td class="table-cell text-right tabular-nums text-text-secondary text-xs">
                {build.durationSeconds ? formatDuration(build.durationSeconds * 1000) : '--'}
              </td>
              <td class="table-cell text-right tabular-nums text-text-secondary text-xs">
                {#if build.artifacts && build.artifacts.length > 0}
                  <span class="inline-flex items-center gap-1">
                    <Download size={12} class="text-text-tertiary" />
                    {build.artifacts.length}
                    <span class="text-text-tertiary">({artifactTotalSize(build)})</span>
                  </span>
                {:else}
                  --
                {/if}
              </td>
              <td class="table-cell text-right text-text-tertiary" title={formatDateTime(build.createdAt)}>
                {formatTimeAgo(build.createdAt)}
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
          onclick={() => (currentPage = 1)}
          disabled={currentPage <= 1}
          aria-label="First page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronsLeft size={16} />
        </button>
        <button
          onclick={() => (currentPage = Math.max(1, currentPage - 1))}
          disabled={currentPage <= 1}
          aria-label="Previous page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronLeft size={16} />
        </button>
        <button
          onclick={() => (currentPage = Math.min(pagination.pages, currentPage + 1))}
          disabled={currentPage >= pagination.pages}
          aria-label="Next page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronRight size={16} />
        </button>
        <button
          onclick={() => (currentPage = pagination.pages)}
          disabled={currentPage >= pagination.pages}
          aria-label="Last page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronsRight size={16} />
        </button>
      </div>
    </div>
  {/if}
</div>
