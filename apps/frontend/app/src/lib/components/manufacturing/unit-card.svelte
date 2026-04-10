<script lang="ts">
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import MeasurementsDisplay from '$lib/components/ui/measurements-display.svelte';
  import UnitStageProgress from './unit-stage-progress.svelte';
  import { formatDuration } from '$lib/utils/formatting';
  import type { RunTarget } from '$lib/types/models';

  let { unit }: { unit: RunTarget } = $props();

  const duration = $derived.by(() => {
    if (!unit.startedAt) return null;
    const start = new Date(unit.startedAt).getTime();
    const end = unit.completedAt ? new Date(unit.completedAt).getTime() : Date.now();
    return formatDuration(end - start);
  });
</script>

<div class="rounded-lg border border-border bg-surface-0 p-3 transition-colors
  {unit.status === 'PASSED' ? 'border-success/30' :
   unit.status === 'FAILED' ? 'border-error/30' :
   unit.status === 'RUNNING' ? 'border-accent/30' : ''}">
  <!-- Header: slot label + status -->
  <div class="flex items-center justify-between mb-2">
    <div class="flex items-center gap-2">
      <span class="text-xs font-semibold text-text-primary">
        Slot {unit.slotIndex + 1}
      </span>
      {#if unit.serialNumber}
        <span class="text-2xs font-mono text-text-tertiary">{unit.serialNumber}</span>
      {/if}
    </div>
    <StatusBadge status={unit.status} />
  </div>

  <!-- Execution progress -->
  <UnitStageProgress executions={unit.executions || []} />

  <!-- Execution measurements -->
  {#each (unit.executions || []) as exec (exec.id)}
    {#if exec.measurements && Object.keys(exec.measurements).length > 0}
      <MeasurementsDisplay measurements={exec.measurements} />
    {/if}
  {/each}

  <!-- Footer: duration + error -->
  <div class="mt-2 flex items-center justify-between">
    {#if duration}
      <span class="text-2xs tabular-nums text-text-tertiary">{duration}</span>
    {:else}
      <span></span>
    {/if}
  </div>

  {#if unit.errorMessage}
    <p class="mt-1.5 text-2xs text-error bg-error-muted rounded px-2 py-1 truncate" title={unit.errorMessage}>
      {unit.errorMessage}
    </p>
  {/if}
</div>
