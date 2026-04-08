<script lang="ts">
  import { CheckCircle2, XCircle } from 'lucide-svelte';
  import UnitCard from './unit-card.svelte';
  import type { ManufacturingPanel } from '$lib/types/models';

  let { panel }: { panel: ManufacturingPanel } = $props();

  const completedCount = $derived(
    panel.units.filter((u) => u.status === 'PASSED' || u.status === 'FAILED').length
  );
</script>

<div>
  <!-- Panel summary bar -->
  <div class="flex items-center justify-between mb-3">
    <div class="flex items-center gap-3 text-xs">
      <span class="font-mono text-text-secondary">{panel.qrCode}</span>
      <div class="flex items-center gap-2">
        <span class="flex items-center gap-1">
          <CheckCircle2 size={12} class="text-success" />
          <span class="font-medium text-text-primary">{panel.passCount}</span>
        </span>
        {#if panel.failCount > 0}
          <span class="flex items-center gap-1 text-error">
            <XCircle size={12} />
            <span class="font-medium">{panel.failCount}</span>
          </span>
        {/if}
        <span class="text-text-tertiary">/ {panel.unitCount} units</span>
      </div>
    </div>

    {#if panel.unitCount > 0}
      <div class="w-24 h-1.5 bg-surface-2 rounded-full overflow-hidden flex-shrink-0">
        <div
          class="h-full rounded-full transition-all duration-500 {panel.failCount > 0 ? 'bg-error' : panel.status === 'RUNNING' ? 'bg-accent' : 'bg-success'}"
          style="width: {Math.round(completedCount / panel.unitCount * 100)}%"
        ></div>
      </div>
    {/if}
  </div>

  <!-- Unit grid -->
  <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
    {#each panel.units as unit (unit.id)}
      <UnitCard {unit} />
    {/each}
  </div>
</div>
