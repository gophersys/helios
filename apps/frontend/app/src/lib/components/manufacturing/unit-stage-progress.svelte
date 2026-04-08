<script lang="ts">
  import { CheckCircle2, XCircle, Loader2 } from 'lucide-svelte';
  import type { ManufacturingStage } from '$lib/types/models';

  let { stages }: { stages: ManufacturingStage[] } = $props();

  const STAGE_LABELS: Record<string, string> = {
    ELECTRICAL: 'Electrical',
    FLASH: 'Flash',
    POST: 'POST',
  };

  const STAGE_ORDER = ['ELECTRICAL', 'FLASH', 'POST'];

  const orderedStages = $derived(
    STAGE_ORDER.map((type) => {
      const found = stages.find((s) => s.type === type);
      return found || { type, status: 'QUEUED' as const, durationMs: null, errorMessage: null };
    })
  );
</script>

<div class="flex items-center gap-1">
  {#each orderedStages as stage, i (stage.type)}
    {#if i > 0}
      <div class="w-3 h-px {stage.status === 'QUEUED' ? 'bg-border' : stage.status === 'PASSED' ? 'bg-success' : stage.status === 'FAILED' ? 'bg-error' : 'bg-accent'}"></div>
    {/if}
    <div
      class="flex items-center gap-1 rounded px-1.5 py-0.5 text-2xs font-medium
        {stage.status === 'PASSED' ? 'bg-success-muted text-success' :
         stage.status === 'FAILED' ? 'bg-error-muted text-error' :
         stage.status === 'RUNNING' ? 'bg-accent-muted text-accent' :
         'bg-surface-2 text-text-tertiary'}"
      title={stage.errorMessage || STAGE_LABELS[stage.type] || stage.type}
    >
      {#if stage.status === 'RUNNING'}
        <Loader2 size={10} class="animate-spin" />
      {:else if stage.status === 'PASSED'}
        <CheckCircle2 size={10} />
      {:else if stage.status === 'FAILED'}
        <XCircle size={10} />
      {/if}
      {STAGE_LABELS[stage.type] || stage.type}
    </div>
  {/each}
</div>
