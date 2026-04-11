<script lang="ts">
  import {
    CheckCircle2,
    ChevronDown,
    ChevronRight,
    Circle,
    Clock,
    FileText,
    Layers,
    Loader2,
    SkipForward,
    XCircle,
  } from 'lucide-svelte';
  import { formatDuration } from '$lib/utils/formatting';
  import { parseAnsi } from '$lib/utils/ansi';
  import { highlightTraceback } from '$lib/utils/python-highlight';
  import MeasurementsDisplay from '$lib/components/ui/measurements-display.svelte';
  import { getSlotContext } from './slot-context.svelte';

  const ctx = getSlotContext();

  function autoScroll(node: HTMLElement, _trigger: unknown) {
    requestAnimationFrame(() => node.scrollTop = node.scrollHeight);
    return {
      update() {
        requestAnimationFrame(() => node.scrollTop = node.scrollHeight);
      }
    };
  }
</script>

{#if ctx.selectedStageData}
  <div class="rounded-lg border border-border bg-surface-0 overflow-hidden">
    <!-- Stage header -->
    <div class="flex items-center gap-3 px-4 py-3 border-b border-border bg-surface-1">
      <Layers size={16} class="text-text-tertiary" />
      <span class="font-medium text-text-primary">{ctx.selectedStageData.name}</span>
      <span class="text-xs text-text-tertiary">
        {ctx.selectedStageData.tests.length} test{ctx.selectedStageData.tests.length !== 1 ? 's' : ''}
      </span>
      {#if ctx.selectedStageData.durationS > 0}
        <span class="ml-auto text-xs text-text-tertiary flex items-center gap-1">
          <Clock size={12} />
          {formatDuration(ctx.selectedStageData.durationS * 1000)}
        </span>
      {/if}
    </div>

    <!-- Test list -->
    <div class="divide-y divide-border">
      {#each ctx.selectedStageData.tests as test (test.name)}
        <div class="group">
          <button
            data-test-name={test.name}
            data-test-module={test.module}
            onclick={() => ctx.toggleTestExpanded(test.name, test.module)}
            class="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface-1 transition-colors
              {test.status === 'failed' ? 'bg-error-muted/30' : ''}
              {test.status === 'running' ? 'bg-accent-muted/30' : ''}
              {test.status === 'skipped' ? 'opacity-60' : ''}
            "
          >
            <div class="shrink-0 text-text-tertiary">
              {#if test.expanded}
                <ChevronDown size={14} />
              {:else}
                <ChevronRight size={14} />
              {/if}
            </div>

            <div class="shrink-0">
              {#if test.status === 'queued'}
                <Circle size={14} class="text-text-tertiary" />
              {:else if test.status === 'running'}
                <Loader2 size={14} class="text-accent animate-spin" />
              {:else if test.status === 'passed'}
                <CheckCircle2 size={14} class="text-success" />
              {:else if test.status === 'failed'}
                <XCircle size={14} class="text-error" />
              {:else if test.status === 'skipped'}
                <SkipForward size={14} class="text-text-tertiary" />
              {/if}
            </div>

            <span class="flex-1 text-sm font-mono text-text-primary truncate">
              {test.name}
            </span>

            {#if test.status === 'running' && test.startedAtMs}
              <span class="text-xs tabular-nums text-accent">
                {formatDuration(ctx.nowMs - test.startedAtMs)}
              </span>
            {:else if test.durationS !== null}
              <span class="text-xs tabular-nums text-text-tertiary">
                {formatDuration((test.durationS ?? 0) * 1000)}
              </span>
            {/if}
          </button>

          {#if test.expanded}
            <div class="border-t border-border bg-[#0d1117]">
              <!-- Error traceback -->
              {#if test.errorMessage}
                {@const highlighted = highlightTraceback(test.errorMessage)}
                {@const fileLine = highlighted.find(l => l.isFilePath)}
                <div class="border-b border-error/20">
                  {#if fileLine}
                    <div class="px-4 py-1.5 bg-[#161b22] border-b border-border/30 flex items-center gap-2">
                      <FileText size={12} class="text-text-tertiary" />
                      <span class="text-xs font-mono text-accent">{fileLine.filePath}</span>
                      {#if fileLine.fileLineNum}
                        <span class="text-2xs font-mono text-orange-300">line {fileLine.fileLineNum}</span>
                      {/if}
                    </div>
                  {/if}
                  <div class="px-2 py-2 bg-[#0d1117] max-h-80 overflow-auto font-mono text-xs leading-relaxed">
                    {#each highlighted as line}
                      <div class="flex {line.isMarker ? 'bg-warning/10 border-l-2 border-warning' : line.isError ? 'bg-error/5 border-l-2 border-error' : line.isFilePath ? 'hidden' : ''}">
                        <span class="w-8 text-right pr-2 select-none shrink-0" style="color: #4b5563">{line.lineNum || ''}</span>
                        <span class="flex-1 whitespace-pre-wrap">{#each line.segments as seg}<span style={seg.cls}>{seg.text}</span>{/each}</span>
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}

              <!-- Sub-steps (from report.step()) -->
              {#if test.steps.length > 0}
                <div class="border-b border-border/30">
                  <div class="px-4 py-1 text-2xs font-medium text-text-tertiary bg-[#161b22]">Steps</div>
                  <div class="divide-y divide-border/20">
                    {#each test.steps as step (step.index)}
                      <div class="flex items-center gap-2 px-4 py-1.5 text-xs">
                        <div class="shrink-0">
                          {#if step.status === 'passed'}
                            <CheckCircle2 size={12} class="text-success" />
                          {:else if step.status === 'failed'}
                            <XCircle size={12} class="text-error" />
                          {:else if step.status === 'running'}
                            <Loader2 size={12} class="text-accent animate-spin" />
                          {:else}
                            <Circle size={12} class="text-text-tertiary" />
                          {/if}
                        </div>
                        <span class="flex-1 font-mono text-[#c9d1d9] truncate">{step.name}</span>
                        {#if step.durationMs !== null}
                          <span class="text-2xs tabular-nums text-text-tertiary">{formatDuration(step.durationMs)}</span>
                        {/if}
                      </div>
                      {#if step.measurements && Object.keys(step.measurements).length > 0}
                        <div class="px-8 py-1">
                          <MeasurementsDisplay measurements={step.measurements} />
                        </div>
                      {/if}
                      {#if step.errorMessage}
                        <div class="px-8 py-1">
                          <p class="text-2xs text-error">{step.errorMessage}</p>
                        </div>
                      {/if}
                    {/each}
                  </div>
                </div>
              {/if}

              <!-- Measurements -->
              {#if test.measurements && Object.keys(test.measurements).length > 0}
                <div class="px-4 py-2 border-b border-border/30">
                  <MeasurementsDisplay measurements={test.measurements} />
                </div>
              {/if}

              <!-- Log output -->
              {#if test.logOutput}
                <div class="border-t border-border/20">
                  <div class="px-4 py-1 text-2xs font-medium text-text-tertiary bg-[#161b22]">Output</div>
                  <div class="px-4 py-2 max-h-96 overflow-auto bg-[#0d1117] font-mono text-xs leading-relaxed" use:autoScroll={test.logOutput}>
                    {#each test.logOutput.split('\n') as line}
                      <div class="whitespace-pre-wrap">{#each parseAnsi(line) as seg}<span class="{seg.classes || 'text-[#c9d1d9]'}">{seg.text}</span>{/each}</div>
                    {/each}
                  </div>
                </div>
              {:else if test.status === 'skipped'}
                <div class="px-4 py-3 text-xs text-text-tertiary">Test was skipped.</div>
              {:else if test.status === 'running'}
                <div class="px-4 py-3 flex items-center gap-2 text-xs text-text-tertiary">
                  <Loader2 size={12} class="animate-spin" />
                  Waiting for output...
                </div>
              {:else if test.status === 'passed' || test.status === 'failed'}
                <div class="px-4 py-3 text-xs text-text-tertiary italic">No log output captured.</div>
              {:else}
                <div class="px-4 py-3 text-xs text-text-tertiary italic">Queued</div>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  </div>
{:else}
  <div class="flex items-center justify-center h-64 text-text-tertiary text-sm">
    Select a stage to view test details
  </div>
{/if}
