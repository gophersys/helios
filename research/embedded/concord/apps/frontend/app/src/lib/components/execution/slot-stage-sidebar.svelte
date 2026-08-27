<script lang="ts">
  import {
    CheckCircle2,
    Circle,
    Loader2,
    SkipForward,
    XCircle,
  } from 'lucide-svelte';
  import { formatDuration } from '$lib/utils/formatting';
  import { getSlotContext, type SlotStage } from './slot-context.svelte';

  const ctx = getSlotContext();

  function getStageStatusIcon(stage: SlotStage) {
    if (stage.running > 0) return { icon: Loader2, class: 'text-accent animate-spin' };
    if (stage.failed > 0) return { icon: XCircle, class: 'text-error' };
    const totalTests = stage.tests.length;
    const allPassed = stage.passed === totalTests && totalTests > 0;
    if (allPassed) return { icon: CheckCircle2, class: 'text-success' };
    if (stage.passed > 0 && stage.skipped > 0) return { icon: SkipForward, class: 'text-text-tertiary' };
    if (stage.passed > 0) return { icon: CheckCircle2, class: 'text-success' };
    return { icon: Circle, class: 'text-text-tertiary' };
  }
</script>

<div class="space-y-1">
  {#each ctx.stages as stage (stage.name)}
    {@const statusInfo = getStageStatusIcon(stage)}
    <button
      onclick={() => {
        ctx.selectedStage = stage.name;
        if (ctx.analysisMode && ctx.activeManifest) {
          const stageSteps = ctx.activeManifest.steps.filter(s => s.module === stage.name);
          if (stageSteps.length > 0) {
            ctx.selectedRange = {
              start: Math.min(...stageSteps.map(s => s.startedAt)),
              end: Math.max(...stageSteps.map(s => s.finishedAt)),
            };
          }
        }
      }}
      class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors
        {ctx.selectedStage === stage.name
          ? 'bg-accent-muted border border-accent/30 text-text-primary'
          : 'hover:bg-surface-1 text-text-secondary'
        }"
    >
      {#if statusInfo.icon}{@const StatusIcon = statusInfo.icon}<StatusIcon size={16} class="{statusInfo.class}" />{/if}
      <div class="flex-1 min-w-0">
        <div class="text-sm font-medium truncate">{stage.name}</div>
        <div class="text-2xs text-text-tertiary">
          {stage.tests.length} test{stage.tests.length !== 1 ? 's' : ''}
          {#if stage.durationS > 0}
            · {formatDuration(stage.durationS * 1000)}
          {/if}
        </div>
      </div>
      {#if stage.failed > 0}
        <span class="text-2xs font-medium text-error bg-error-muted px-1.5 py-0.5 rounded">
          {stage.failed}
        </span>
      {/if}
    </button>
  {/each}
</div>
