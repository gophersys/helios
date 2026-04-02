<script lang="ts">
  import { Check, X, Minus, Loader2 } from 'lucide-svelte';

  const STAGE_LABELS: Record<number, string> = {
    1: 'SM',
    2: 'SI',
    3: 'IN',
    4: 'NY',
    5: 'FU',
  };

  let {
    stages,
    onStageClick,
  }: {
    stages: Record<number, { status: string; enabled: boolean } | null>;
    onStageClick?: (stage: number) => void;
  } = $props();

  function getStageStyle(stage: { status: string; enabled: boolean } | null | undefined) {
    if (!stage || !stage.enabled) {
      return { class: 'bg-surface-2 text-text-tertiary', icon: Minus, spin: false };
    }
    const s = stage.status.toUpperCase();
    if (s === 'PASSED' || s === 'SUCCESS' || s === 'COMPLETED') {
      return { class: 'bg-success-muted text-success', icon: Check, spin: false };
    }
    if (s === 'FAILED' || s === 'ERROR') {
      return { class: 'bg-error-muted text-error', icon: X, spin: false };
    }
    if (s === 'RUNNING' || s === 'BUILDING' || s === 'VALIDATING') {
      return { class: 'bg-warning-muted text-warning', icon: Loader2, spin: true };
    }
    return { class: 'bg-surface-2 text-text-secondary', icon: Minus, spin: false };
  }
</script>

<div class="inline-flex items-center gap-1">
  {#each [1, 2, 3, 4, 5] as num}
    {@const stage = stages[num]}
    {@const style = getStageStyle(stage)}
    {@const clickable = !!onStageClick}
    <button
      type="button"
      disabled={!clickable}
      onclick={() => onStageClick?.(num)}
      class="inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-2xs font-medium transition-colors {style.class} {clickable ? 'cursor-pointer hover:opacity-80' : 'cursor-default'}"
      title="Stage {num}: {STAGE_LABELS[num]}"
    >
      {STAGE_LABELS[num]}
      <style.icon size={10} strokeWidth={2.5} class={style.spin ? 'animate-spin' : ''} />
    </button>
  {/each}
</div>
