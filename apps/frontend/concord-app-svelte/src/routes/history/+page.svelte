<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    ChevronDown,
    ChevronRight,
    Search,
    ChevronLeft,
    ChevronsLeft,
    ChevronsRight,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch } from '$lib/api';
  import type { AuditEntry, Pagination } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import { formatTimeAgo, formatDateTime } from '$lib/utils/formatting';
  import EmptyState from '$lib/components/ui/empty-state.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';
  import Select from '$lib/components/ui/select.svelte';

  const auth = getAuth();

  const ENTITY_TYPES = [
    'User',
    'PermissionSet',
    'ApiKey',
    'MTIB',
    'InventoryComponent',
    'ComponentRevision',
    'InventoryAssembly',
    'AssemblyRevision',
    'Codebase',
    'Release',
    'Artifact',
  ];

  function getVerbPastTense(verb: string): string {
    const map: Record<string, string> = {
      create: 'created',
      update: 'updated',
      delete: 'deleted',
      deactivate: 'deactivated',
      register: 'registered',
      unregister: 'unregistered',
      upload: 'uploaded',
    };
    return map[verb] || verb;
  }

  function formatAction(action: string): { verb: string; entity: string } {
    const parts = action.split('.');
    if (parts.length >= 2) {
      const verb = parts[parts.length - 1];
      const entity = parts.slice(0, -1).join(' ');
      return { verb: getVerbPastTense(verb), entity };
    }
    return { verb: action, entity: '' };
  }

  let entries = $state<AuditEntry[]>([]);
  let pagination = $state<Pagination>({ page: 1, limit: 50, total: 0, pages: 0 });
  let loading = $state(true);
  let error = $state<string | null>(null);
  let expandedId = $state<string | null>(null);

  let entityType = $state('');
  let actionSearch = $state('');
  let page = $state(1);

  async function fetchHistory(): Promise<void> {
    loading = true;
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('limit', '50');
      if (entityType) params.set('entityType', entityType);
      if (actionSearch) params.set('action', actionSearch);

      const res = await apiFetch<ApiResponse<{ entries: AuditEntry[]; pagination: Pagination }>>(
        '/v2/system/history?' + params.toString()
      );

      entries = res.data.entries;
      pagination = res.data.pagination;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load history';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.History.View')) {
      goto('/');
      return;
    }
    fetchHistory();
  });

  // Refetch when page changes (filter changes trigger this via page reset)
  $effect(() => {
    const _p = page;
    fetchHistory();
  });

  // Reset to page 1 when filters change (this triggers the page effect above)
  $effect(() => {
    const _et = entityType;
    const _as = actionSearch;
    page = 1;
  });

  function toggleExpand(id: string): void {
    expandedId = expandedId === id ? null : id;
  }
</script>

