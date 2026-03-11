<script lang="ts">
  import { X, Clock, CheckCircle, XCircle, AlertTriangle, FileText, Zap, Radio } from 'lucide-svelte';
  import type { ValidationStep, TestResult } from './types';
  import { NODE_TYPE_ICONS } from './types';

  let {
    step,
    onclose = () => {},
  }: {
    step: ValidationStep | null;
    onclose?: () => void;
  } = $props();

  let activeTab = $state<'tests' | 'logs' | 'power' | 'fuota'>('tests');

  function formatDuration(ms: number | undefined): string {
    if (!ms) return '-';
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    const mins = Math.floor(ms / 60000);
    const secs = Math.floor((ms % 60000) / 1000);
    return `${mins}m ${secs}s`;
  }

  const statusColors: Record<string, string> = {
    PASSED: 'text-success',
    FAILED: 'text-error',
    SKIPPED: 'text-warning',
    ERROR: 'text-error',
    RUNNING: 'text-accent',
    PENDING: 'text-text-tertiary',
    BLOCKED: 'text-text-tertiary',
  };
</script>

{#if step}
  <div class="flex h-full flex-col bg-surface-0">
    <!-- Header -->
    <div class="flex items-center justify-between border-b border-surface-2 px-4 py-3">
      <div class="flex items-center gap-2">
        <span class="text-lg">{NODE_TYPE_ICONS[step.nodeType]}</span>
        <span class="font-medium">{step.nodeLabel}</span>
        <span class="rounded bg-surface-2 px-2 py-0.5 text-xs {statusColors[step.status]}">
          {step.status}
        </span>
      </div>
      <button
        type="button"
        class="rounded p-1 hover:bg-surface-1"
        onclick={onclose}
      >
        <X class="h-4 w-4" />
      </button>
    </div>

    <!-- Summary bar -->
    <div class="flex gap-4 border-b border-surface-2 bg-surface-1 px-4 py-2 text-sm">
      <div class="flex items-center gap-1">
        <Clock class="h-4 w-4 text-text-tertiary" />
        <span>{formatDuration(step.durationMs)}</span>
      </div>
      {#if step.testsTotal !== undefined}
        <div class="flex items-center gap-1">
          <CheckCircle class="h-4 w-4 text-success" />
          <span>{step.testsPassed ?? 0}/{step.testsTotal}</span>
        </div>
        {#if step.testsFailed}
          <div class="flex items-center gap-1">
            <XCircle class="h-4 w-4 text-error" />
            <span>{step.testsFailed}</span>
          </div>
        {/if}
      {/if}
      {#if step.fuotaPercent !== undefined}
        <div class="flex items-center gap-1">
          <Radio class="h-4 w-4 text-accent" />
          <span>{step.fuotaPercent}%</span>
        </div>
      {/if}
    </div>

    <!-- Tabs -->
    <div class="flex border-b border-surface-2">
      <button
        type="button"
        class="px-4 py-2 text-sm {activeTab === 'tests'
          ? 'border-b-2 border-accent text-accent'
          : 'text-text-secondary hover:text-text-primary'}"
        onclick={() => (activeTab = 'tests')}
      >
        Tests
      </button>
      <button
        type="button"
        class="px-4 py-2 text-sm {activeTab === 'logs'
          ? 'border-b-2 border-accent text-accent'
          : 'text-text-secondary hover:text-text-primary'}"
        onclick={() => (activeTab = 'logs')}
      >
        Logs
      </button>
      <button
        type="button"
        class="px-4 py-2 text-sm {activeTab === 'power'
          ? 'border-b-2 border-accent text-accent'
          : 'text-text-secondary hover:text-text-primary'}"
        onclick={() => (activeTab = 'power')}
      >
        Power
      </button>
      {#if step.nodeType === 'FUOTA'}
        <button
          type="button"
          class="px-4 py-2 text-sm {activeTab === 'fuota'
            ? 'border-b-2 border-accent text-accent'
            : 'text-text-secondary hover:text-text-primary'}"
          onclick={() => (activeTab = 'fuota')}
        >
          FUOTA
        </button>
      {/if}
    </div>

    <!-- Tab content -->
    <div class="flex-1 overflow-auto p-4">
      {#if activeTab === 'tests'}
        <!-- Test Results -->
        {#if step.testResults && step.testResults.length > 0}
          <div class="space-y-1">
            {#each step.testResults as test}
              <div
                class="flex items-center justify-between rounded px-2 py-1.5 hover:bg-surface-1"
              >
                <div class="flex items-center gap-2">
                  {#if test.status === 'PASSED'}
                    <CheckCircle class="h-4 w-4 text-success" />
                  {:else if test.status === 'FAILED' || test.status === 'ERROR'}
                    <XCircle class="h-4 w-4 text-error" />
                  {:else}
                    <AlertTriangle class="h-4 w-4 text-warning" />
                  {/if}
                  <span class="font-mono text-sm">{test.name}</span>
                </div>
                <span class="text-xs text-text-tertiary">
                  {formatDuration(test.durationMs)}
                </span>
              </div>
              {#if test.message}
                <div class="ml-6 rounded bg-surface-1 p-2 text-xs text-text-secondary">
                  {test.message}
                </div>
              {/if}
            {/each}
          </div>
        {:else}
          <div class="text-center text-sm text-text-tertiary">No test results</div>
        {/if}
      {:else if activeTab === 'logs'}
        <!-- Log viewer -->
        {#if step.logs}
          <pre
            class="h-full overflow-auto rounded bg-surface-1 p-3 font-mono text-xs leading-relaxed">{step.logs}</pre>
        {:else}
          <div class="text-center text-sm text-text-tertiary">No logs available</div>
        {/if}
      {:else if activeTab === 'power'}
        <!-- Power metrics -->
        {#if step.metrics}
          <div class="space-y-4">
            {#if step.metrics.ch0}
              <div>
                <div class="mb-1 text-sm font-medium">Channel 0 (VBAT)</div>
                <div class="flex gap-4 text-sm">
                  <div>
                    <span class="text-text-tertiary">Avg:</span>
                    <span class="font-mono">{step.metrics.ch0.avg.toFixed(1)}mA</span>
                  </div>
                  <div>
                    <span class="text-text-tertiary">Min:</span>
                    <span class="font-mono">{step.metrics.ch0.min.toFixed(1)}mA</span>
                  </div>
                  <div>
                    <span class="text-text-tertiary">Max:</span>
                    <span class="font-mono">{step.metrics.ch0.max.toFixed(1)}mA</span>
                  </div>
                </div>
                <!-- Simple bar visualization -->
                <div class="mt-2 h-4 w-full overflow-hidden rounded bg-surface-2">
                  <div
                    class="h-full bg-accent"
                    style="width: {Math.min(100, (step.metrics.ch0.avg / 50) * 100)}%"
                  ></div>
                </div>
              </div>
            {/if}
            {#if step.metrics.ch1}
              <div>
                <div class="mb-1 text-sm font-medium">Channel 1 (Charger)</div>
                <div class="flex gap-4 text-sm">
                  <div>
                    <span class="text-text-tertiary">Avg:</span>
                    <span class="font-mono">{step.metrics.ch1.avg.toFixed(1)}mA</span>
                  </div>
                  <div>
                    <span class="text-text-tertiary">Min:</span>
                    <span class="font-mono">{step.metrics.ch1.min.toFixed(1)}mA</span>
                  </div>
                  <div>
                    <span class="text-text-tertiary">Max:</span>
                    <span class="font-mono">{step.metrics.ch1.max.toFixed(1)}mA</span>
                  </div>
                </div>
                <div class="mt-2 h-4 w-full overflow-hidden rounded bg-surface-2">
                  <div
                    class="h-full bg-success"
                    style="width: {Math.min(100, (step.metrics.ch1.avg / 50) * 100)}%"
                  ></div>
                </div>
              </div>
            {/if}
          </div>
        {:else}
          <div class="text-center text-sm text-text-tertiary">No power data</div>
        {/if}
      {:else if activeTab === 'fuota'}
        <!-- FUOTA progress -->
        {#if step.fuotaTargets}
          <div class="space-y-4">
            <div>
              <div class="mb-1 text-sm font-medium">Targets</div>
              <div class="font-mono text-sm">{step.fuotaTargets}</div>
            </div>
            {#if step.fuotaPlanId}
              <div>
                <div class="mb-1 text-sm font-medium">Plan ID</div>
                <div class="font-mono text-sm">{step.fuotaPlanId}</div>
              </div>
            {/if}
            {#if step.fuotaPages !== undefined && step.fuotaPagesTotal}
              <div>
                <div class="mb-1 text-sm font-medium">Pages Delivered</div>
                <div class="mb-2 font-mono text-sm">
                  {step.fuotaPages} / {step.fuotaPagesTotal}
                </div>
                <div class="h-4 w-full overflow-hidden rounded bg-surface-2">
                  <div
                    class="h-full bg-accent transition-all"
                    style="width: {step.fuotaPercent ?? 0}%"
                  ></div>
                </div>
                <div class="mt-1 text-center text-sm">{step.fuotaPercent ?? 0}%</div>
              </div>
            {/if}
          </div>
        {:else}
          <div class="text-center text-sm text-text-tertiary">No FUOTA data</div>
        {/if}
      {/if}
    </div>

    <!-- Artifacts -->
    {#if step.artifacts && step.artifacts.length > 0}
      <div class="border-t border-surface-2 px-4 py-3">
        <div class="mb-2 text-sm font-medium">Artifacts</div>
        <div class="flex flex-wrap gap-2">
          {#each step.artifacts as artifact}
            <a
              href={artifact.url}
              target="_blank"
              rel="noopener"
              class="flex items-center gap-1 rounded bg-surface-1 px-2 py-1 text-xs hover:bg-surface-2"
            >
              <FileText class="h-3 w-3" />
              {artifact.name}
            </a>
          {/each}
        </div>
      </div>
    {/if}
  </div>
{/if}
