<script lang="ts">
  import { onMount } from 'svelte';
  import { ChevronDown, ChevronRight } from 'lucide-svelte';
  import { apiFetch } from '$lib/api';
  import type { AuditEntry, Pagination } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import { formatTimeAgo, formatDateTime } from '$lib/utils/formatting';
  import EmptyState from './empty-state.svelte';
  import LoadingState from './loading-state.svelte';

  let { entityType, entityId }: { entityType: string; entityId: string } = $props();

  let entries = $state<AuditEntry[]>([]);
  let pagination = $state<Pagination>({ page: 1, limit: 25, total: 0, pages: 0 });
  let loading = $state(true);
  let expandedId = $state<string | null>(null);
  let page = $state(1);

  function getVerbPastTense(verb: string): string {
    const map: Record<string, string> = {
      create: 'created', update: 'updated', delete: 'deleted',
      deactivate: 'deactivated', upload: 'uploaded', trigger: 'triggered',
      cancel: 'cancelled', assign: 'assigned', unassign: 'unassigned',
      deploy: 'deployed', undeploy: 'undeployed', lock: 'locked',
      unlock: 'unlocked', login: 'logged in', sync: 'synced',
      start: 'started', end: 'ended', reset: 'reset',
    };
    return map[verb] || verb;
  }

  function formatAction(action: string): string {
    const parts = action.split('.');
    if (parts.length >= 2) {
      const verb = parts[parts.length - 1];
      const scope = parts.slice(0, -1).join('.');
      return `${getVerbPastTense(verb)}${scope !== entityType.toLowerCase() ? ` (${scope})` : ''}`;
    }
    return action;
  }

  function getActionColor(action: string): string {
    if (action.includes('create') || action.includes('register')) return 'text-success';
    if (action.includes('delete') || action.includes('deactivate')) return 'text-error';
    return 'text-text-primary';
  }

  async function fetchHistory(): Promise<void> {
    loading = true;
    try {
      const params = new URLSearchParams({ page: String(page), limit: '25' });
      const res = await apiFetch<ApiResponse<{ data: AuditEntry[]; pagination: Pagination }>>(
        `/v2/system/history/entity/${entityType}/${entityId}?${params}`
      );
      entries = res.data.data;
      pagination = res.data.pagination;
    } catch {
      entries = [];
    } finally {
      loading = false;
    }
  }

  onMount(() => { fetchHistory(); });

  $effect(() => { page; fetchHistory(); });
</script>

<div class="space-y-3">
  {#if loading}
    <LoadingState message="Loading history..." />
  {:else if entries.length === 0}
    <EmptyState message="No changes recorded yet." />
  {:else}
    <div class="space-y-1">
      {#each entries as entry (entry.id)}
        {@const isExpanded = expandedId === entry.id}
        {@const hasDetails = entry.details && Object.keys(entry.details).length > 0}

        <div class="rounded-lg border border-border-subtle">
          <button
            onclick={() => hasDetails && (expandedId = isExpanded ? null : entry.id)}
            class="flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm transition-colors {hasDetails ? 'cursor-pointer hover:bg-surface-2' : 'cursor-default'}"
          >
            {#if hasDetails}
              {#if isExpanded}
                <ChevronDown size={14} class="shrink-0 text-text-tertiary" />
              {:else}
                <ChevronRight size={14} class="shrink-0 text-text-tertiary" />
              {/if}
            {:else}
              <div class="w-3.5 shrink-0"></div>
            {/if}

            <span class="font-medium {getActionColor(entry.action)}">
              {formatAction(entry.action)}
            </span>
            <span class="ml-auto flex items-center gap-3 text-2xs text-text-tertiary">
              {#if entry.user}
                <span>{entry.user.name}</span>
              {:else}
                <span class="italic">System</span>
              {/if}
              <span title={formatDateTime(entry.createdAt)}>{formatTimeAgo(entry.createdAt)}</span>
            </span>
          </button>

          {#if isExpanded && hasDetails}
            <div class="border-t border-border-subtle bg-surface-1 px-4 py-3">
              {#if entry.details!.before && entry.details!.after}
                <div class="grid grid-cols-2 gap-4 text-xs">
                  <div>
                    <div class="mb-1 font-semibold text-error">Before</div>
                    <pre class="max-h-32 overflow-auto rounded bg-surface-0 p-2 text-2xs">{JSON.stringify(entry.details!.before, null, 2)}</pre>
                  </div>
                  <div>
                    <div class="mb-1 font-semibold text-success">After</div>
                    <pre class="max-h-32 overflow-auto rounded bg-surface-0 p-2 text-2xs">{JSON.stringify(entry.details!.after, null, 2)}</pre>
                  </div>
                </div>
              {:else}
                <pre class="max-h-40 overflow-auto rounded bg-surface-0 p-2 text-2xs text-text-secondary">{JSON.stringify(entry.details, null, 2)}</pre>
              {/if}
              <div class="mt-2 flex gap-3 text-2xs text-text-tertiary">
                <span>{formatDateTime(entry.createdAt)}</span>
                {#if entry.ipAddress}<span>IP: {entry.ipAddress}</span>{/if}
              </div>
            </div>
          {/if}
        </div>
      {/each}
    </div>

    {#if pagination.pages > 1}
      <div class="flex items-center justify-between text-2xs text-text-tertiary">
        <span>Page {page} of {pagination.pages} ({pagination.total} entries)</span>
        <div class="flex gap-1">
          <button disabled={page <= 1} onclick={() => page--} class="rounded px-2 py-1 hover:bg-surface-2 disabled:opacity-30">Prev</button>
          <button disabled={page >= pagination.pages} onclick={() => page++} class="rounded px-2 py-1 hover:bg-surface-2 disabled:opacity-30">Next</button>
        </div>
      </div>
    {/if}
  {/if}
</div>
