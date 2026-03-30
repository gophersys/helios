<script lang="ts">
  import {
    CheckCircle2,
    Circle,
    Download,
    Loader2,
    Package,
    SkipForward,
    XCircle,
  } from 'lucide-svelte';
  import { formatDuration } from '$lib/utils/formatting';
  import { getRunContext, type Stage } from './run-context.svelte';

  const ctx = getRunContext();

  function getStageStatusIcon(stage: Stage) {
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
        // In analysis mode, select the entire stage's time range
        if (ctx.analysisMode && ctx.telemetryManifest) {
          const stageSteps = ctx.telemetryManifest.steps.filter(s => s.module === stage.name);
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
      {@const StatusIcon = statusInfo.icon}
      <StatusIcon size={16} class="{statusInfo.class}" />
      <div class="flex-1 min-w-0">
        <div class="text-sm font-medium truncate flex items-center gap-1.5">
          {#if stage.type === 'build'}
            <Package size={12} class="text-text-tertiary" />
          {/if}
          {stage.name}
        </div>
        <div class="text-2xs text-text-tertiary">
          {#if stage.type === 'build'}
            {stage.builds.length} build{stage.builds.length !== 1 ? 's' : ''}
          {:else}
            {stage.tests.length} test{stage.tests.length !== 1 ? 's' : ''}
          {/if}
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

  <!-- Artifacts section in sidebar -->
  {#if ctx.artifacts.length > 0}
    <div class="mt-4 pt-4 border-t border-border">
      <div class="text-2xs font-medium text-text-tertiary uppercase tracking-wider mb-2 px-3">
        Artifacts
      </div>
      {#each ctx.artifacts.slice(0, 5) as artifact (artifact.objectName)}
        <a
          href="/v2/sessions/{ctx.runId}/artifacts/{artifact.name}"
          target="_blank"
          class="flex items-center gap-2 px-3 py-1.5 text-xs text-text-secondary hover:text-text-primary hover:bg-surface-1 rounded transition-colors"
        >
          <Download size={12} class="text-text-tertiary" />
          <span class="truncate">{artifact.name}</span>
        </a>
      {/each}
      {#if ctx.artifacts.length > 5}
        <div class="px-3 py-1 text-2xs text-text-tertiary">
          +{ctx.artifacts.length - 5} more
        </div>
      {/if}
    </div>
  {/if}
</div>
