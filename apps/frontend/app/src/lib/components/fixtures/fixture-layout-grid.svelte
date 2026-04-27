<script lang="ts" module>
  export interface FixtureLayoutSlot {
    id?: string;
    slotIndex: number;
    label?: string | null;
    node?: {
      id: string;
      name: string;
      hostname: string;
      status: string;
    } | null;
    mtibReady?: boolean | null;
  }
</script>

<script lang="ts">
  import type { Snippet } from 'svelte';
  import { LayoutGrid } from 'lucide-svelte';

  let {
    panelRows = 1,
    panelCols = 1,
    hasStandaloneSlot = false,
    slots = [],
    slotContent,
    onSlotClick,
  }: {
    panelRows?: number;
    panelCols?: number;
    hasStandaloneSlot?: boolean;
    slots?: FixtureLayoutSlot[];
    slotContent?: Snippet<[FixtureLayoutSlot]>;
    onSlotClick?: (slotIndex: number) => void;
  } = $props();

  const panelSlotCount = $derived(panelRows * panelCols);

  const standaloneSlot = $derived(
    hasStandaloneSlot
      ? slots.find((s) => s.slotIndex === panelSlotCount)
      : undefined
  );

  const panelSlots = $derived.by(() => {
    const result: { index: number; slot: FixtureLayoutSlot | undefined }[] = [];
    for (let i = 0; i < panelSlotCount; i++) {
      result.push({ index: i, slot: slots.find((s) => s.slotIndex === i) });
    }
    return result;
  });

  function statusDot(slot: FixtureLayoutSlot | undefined): string {
    if (!slot || !slot.node) return 'bg-surface-2 border border-border';
    const status = slot.node.status;
    if (status === 'ONLINE' && slot.mtibReady) return 'bg-success';
    if (status === 'ONLINE') return 'bg-warning';
    if (status === 'ERROR') return 'bg-error';
    return 'bg-surface-2 border border-border';
  }

  function tileClasses(slot: FixtureLayoutSlot | undefined): string {
    if (!slot) return 'bg-surface-2 border-border text-text-tertiary';
    if (!slot.node) return 'bg-surface-2 border-border-subtle text-text-tertiary';
    const status = slot.node.status;
    if (status === 'ONLINE' && slot.mtibReady) return 'bg-success-muted border-success text-success';
    if (status === 'ONLINE') return 'bg-warning-muted border-warning text-warning';
    if (status === 'ERROR') return 'bg-error-muted border-error text-error';
    return 'bg-surface-2 border-border text-text-secondary';
  }
</script>

<div class="space-y-4">
  <!-- Panel grid -->
  <div class="rounded-lg border border-border bg-surface-0 p-4">
    <div class="flex items-center gap-2 mb-3">
      <LayoutGrid size={14} class="text-text-tertiary" />
      <span class="text-2xs font-semibold text-text-tertiary uppercase tracking-wider">Panel &middot; Top-Down View</span>
      <span class="text-2xs text-text-tertiary ml-auto">{panelSlotCount} slot{panelSlotCount !== 1 ? 's' : ''} &middot; {panelRows}&times;{panelCols}</span>
    </div>

    <div
      class="grid gap-2 mx-auto"
      style="grid-template-columns: repeat({panelCols}, minmax(0, 1fr)); max-width: {Math.min(panelCols * 140, 700)}px;"
    >
      {#each panelSlots as entry (entry.index)}
        {@const slot = entry.slot}
        <button
          type="button"
          onclick={() => onSlotClick?.(entry.index)}
          class="flex flex-col items-stretch justify-start rounded-lg border-2 min-h-20 p-2 text-left transition-all cursor-pointer hover:shadow-card-hover {tileClasses(slot)}"
        >
          {#if slotContent && slot}
            {@render slotContent(slot)}
          {:else}
            <div class="flex items-center gap-2">
              <span class="h-2 w-2 rounded-full {statusDot(slot)}"></span>
              <span class="text-xs font-semibold">{entry.index + 1}</span>
              {#if slot?.label}
                <span class="text-2xs text-text-tertiary truncate">{slot.label}</span>
              {/if}
            </div>
            <div class="mt-1 min-w-0">
              {#if slot?.node}
                <p class="text-2xs font-medium truncate">{slot.node.name}</p>
                <p class="text-2xs font-mono text-text-tertiary truncate">{slot.node.hostname}</p>
              {:else}
                <p class="text-2xs text-text-tertiary">Unassigned</p>
              {/if}
            </div>
          {/if}
        </button>
      {/each}
    </div>
  </div>

  <!-- Standalone slot -->
  {#if hasStandaloneSlot}
    <div class="rounded-lg border border-border bg-surface-0 p-4">
      <div class="flex items-center gap-2 mb-3">
        <LayoutGrid size={14} class="text-text-tertiary" />
        <span class="text-2xs font-semibold text-text-tertiary uppercase tracking-wider">Standalone Slot</span>
      </div>

      <div class="flex justify-center">
        <button
          type="button"
          onclick={() => onSlotClick?.(panelSlotCount)}
          class="flex flex-col items-stretch justify-start rounded-lg border-2 min-h-20 w-40 p-2 text-left transition-all cursor-pointer hover:shadow-card-hover {tileClasses(standaloneSlot)}"
        >
          {#if slotContent && standaloneSlot}
            {@render slotContent(standaloneSlot)}
          {:else}
            <div class="flex items-center gap-2">
              <span class="h-2 w-2 rounded-full {statusDot(standaloneSlot)}"></span>
              <span class="text-xs font-semibold">SA</span>
            </div>
            <div class="mt-1 min-w-0">
              {#if standaloneSlot?.node}
                <p class="text-2xs font-medium truncate">{standaloneSlot.node.name}</p>
                <p class="text-2xs font-mono text-text-tertiary truncate">{standaloneSlot.node.hostname}</p>
              {:else}
                <p class="text-2xs text-text-tertiary">Unassigned</p>
              {/if}
            </div>
          {/if}
        </button>
      </div>
    </div>
  {/if}
</div>
