<script lang="ts">
  import UartTerminal from '$lib/components/validation/uart-terminal.svelte';
  import { getSlotContext } from './slot-context.svelte';

  let { socLabels = [] }: { socLabels?: string[] } = $props();

  const ctx = getSlotContext();

  // Dynamic labels from boardRevision.socs, with fallbacks
  const appLabel = $derived(socLabels[0] ? `${socLabels[0]} (App)` : 'UART App');
  const commsLabel = $derived(socLabels[1] ? `${socLabels[1]} (Comms)` : socLabels.length === 1 ? 'UART Comms' : 'UART Comms');
  const showComms = $derived(socLabels.length !== 1); // Hide comms if only one SOC
</script>

<div class="grid gap-2 h-full {showComms ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1'}">
  <UartTerminal lines={ctx.effectiveUartApp} label={appLabel} iconColor="text-green-400" />
  {#if showComms}
    <UartTerminal lines={ctx.effectiveUartComms} label={commsLabel} iconColor="text-blue-400" />
  {/if}
</div>
