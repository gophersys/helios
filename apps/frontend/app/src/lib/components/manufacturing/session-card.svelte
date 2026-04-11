<script lang="ts">
  import { goto } from '$app/navigation';
  import { CheckCircle2, XCircle } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import { formatTimeAgo, formatDuration, formatDateTime } from '$lib/utils/formatting';
  import type { ManufacturingSession } from '$lib/types/models';

  let { session }: { session: ManufacturingSession } = $props();

  // Aggregate counts from runs when available
  const runs = $derived(session.runs || []);
  const runCount = $derived(runs.length);
  const passCount = $derived(runs.reduce((sum, r) => sum + (r.passedCount || 0), 0));
  const failCount = $derived(runs.reduce((sum, r) => sum + (r.failedCount || 0), 0));

  const duration = $derived.by(() => {
    if (!session.startedAt) return null;
    const start = new Date(session.startedAt).getTime();
    const end = session.endedAt ? new Date(session.endedAt).getTime() : Date.now();
    return formatDuration(end - start);
  });
</script>

<button
  onclick={() => goto(`/manufacturing/session/${session.id}`)}
  class="flex w-full items-center gap-4 px-4 py-3 text-left transition-colors hover:bg-surface-2/50"
>
  <!-- Left: Session info -->
  <div class="min-w-0 flex-1">
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-sm font-medium text-text-primary">
        {session.product?.name || 'Unknown Product'}
      </span>
      {#if session.fixture?.name}
        <span class="inline-flex items-center rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-secondary">
          {session.fixture.name}
        </span>
      {/if}
      {#if session.operator?.name}
        <span class="text-2xs text-text-tertiary">
          {session.operator.name}
        </span>
      {/if}
    </div>

    <div class="flex items-center gap-3 mt-1.5 text-2xs">
      <StatusBadge status={session.status} />

      <span class="flex items-center gap-1">
        <CheckCircle2 size={11} class="text-success" />
        <span class="text-text-primary font-medium">{passCount}</span>
      </span>
      {#if failCount > 0}
        <span class="flex items-center gap-1 text-error">
          <XCircle size={11} />
          <span class="font-medium">{failCount}</span>
        </span>
      {/if}
      <span class="text-text-tertiary">
        {runCount} {runCount === 1 ? 'panel' : 'panels'}
      </span>
    </div>
  </div>

  <!-- Right: Duration + time -->
  <div class="flex flex-col items-end gap-1 text-2xs text-text-tertiary shrink-0">
    {#if duration}
      <span class="tabular-nums">{duration}</span>
    {/if}
    {#if session.startedAt}
      <span title={formatDateTime(session.startedAt)}>
        {formatTimeAgo(session.startedAt)}
      </span>
    {/if}
  </div>
</button>
