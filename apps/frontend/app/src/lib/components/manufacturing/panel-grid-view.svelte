<script lang="ts">
  import { LayoutGrid } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import type { RunTarget } from '$lib/types/models';

  let {
    panelRows = 1,
    panelCols = 1,
    hasStandaloneSlot = false,
    targets = [],
    onSlotClick,
  }: {
    panelRows?: number;
    panelCols?: number;
    hasStandaloneSlot?: boolean;
    targets?: RunTarget[];
    onSlotClick?: (slotIndex: number) => void;
  } = $props();

  const panelSlotCount = $derived(panelRows * panelCols);
  const totalSlotCount = $derived(panelSlotCount + (hasStandaloneSlot ? 1 : 0));

  // Build slot list: panel slots (row-major) + optional standalone
  const slots = $derived.by(() => {
    const result: { index: number; standalone: boolean }[] = [];
    for (let i = 0; i < panelSlotCount; i++) {
      result.push({ index: i, standalone: false });
    }
    if (hasStandaloneSlot) {
      result.push({ index: panelSlotCount, standalone: true });
    }
    return result;
  });

  function getTarget(slotIndex: number): RunTarget | undefined {
    return targets.find((t) => t.slotIndex === slotIndex);
  }

  function slotClasses(target: RunTarget | undefined): string {
    if (!target) return 'bg-surface-2 border-border text-text-tertiary';
    switch (target.status) {
      case 'PENDING':
        return 'bg-surface-2 border-border text-text-secondary';
      case 'RUNNING':
        return 'bg-accent-muted border-accent animate-pulse text-accent';
      case 'PASSED':
        return 'bg-success-muted border-success text-success';
      case 'FAILED':
      case 'ERROR':
        return 'bg-error-muted border-error text-error';
      default:
        return 'bg-surface-2 border-border text-text-tertiary';
    }
  }
</script>

<div class="rounded-lg border border-border bg-surface-0 p-4">
  <!-- Label -->
  <div class="flex items-center gap-2 mb-3">
    <LayoutGrid size={14} class="text-text-tertiary" />
    <span class="text-2xs font-semibold text-text-tertiary uppercase tracking-wider">Top-Down View</span>
    <span class="text-2xs text-text-tertiary ml-auto">{totalSlotCount} slot{totalSlotCount !== 1 ? 's' : ''}</span>
  </div>

  <!-- Panel grid -->
  <div
    class="grid gap-2 mx-auto"
    style="grid-template-columns: repeat({panelCols}, minmax(0, 1fr)); max-width: {Math.min(panelCols * 100, 600)}px;"
  >
    {#each slots.filter((s) => !s.standalone) as slot (slot.index)}
      {@const target = getTarget(slot.index)}
      <button
        type="button"
        onclick={() => onSlotClick?.(slot.index)}
        class="flex flex-col items-center justify-center rounded-lg border-2 aspect-square min-h-16
          transition-all cursor-pointer hover:shadow-card-hover {slotClasses(target)}"
      >
        <span class="text-xs font-semibold">{slot.index + 1}</span>
        {#if target?.serialNumber}
          <span class="text-2xs font-mono truncate max-w-full px-1">{target.serialNumber}</span>
        {:else}
          <span class="text-2xs opacity-50">Idle</span>
        {/if}
        {#if target}
          <div class="mt-0.5">
            <StatusBadge status={target.status} />
          </div>
        {/if}
      </button>
    {/each}
  </div>

  <!-- Standalone slot -->
  {#if hasStandaloneSlot}
    {@const standaloneTarget = getTarget(panelSlotCount)}
    <div class="mt-4 pt-4 border-t border-border-subtle">
      <button
        type="button"
        onclick={() => onSlotClick?.(panelSlotCount)}
        class="flex items-center gap-3 w-full text-left rounded-lg p-2 transition-colors hover:bg-surface-2 cursor-pointer"
      >
        <div
          class="flex flex-col items-center justify-center rounded-lg border-2 w-16 h-16 shrink-0
            {standaloneTarget ? slotClasses(standaloneTarget) : 'border-warning/30 bg-warning-muted/30 text-warning'}"
        >
          <span class="text-xs font-semibold">{panelSlotCount + 1}</span>
          <span class="text-2xs">SA</span>
        </div>
        <div class="min-w-0">
          <p class="text-xs font-medium text-text-primary">Standalone Slot</p>
          {#if standaloneTarget?.serialNumber}
            <p class="text-2xs font-mono text-text-tertiary truncate">{standaloneTarget.serialNumber}</p>
          {:else}
            <p class="text-2xs text-text-tertiary">Not assigned</p>
          {/if}
          {#if standaloneTarget}
            <div class="mt-0.5">
              <StatusBadge status={standaloneTarget.status} />
            </div>
          {/if}
        </div>
      </button>
    </div>
  {/if}
</div>
