<script lang="ts">
  import { LayoutGrid, QrCode } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import type { RunTarget } from '$lib/types/models';
  import { actionable } from '$lib/actions/actionable';

  let {
    panelRows = 1,
    panelCols = 1,
    hasStandaloneSlot = false,
    targets = [],
    scannable = false,
    onScanPanel,
    onScanStandalone,
    onSlotClick,
  }: {
    panelRows?: number;
    panelCols?: number;
    hasStandaloneSlot?: boolean;
    targets?: RunTarget[];
    scannable?: boolean;
    onScanPanel?: () => void;
    onScanStandalone?: () => void;
    onSlotClick?: (slotIndex: number) => void;
  } = $props();

  const panelSlotCount = $derived(panelRows * panelCols);
  const totalSlotCount = $derived(panelSlotCount + (hasStandaloneSlot ? 1 : 0));

  // Panel slots have targets assigned
  const panelHasTargets = $derived(
    targets.some(t => t.slotIndex < panelSlotCount)
  );

  // Standalone slot has a target assigned
  const standaloneTarget = $derived(
    hasStandaloneSlot ? targets.find(t => t.slotIndex === panelSlotCount) : undefined
  );

  const slots = $derived.by(() => {
    const result: { index: number; standalone: boolean }[] = [];
    for (let i = 0; i < panelSlotCount; i++) {
      result.push({ index: i, standalone: false });
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

  let panelHovered = $state(false);
  let standaloneHovered = $state(false);
</script>

<div class="space-y-4">
  <!-- Panel grid widget -->
  <div
    use:actionable={{ id: 'scan-panel', label: 'Scan panel' }}
    class="rounded-lg border border-border bg-surface-0 p-4 relative transition-all
      {scannable ? 'cursor-pointer hover:border-accent hover:shadow-card-hover group' : ''}"
    role={scannable ? 'button' : undefined}
    tabindex={scannable ? 0 : undefined}
    onclick={() => { if (scannable) onScanPanel?.(); }}
    onkeydown={(e) => { if (e.key === 'Enter' && scannable) onScanPanel?.(); }}
    onmouseenter={() => { panelHovered = true; }}
    onmouseleave={() => { panelHovered = false; }}
  >
    <!-- Label -->
    <div class="flex items-center gap-2 mb-3">
      <LayoutGrid size={14} class="text-text-tertiary" />
      <span class="text-2xs font-semibold text-text-tertiary uppercase tracking-wider">Panel &middot; Top-Down View</span>
      <span class="text-2xs text-text-tertiary ml-auto">{panelSlotCount} slots &middot; {panelRows}&times;{panelCols}</span>
    </div>

    <!-- Scan overlay (always shown when scannable — covers previous results too) -->
    {#if scannable}
      <div class="absolute inset-0 flex items-center justify-center rounded-lg transition-opacity z-10
        {panelHovered ? 'opacity-100 bg-accent/5' : 'opacity-0'}">
        <div class="flex items-center gap-2 text-accent font-medium text-sm">
          <QrCode size={18} />
          Click to scan panel
        </div>
      </div>
    {/if}

    <!-- Grid -->
    <div
      class="grid gap-2 mx-auto {scannable && panelHovered ? 'opacity-30' : ''} transition-opacity"
      style="grid-template-columns: repeat({panelCols}, minmax(0, 1fr)); max-width: {Math.min(panelCols * 120, 600)}px;"
    >
      {#each slots as slot (slot.index)}
        {@const target = getTarget(slot.index)}
        <button
          type="button"
          onclick={(e) => {
            if (target) { e.stopPropagation(); onSlotClick?.(slot.index); }
          }}
          disabled={!target}
          class="flex flex-col items-center justify-center rounded-lg border-2 aspect-square min-h-16
            transition-all {target ? 'cursor-pointer hover:shadow-card-hover' : ''} {slotClasses(target)}"
        >
          <span class="text-xs font-semibold">{slot.index + 1}</span>
          {#if target?.serialNumber}
            <span class="text-2xs font-mono truncate max-w-full px-1">{target.serialNumber}</span>
          {:else}
            <span class="text-2xs opacity-50">—</span>
          {/if}
          {#if target}
            <div class="mt-0.5">
              <StatusBadge status={target.status} />
            </div>
          {/if}
        </button>
      {/each}
    </div>
  </div>

  <!-- Standalone slot widget -->
  {#if hasStandaloneSlot}
    <div
      use:actionable={{ id: 'scan-standalone', label: 'Scan standalone slot' }}
      class="rounded-lg border border-border bg-surface-0 p-4 relative transition-all
        {scannable ? 'cursor-pointer hover:border-accent hover:shadow-card-hover group' : ''}"
      role={scannable ? 'button' : undefined}
      tabindex={scannable ? 0 : undefined}
      onclick={() => { if (scannable) onScanStandalone?.(); }}
      onkeydown={(e) => { if (e.key === 'Enter' && scannable) onScanStandalone?.(); }}
      onmouseenter={() => { standaloneHovered = true; }}
      onmouseleave={() => { standaloneHovered = false; }}
    >
      <!-- Scan overlay -->
      {#if scannable}
        <div class="absolute inset-0 flex items-center justify-center rounded-lg transition-opacity z-10
          {standaloneHovered ? 'opacity-100 bg-accent/5' : 'opacity-0'}">
          <div class="flex items-center gap-2 text-accent font-medium text-sm">
            <QrCode size={18} />
            Click to scan standalone
          </div>
        </div>
      {/if}

      <div class="{scannable && standaloneHovered ? 'opacity-30' : ''} transition-opacity">
        <div class="flex items-center gap-2 mb-3">
          <LayoutGrid size={14} class="text-text-tertiary" />
          <span class="text-2xs font-semibold text-text-tertiary uppercase tracking-wider">Standalone Slot</span>
        </div>

        <div class="flex justify-center">
          <button
            type="button"
            onclick={(e) => { if (standaloneTarget) { e.stopPropagation(); onSlotClick?.(panelSlotCount); } }}
            disabled={!standaloneTarget}
            class="flex flex-col items-center justify-center rounded-lg border-2 aspect-square min-h-16 w-24
              transition-all {standaloneTarget ? 'cursor-pointer hover:shadow-card-hover' : ''}
              {standaloneTarget ? slotClasses(standaloneTarget) : 'border-border-subtle bg-surface-2 text-text-tertiary'}"
          >
            <span class="text-xs font-semibold">{panelSlotCount + 1}</span>
            {#if standaloneTarget?.serialNumber}
              <span class="text-2xs font-mono truncate max-w-full px-1">{standaloneTarget.serialNumber}</span>
              <div class="mt-0.5"><StatusBadge status={standaloneTarget.status} /></div>
            {:else}
              <span class="text-2xs opacity-50">SA</span>
            {/if}
          </button>
        </div>
      </div>
    </div>
  {/if}
</div>
