<script lang="ts">
  import { CheckCircle2, Loader2, XCircle } from 'lucide-svelte';

  interface SlotTab {
    index: number;
    label: string;
    serialNumber?: string;
    status: string;
  }

  let {
    slots,
    activeIndex,
    onSelect,
  }: {
    slots: SlotTab[];
    activeIndex: number;
    onSelect: (index: number) => void;
  } = $props();

  // Hidden for single-slot mode
  const visible = $derived(slots.length > 1);
</script>

{#if visible}
  <div class="flex items-center gap-1 mb-3 overflow-x-auto pb-1">
    {#each slots as slot (slot.index)}
      <button
        onclick={() => onSelect(slot.index)}
        class="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors flex-shrink-0
          {activeIndex === slot.index
            ? 'bg-accent-muted border border-accent/30 text-text-primary font-medium'
            : 'hover:bg-surface-1 text-text-secondary border border-transparent'
          }"
      >
        <!-- Status dot -->
        <div class="flex-shrink-0">
          {#if slot.status === 'RUNNING'}
            <span class="relative flex h-2 w-2">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
              <span class="relative inline-flex rounded-full h-2 w-2 bg-accent"></span>
            </span>
          {:else if slot.status === 'PASSED'}
            <CheckCircle2 size={12} class="text-success" />
          {:else if slot.status === 'FAILED' || slot.status === 'ERROR'}
            <XCircle size={12} class="text-error" />
          {:else}
            <span class="inline-flex rounded-full h-2 w-2 bg-text-tertiary/40"></span>
          {/if}
        </div>

        <!-- Label -->
        <span>{slot.label}</span>

        <!-- Serial number -->
        {#if slot.serialNumber}
          <span class="font-mono text-2xs text-text-tertiary">{slot.serialNumber}</span>
        {/if}
      </button>
    {/each}
  </div>
{/if}
