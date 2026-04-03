<script lang="ts">
  import PowerChart from '$lib/components/validation/power-chart.svelte';
  import AccelChart from '$lib/components/validation/accel-chart.svelte';
  import { getRunContext } from './run-context.svelte';

  const ctx = getRunContext();
</script>

<div class="flex-shrink-0" style="min-height: 232px; height: 232px;">
  <PowerChart
    samples={ctx.effectivePower}
    chgSamples={ctx.effectivePowerChg}
    jsSamples={ctx.effectivePowerJs}
    windowSeconds={ctx.analysisMode ? 99999 : ctx.POWER_WINDOW_S}
  />
</div>
<div class="flex-shrink-0" style="min-height: 232px; height: 232px;">
  <AccelChart
    samples={ctx.accelSamples}
    windowSeconds={ctx.analysisMode ? 99999 : ctx.POWER_WINDOW_S}
  />
</div>
