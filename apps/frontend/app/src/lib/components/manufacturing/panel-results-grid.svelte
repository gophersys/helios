<script lang="ts">
  import { CheckCircle2, XCircle } from 'lucide-svelte';
  import UnitCard from './unit-card.svelte';
  import type { TestRun } from '$lib/types/models';

  let { panel, onSelectUnit }: { panel: TestRun; onSelectUnit?: (target: import('$lib/types/models').RunTarget) => void } = $props();

  const targets = $derived(panel.targets || []);

  const completedCount = $derived(
    targets.filter((t) => t.status === 'PASSED' || t.status === 'FAILED' || t.status === 'ERROR').length
  );
</script>

<div>
  <!-- Panel summary bar -->
  <div class="flex items-center justify-between mb-3">
    <div class="flex items-center gap-3 text-xs">
      <span class="font-mono text-text-secondary">{panel.panelIdentifier || panel.name || panel.id.slice(0, 8)}</span>
      <div class="flex items-center gap-2">
        <span class="flex items-center gap-1">
          <CheckCircle2 size={12} class="text-success" />
          <span class="font-medium text-text-primary">{panel.passedCount}</span>
        </span>
        {#if panel.failedCount > 0}
          <span class="flex items-center gap-1 text-error">
            <XCircle size={12} />
            <span class="font-medium">{panel.failedCount}</span>
          </span>
        {/if}
        <span class="text-text-tertiary">/ {panel.targetCount} units</span>
      </div>
    </div>

    {#if panel.targetCount > 0}
      <div class="w-24 h-1.5 bg-surface-2 rounded-full overflow-hidden flex-shrink-0">
        <div
          class="h-full rounded-full transition-all duration-500 {panel.failedCount > 0 ? 'bg-error' : panel.status === 'ACTIVE' ? 'bg-accent' : 'bg-success'}"
          style="width: {Math.round(completedCount / panel.targetCount * 100)}%"
        ></div>
      </div>
    {/if}
  </div>

  <!-- Target grid -->
  <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
    {#each targets as target (target.id)}
      <UnitCard unit={target} onclick={onSelectUnit ? () => onSelectUnit(target) : undefined} />
    {/each}
  </div>
</div>
