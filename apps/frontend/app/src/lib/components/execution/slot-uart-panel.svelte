<script lang="ts">
  import UartTerminal from '$lib/components/validation/uart-terminal.svelte';
  import { getSlotContext } from './slot-context.svelte';

  let { socLabels = [] }: { socLabels?: string[] } = $props();

  const ctx = getSlotContext();

  // Derive App/Comms labels from SoC names — nrf52840 is always App, nrf9151/nrf9160 is Comms
  const appSoc = $derived(socLabels.find(s => s.includes('52')) || socLabels[0] || '');
  const commsSoc = $derived(socLabels.find(s => s.includes('91')) || socLabels[1] || '');
  const appLabel = $derived(appSoc ? `${appSoc} (App)` : 'UART App');
  const commsLabel = $derived(commsSoc ? `${commsSoc} (Comms)` : 'UART Comms');
  const showComms = $derived(socLabels.length > 1);
</script>

<div class="grid gap-2 h-full {showComms ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1'}">
  <UartTerminal lines={ctx.effectiveUartApp} label={appLabel} iconColor="text-green-400" />
  {#if showComms}
    <UartTerminal lines={ctx.effectiveUartComms} label={commsLabel} iconColor="text-blue-400" />
  {/if}
</div>
