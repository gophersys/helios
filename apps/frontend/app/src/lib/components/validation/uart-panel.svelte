<script lang="ts">
  import UartTerminal from '$lib/components/validation/uart-terminal.svelte';
  import { getRunContext } from './run-context.svelte';

  const ctx = getRunContext();
</script>

<div class="grid grid-cols-1 md:grid-cols-2 gap-2 h-full">
  <UartTerminal lines={ctx.effectiveUartApp} label="nRF52840" iconColor="text-green-400" />
  <UartTerminal lines={ctx.effectiveUartComms} label="nRF9151" iconColor="text-blue-400" />
</div>
