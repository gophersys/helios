<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { CheckCircle2, XCircle, SkipForward, Clock, AlertCircle } from 'lucide-svelte';
  import { apiFetch } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { ValidationRun, Pagination } from '$lib/types/models';
  import { formatTimeAgo, formatDuration } from '$lib/utils/formatting';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';

  interface Props {
    productId: string;
    productName: string;
  }

  let { productId, productName }: Props = $props();

  let runs = $state<ValidationRun[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  function runDuration(run: ValidationRun): string {
    if (!run.startedAt) return '\u2014';
    const start = new Date(run.startedAt).getTime();
    const end = run.finishedAt ? new Date(run.finishedAt).getTime() : Date.now();
    return formatDuration(end - start);
  }

  const skippedCount = (run: ValidationRun): number => {
    const total = run.targetCount ?? 0;
    const completed = (run.passedCount ?? 0) + (run.failedCount ?? 0);
    return Math.max(0, total - completed);
  };

  async function fetchRuns(): Promise<void> {
    loading = true;
    error = null;
    try {
      const params = new URLSearchParams({ productId, limit: '20' });
      const res = await apiFetch<ApiResponse<{ data: ValidationRun[]; pagination: Pagination }>>(
        `/v2/validation/runs?${params.toString()}`
      );
      runs = res.data.data;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load validation runs';
    } finally {
      loading = false;
    }
  }

  onMount(() => { fetchRuns(); });
</script>

<div>
  <div class="mb-3 flex items-center justify-between">
    <h3 class="text-sm font-semibold text-[var(--color-text-primary)]">Validation Runs</h3>
    <a href="/validation/runs?productId={productId}"
       class="text-xs font-medium text-[var(--color-accent)] hover:underline">
      View All
    </a>
  </div>

  {#if loading}
    <div class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-0)]">
      {#each Array(3) as _, i}
        <div class="flex items-center gap-4 px-3 py-3" class:border-t={i > 0} class:border-[var(--color-border)]={i > 0}>
          <div class="h-5 w-16 animate-pulse rounded bg-[var(--color-surface-2)]"></div>
          <div class="h-4 w-40 animate-pulse rounded bg-[var(--color-surface-2)]"></div>
          <div class="flex-1"></div>
          <div class="h-4 w-24 animate-pulse rounded bg-[var(--color-surface-2)]"></div>
        </div>
      {/each}
    </div>
  {:else if error}
    <div class="flex items-center gap-2 rounded-lg border border-[var(--color-error)] bg-[var(--color-surface-1)] p-3 text-sm text-[var(--color-error)]">
      <AlertCircle size={14} />
      {error}
    </div>
  {:else if runs.length === 0}
    <div class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-0)] px-4 py-8 text-center text-sm text-[var(--color-text-tertiary)]">
      No validation runs found for this product.
    </div>
  {:else}
    <div class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-0)] overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--color-border)] bg-[var(--color-surface-1)]">
            <th class="px-3 py-2 text-left text-xs font-medium text-[var(--color-text-tertiary)]">Name</th>
            <th class="px-3 py-2 text-left text-xs font-medium text-[var(--color-text-tertiary)]">Status</th>
            <th class="px-3 py-2 text-left text-xs font-medium text-[var(--color-text-tertiary)]">Results</th>
            <th class="px-3 py-2 text-right text-xs font-medium text-[var(--color-text-tertiary)]">Duration</th>
          </tr>
        </thead>
        <tbody>
          {#each runs as run (run.id)}
            <tr
              class="border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-surface-1)] transition-colors cursor-pointer"
              onclick={() => goto(`/validation/runs/${run.id}`)}
            >
              <td class="px-3 py-2">
                <span class="text-sm font-medium text-[var(--color-text-primary)] truncate block max-w-[200px]">
                  {run.name}
                </span>
                <span class="text-xs text-[var(--color-text-tertiary)]">{formatTimeAgo(run.createdAt)}</span>
              </td>
              <td class="px-3 py-2">
                <StatusBadge status={run.status} />
              </td>
              <td class="px-3 py-2">
                <div class="flex items-center gap-3 text-xs">
                  <span class="flex items-center gap-1 text-[var(--color-success)]">
                    <CheckCircle2 size={12} /> {run.passedCount ?? 0}
                  </span>
                  <span class="flex items-center gap-1 text-[var(--color-error)]">
                    <XCircle size={12} /> {run.failedCount ?? 0}
                  </span>
                  {#if skippedCount(run) > 0}
                    <span class="flex items-center gap-1 text-[var(--color-text-tertiary)]">
                      <SkipForward size={12} /> {skippedCount(run)}
                    </span>
                  {/if}
                </div>
              </td>
              <td class="px-3 py-2 text-right">
                <span class="flex items-center justify-end gap-1 text-xs text-[var(--color-text-tertiary)]">
                  <Clock size={12} />
                  {runDuration(run)}
                </span>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
