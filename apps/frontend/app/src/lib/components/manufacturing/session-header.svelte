<script lang="ts">
  import { onDestroy } from 'svelte';
  import { ArrowLeft } from 'lucide-svelte';
  import { goto } from '$app/navigation';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import { formatDateTime, formatDuration } from '$lib/utils/formatting';
  import type { ManufacturingSession } from '$lib/types/models';

  let { session }: { session: ManufacturingSession } = $props();

  let elapsed = $state('');
  let timer: ReturnType<typeof setInterval> | null = null;

  // Aggregate counts from runs
  const runs = $derived(session.runs || []);
  const panelCount = $derived(runs.length);
  const passCount = $derived(runs.reduce((sum, r) => sum + (r.passedCount || 0), 0));
  const failCount = $derived(runs.reduce((sum, r) => sum + (r.failedCount || 0), 0));

  function updateElapsed() {
    if (!session.startedAt) {
      elapsed = '';
      return;
    }
    const start = new Date(session.startedAt).getTime();
    const end = session.endedAt ? new Date(session.endedAt).getTime() : Date.now();
    elapsed = formatDuration(end - start);
  }

  $effect(() => {
    updateElapsed();
    if (session.status === 'ACTIVE' && !timer) {
      timer = setInterval(updateElapsed, 1000);
    } else if (session.status !== 'ACTIVE' && timer) {
      clearInterval(timer);
      timer = null;
    }
  });

  onDestroy(() => {
    if (timer) clearInterval(timer);
  });
</script>

<div class="mb-4">
  <button
    onclick={() => goto('/manufacturing')}
    class="mb-3 flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
  >
    <ArrowLeft size={14} />
    Manufacturing
  </button>

  <div class="flex items-start justify-between gap-4">
    <div>
      <div class="flex items-center gap-3 mb-1">
        <h1 class="text-lg font-semibold text-text-primary">
          {session.product?.name || 'Session'}
        </h1>
        <StatusBadge status={session.status} />
      </div>

      <div class="flex items-center gap-4 text-xs text-text-secondary">
        {#if session.fixture?.name}
          <span>Fixture: <span class="font-medium text-text-primary">{session.fixture.name}</span></span>
        {/if}
        {#if session.operator?.name}
          <span>Operator: <span class="font-medium text-text-primary">{session.operator.name}</span></span>
        {/if}
        {#if session.startedAt}
          <span title={formatDateTime(session.startedAt)}>
            Started: <span class="font-medium text-text-primary">{formatDateTime(session.startedAt)}</span>
          </span>
        {/if}
        {#if elapsed}
          <span>Elapsed: <span class="font-medium text-text-primary tabular-nums">{elapsed}</span></span>
        {/if}
      </div>
    </div>

    <div class="flex items-center gap-3 text-xs">
      <div class="text-center">
        <div class="text-lg font-semibold text-text-primary">{panelCount}</div>
        <div class="text-text-tertiary">Panels</div>
      </div>
      <div class="text-center">
        <div class="text-lg font-semibold text-success">{passCount}</div>
        <div class="text-text-tertiary">Pass</div>
      </div>
      <div class="text-center">
        <div class="text-lg font-semibold {failCount > 0 ? 'text-error' : 'text-text-primary'}">{failCount}</div>
        <div class="text-text-tertiary">Fail</div>
      </div>
    </div>
  </div>
</div>
