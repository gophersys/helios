<script lang="ts">
  import { onMount } from 'svelte';
  import { Clock, AlertCircle } from 'lucide-svelte';
  import { fetchPipelines } from '$lib/services/ci';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import type { Pipeline } from '$lib/types/ci';

  interface Props {
    productId: string;
    productName: string;
  }

  let { productId, productName }: Props = $props();

  let pipelines = $state<Pipeline[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  function formatDuration(startedAt: string | null, finishedAt: string | null): string {
    if (!startedAt || !finishedAt) return '\u2014';
    const ms = new Date(finishedAt).getTime() - new Date(startedAt).getTime();
    if (ms < 0) return '\u2014';
    const sec = Math.floor(ms / 1000);
    const min = Math.floor(sec / 60);
    return min > 0 ? `${min}m ${sec % 60}s` : `${sec}s`;
  }

  function relativeTime(dateStr: string): string {
    const diff = Date.now() - new Date(dateStr).getTime();
    const min = Math.floor(diff / 60000);
    if (min < 60) return `${min}m ago`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr}h ago`;
    return `${Math.floor(hr / 24)}d ago`;
  }

  async function load() {
    loading = true;
    error = null;
    try {
      const result = await fetchPipelines({ product: productName, limit: 20 });
      pipelines = result.data;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load pipelines';
    } finally {
      loading = false;
    }
  }

  onMount(() => { load(); });
</script>

<div>
  <div class="mb-3 flex items-center justify-between">
    <h3 class="text-sm font-semibold text-[var(--color-text-primary)]">Pipelines</h3>
    <a href="/builds?product={encodeURIComponent(productName)}"
       class="text-xs font-medium text-[var(--color-accent)] hover:underline">
      View All
    </a>
  </div>

  {#if loading}
    <div class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-0)]">
      {#each Array(4) as _, i}
        <div class="flex items-center gap-4 px-3 py-3" class:border-t={i > 0} class:border-[var(--color-border)]={i > 0}>
          <div class="h-5 w-16 animate-pulse rounded bg-[var(--color-surface-2)]"></div>
          <div class="h-4 w-32 animate-pulse rounded bg-[var(--color-surface-2)]"></div>
          <div class="flex-1"></div>
          <div class="h-4 w-20 animate-pulse rounded bg-[var(--color-surface-2)]"></div>
          <div class="h-4 w-14 animate-pulse rounded bg-[var(--color-surface-2)]"></div>
        </div>
      {/each}
    </div>
  {:else if error}
    <div class="flex items-center gap-2 rounded-lg border border-[var(--color-error)] bg-[var(--color-surface-1)] p-3 text-sm text-[var(--color-error)]">
      <AlertCircle size={14} />
      {error}
    </div>
  {:else if pipelines.length === 0}
    <div class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-0)] px-4 py-8 text-center text-sm text-[var(--color-text-tertiary)]">
      No pipelines found for this product.
    </div>
  {:else}
    <div class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-0)] overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--color-border)] bg-[var(--color-surface-1)]">
            <th class="px-3 py-2 text-left text-xs font-medium text-[var(--color-text-tertiary)]">ID</th>
            <th class="px-3 py-2 text-left text-xs font-medium text-[var(--color-text-tertiary)]">Branch</th>
            <th class="px-3 py-2 text-left text-xs font-medium text-[var(--color-text-tertiary)]">Status</th>
            <th class="px-3 py-2 text-left text-xs font-medium text-[var(--color-text-tertiary)]">Builds</th>
            <th class="px-3 py-2 text-right text-xs font-medium text-[var(--color-text-tertiary)]">Duration</th>
          </tr>
        </thead>
        <tbody>
          {#each pipelines as pipeline (pipeline.id)}
            <tr class="border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-surface-1)] transition-colors">
              <td class="px-3 py-2">
                <a href="/builds/pipelines/{pipeline.id}" class="font-mono text-xs text-[var(--color-accent)] hover:underline">
                  {pipeline.name || pipeline.id.slice(0, 8)}
                </a>
              </td>
              <td class="px-3 py-2 font-mono text-xs text-[var(--color-text-secondary)]">
                {pipeline.branch || '\u2014'}
              </td>
              <td class="px-3 py-2">
                <StatusBadge status={pipeline.status} />
              </td>
              <td class="px-3 py-2 text-xs text-[var(--color-text-secondary)]">
                {pipeline.completedBuilds}/{pipeline.expectedBuilds}
              </td>
              <td class="px-3 py-2 text-right">
                <span class="flex items-center justify-end gap-1 text-xs text-[var(--color-text-tertiary)]">
                  <Clock size={12} />
                  {formatDuration(pipeline.startedAt, pipeline.finishedAt)}
                </span>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
