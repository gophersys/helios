<script lang="ts">
  import {
    Hammer,
    Zap,
    FlaskConical,
    CheckCircle2,
    XCircle,
    Loader2,
    Circle,
    SkipForward,
    ArrowRight,
  } from 'lucide-svelte';
  import type { BuildRunStageInfo, BuildRunStageStatus } from '$lib/types/ci';

  let { stages }: { stages: BuildRunStageInfo[] } = $props();

  const STAGE_ICONS: Record<string, typeof Hammer> = {
    BUILD: Hammer,
    FLASH: Zap,
    VALIDATE: FlaskConical,
  };

  const STAGE_LABELS: Record<string, string> = {
    BUILD: 'Build',
    FLASH: 'Flash',
    VALIDATE: 'Validate',
  };

  function statusColor(status: BuildRunStageStatus): string {
    switch (status) {
      case 'SUCCESS': return 'bg-success-muted text-success border-success/20';
      case 'RUNNING': return 'bg-accent-muted text-accent border-accent/20';
      case 'FAILED': return 'bg-error-muted text-error border-error/20';
      case 'SKIPPED': return 'bg-surface-2 text-text-tertiary border-border';
      case 'PENDING':
      default: return 'bg-surface-1 text-text-tertiary border-border';
    }
  }

  function statusChipColor(status: BuildRunStageStatus): string {
    switch (status) {
      case 'SUCCESS': return 'bg-success-muted text-success';
      case 'RUNNING': return 'bg-accent-muted text-accent';
      case 'FAILED': return 'bg-error-muted text-error';
      case 'SKIPPED': return 'bg-surface-2 text-text-tertiary';
      case 'PENDING':
      default: return 'bg-surface-2 text-text-secondary';
    }
  }

  function arrowColor(index: number): string {
    if (index >= stages.length - 1) return '';
    const current = stages[index];
    if (current.status === 'SUCCESS') return 'text-success';
    if (current.status === 'FAILED') return 'text-error';
    return 'text-text-tertiary';
  }
</script>

<div class="flex items-center gap-2">
  {#each stages as stage, i (stage.stage)}
    {@const Icon = STAGE_ICONS[stage.stage] ?? Circle}
    <div class="flex items-center gap-3 rounded-lg border px-3 py-2 {statusColor(stage.status)}">
      <div class="flex-shrink-0">
        {#if stage.status === 'RUNNING'}
          <Loader2 size={16} class="animate-spin" />
        {:else if stage.status === 'SUCCESS'}
          <CheckCircle2 size={16} />
        {:else if stage.status === 'FAILED'}
          <XCircle size={16} />
        {:else if stage.status === 'SKIPPED'}
          <SkipForward size={16} />
        {:else}
          <Icon size={16} />
        {/if}
      </div>
      <div class="flex flex-col">
        <span class="text-xs font-medium">{STAGE_LABELS[stage.stage] ?? stage.stage}</span>
        <span class="inline-flex items-center rounded-full px-1.5 py-0.5 text-2xs font-medium {statusChipColor(stage.status)}">
          {stage.status}
        </span>
      </div>
    </div>
    {#if i < stages.length - 1}
      <ArrowRight size={16} class="flex-shrink-0 {arrowColor(i)}" />
    {/if}
  {/each}
</div>
