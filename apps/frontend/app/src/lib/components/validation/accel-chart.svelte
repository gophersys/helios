<script lang="ts">
  import { Cpu } from 'lucide-svelte';
  import type { AccelSample } from './types';

  interface Props {
    samples: AccelSample[];
  }

  let { samples }: Props = $props();
</script>

<div class="rounded-lg border border-border bg-surface-0 overflow-hidden flex flex-col h-full">
  <div class="flex items-center gap-2 px-3 py-1.5 border-b border-border bg-surface-1 flex-shrink-0">
    <Cpu size={12} class="text-accent" />
    <span class="text-xs font-medium text-text-primary">Accelerometer</span>
    <span class="ml-auto text-2xs text-text-tertiary">{samples.length > 0 ? `${samples.length} samples` : 'No data'}</span>
  </div>
  <div class="bg-[#0d1117] flex-1 overflow-hidden">
    {#if samples.length > 0}
      <!-- TODO: XYZ line chart similar to PowerChart -->
      <div class="w-full h-full flex items-center justify-center">
        <div class="text-xs text-text-tertiary">{samples.length} samples</div>
      </div>
    {:else}
      <div class="w-full h-full flex items-center justify-center">
        <div class="text-center">
          <Cpu size={24} class="mx-auto text-text-tertiary opacity-20 mb-2" />
          <div class="text-xs text-text-tertiary">Waiting for accelerometer data</div>
          <div class="text-2xs text-text-tertiary mt-1 opacity-60">XYZ from MTIB motion controller</div>
        </div>
      </div>
    {/if}
  </div>
</div>