{#snippet DetailValue(value: unknown)}
  {#if value === null || value === undefined}
    <span class="text-text-tertiary">null</span>
  {:else if typeof value === 'boolean'}
    <span class={value ? 'text-success' : 'text-error'}>{String(value)}</span>
  {:else if typeof value === 'object'}
    <pre class="mt-1 max-h-40 overflow-auto rounded bg-surface-0 p-2 text-2xs text-text-secondary">{JSON.stringify(value, null, 2)}</pre>
  {:else}
    <span class="text-text-primary">{String(value)}</span>
  {/if}
{/snippet}

<svelte:head>
  <title>History — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="History"
      description="Audit log of actions across the system (last 30 days)."
    />
  </div>

  <ErrorAlert message={error} />

  <!-- Filters -->
  <div class="mb-4 flex flex-wrap items-center gap-3">
    <div class="relative">
      <Search
        size={16}
        class="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary"
      />
      <input
        type="text"
        bind:value={actionSearch}
        placeholder="Search actions..."
        aria-label="Search actions"
        class="rounded-lg border border-border bg-surface-0 py-2 pl-8 pr-3 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
      />
    </div>
    <Select
      bind:value={entityType}
      class="w-auto"
      placeholder="All entity types"
      options={ENTITY_TYPES.map(t => ({ value: t, label: t }))}
    />
    <span class="ml-auto text-2xs text-text-tertiary">
      {pagination.total} entries
    </span>
  </div>

  <!-- Table -->
  {#if loading}
    <LoadingState message="Loading history..." />
  {:else if entries.length === 0}
    <EmptyState message="No audit entries found." />
  {:else}
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr class="border-b border-border">
            <th class="table-header w-8 px-3"></th>
            <th class="table-header">Action</th>
            <th class="table-header">Entity</th>
            <th class="table-header">User</th>
            <th class="table-header text-right">When</th>
          </tr>
        </thead>
        <tbody>
          {#each entries as entry (entry.id)}
            {@const isExpanded = expandedId === entry.id}
            {@const { verb, entity } = formatAction(entry.action)}
            {@const hasDetails = entry.details && Object.keys(entry.details).length > 0}

            <tr class="table-row {hasDetails ? 'table-row-interactive' : ''}">
              <td colspan="5" class="p-0">
                <div>
                  <button
                    onclick={() => hasDetails && toggleExpand(entry.id)}
                    class="flex w-full items-center text-left transition-colors {hasDetails
                      ? 'cursor-pointer hover:bg-surface-2'
                      : 'cursor-default'}"
                  >
                    <div class="w-8 shrink-0 px-3 h-12 flex items-center">
                      {#if hasDetails}
                        {#if isExpanded}
                          <ChevronDown size={16} class="text-text-tertiary" />
                        {:else}
                          <ChevronRight size={16} class="text-text-tertiary" />
                        {/if}
                      {/if}
                    </div>
                    <div class="flex-1 px-4 h-12 flex items-center">
                      <span class="font-medium text-text-primary">{verb}</span>
                      {#if entity}
                        <span class="ml-1 text-text-secondary">{entity}</span>
                      {/if}
                    </div>
                    <div class="shrink-0 px-4 h-12 flex items-center">
                      <span class="inline-flex items-center rounded-full bg-surface-2 px-2 py-0.5 text-2xs font-medium text-text-secondary">
                        {entry.entityType}
                      </span>
                      {#if entry.entityId}
                        <span class="ml-2 font-mono text-2xs text-text-tertiary">
                          {entry.entityId.length > 12
                            ? entry.entityId.slice(0, 12) + '...'
                            : entry.entityId}
                        </span>
                      {/if}
                    </div>
                    <div class="shrink-0 px-4 h-12 flex items-center">
                      {#if entry.user}
                        <span class="text-text-secondary">{entry.user.name}</span>
                      {:else}
                        <span class="text-text-tertiary">System</span>
                      {/if}
                    </div>
                    <div class="shrink-0 px-4 h-12 flex items-center justify-end">
                      <span class="text-text-tertiary" title={formatDateTime(entry.createdAt)}>
                        {formatTimeAgo(entry.createdAt)}
                      </span>
                    </div>
                  </button>

                  <!-- Expanded details -->
                  {#if isExpanded && hasDetails}
                    <div class="border-t border-border-subtle bg-surface-1 px-12 py-4">
                      <div class="grid grid-cols-2 gap-x-8 gap-y-3">
                        {#each Object.entries(entry.details!) as [key, value]}
                          <div>
                            <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                              {key}
                            </div>
                            <div class="mt-0.5 text-sm">
                              {@render DetailValue(value)}
                            </div>
                          </div>
                        {/each}
                      </div>
                      <div class="mt-3 flex items-center gap-4 text-2xs text-text-tertiary">
                        <span>{formatDateTime(entry.createdAt)}</span>
                        {#if entry.ipAddress}
                          <span>IP: {entry.ipAddress}</span>
                        {/if}
                        <span class="font-mono">{entry.id}</span>
                      </div>
                    </div>
                  {/if}
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
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
