<script lang="ts">
  import type { ProductStageConfig } from '$lib/types/stages';
  import { STAGE_NAMES, STAGE_DESCRIPTIONS, STAGE_BUILD_COUNTS } from '$lib/types/stages';
  import { updateStageConfig } from '$lib/services/stages';
  import type { BoardRevision } from '$lib/types/models';
  import { ChevronDown, Settings, Zap, Clock, GitBranch, Shield } from 'lucide-svelte';

  interface Props {
    stage: number;
    config: ProductStageConfig | undefined;
    productId: string;
    revisions: BoardRevision[];
    onUpdated: () => void;
  }

  let { stage, config, productId, revisions, onUpdated }: Props = $props();

  let expanded = $state(false);
  let configuring = $state(false);
  let saving = $state(false);

  // Config form state
  let formRevisionId = $state('');
  let formTestDir = $state('');
  let formTestMarker = $state('');
  let formTestTimeout = $state(900);
  let formPriority = $state(50);
  let formBlocksMerge = $state(false);
  let formAutoProgress = $state(false);
  let formRequiresBench = $state(true);
  let formMaxDuration = $state(3600);

  const stageBadgeColors: Record<number, string> = {
    1: 'bg-blue-500/10 text-blue-400',
    2: 'bg-cyan-500/10 text-cyan-400',
    3: 'bg-amber-500/10 text-amber-400',
    4: 'bg-purple-500/10 text-purple-400',
    5: 'bg-red-500/10 text-red-400',
  };

  const stageIcons: Record<number, string> = {
    1: 'SM', 2: 'SI', 3: 'IN', 4: 'NY', 5: 'FU',
  };

  function startConfiguring() {
    if (config) {
      formRevisionId = config.boardRevisionId || '';
      formTestDir = config.testDirectory || '';
      formTestMarker = config.testMarker || '';
      formTestTimeout = config.testTimeout;
      formPriority = config.priority;
      formBlocksMerge = config.blocksMerge;
      formAutoProgress = config.autoProgress;
      formRequiresBench = config.requiresBench;
      formMaxDuration = config.maxDurationSec;
    } else {
      // Defaults for this stage
      const defaults: Record<number, { dir: string; marker: string; timeout: number; priority: number; bench: boolean; merge: boolean }> = {
        1: { dir: 'tests/smoke/', marker: '-m smoke', timeout: 120, priority: 10, bench: false, merge: true },
        2: { dir: 'tests/silicon/', marker: '-m silicon', timeout: 300, priority: 20, bench: true, merge: true },
        3: { dir: 'tests/integration/', marker: '-m integration', timeout: 600, priority: 30, bench: true, merge: true },
        4: { dir: 'tests/nightly/', marker: '-m nightly', timeout: 1800, priority: 40, bench: true, merge: false },
        5: { dir: 'tests/fuota/', marker: '-m fuota', timeout: 600, priority: 100, bench: true, merge: true },
      };
      const d = defaults[stage] || defaults[1];
      formTestDir = d.dir;
      formTestMarker = d.marker;
      formTestTimeout = d.timeout;
      formPriority = d.priority;
      formRequiresBench = d.bench;
      formBlocksMerge = d.merge;
      formRevisionId = revisions[0]?.id || '';
    }
    configuring = true;
    expanded = true;
  }

  async function saveAndEnable() {
    saving = true;
    try {
      await updateStageConfig(productId, stage, {
        enabled: true,
        boardRevisionId: formRevisionId || null,
        testDirectory: formTestDir || null,
        testMarker: formTestMarker || null,
        testTimeout: formTestTimeout,
        priority: formPriority,
        blocksMerge: formBlocksMerge,
        autoProgress: formAutoProgress,
        requiresBench: formRequiresBench,
        maxDurationSec: formMaxDuration,
      });
      configuring = false;
      onUpdated();
    } catch (err) {
      console.error('Failed to save stage config:', err);
    } finally {
      saving = false;
    }
  }

  async function disable() {
    try {
      await updateStageConfig(productId, stage, { enabled: false });
      onUpdated();
    } catch (err) {
      console.error('Failed to disable stage:', err);
    }
  }
</script>

<div class="rounded-lg border border-border bg-surface-1 overflow-hidden">
  <!-- Header -->
  <button
    class="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface-2 transition-colors text-left"
    onclick={() => { if (!configuring) expanded = !expanded; }}
  >
    <span class="flex items-center justify-center w-8 h-8 rounded {stageBadgeColors[stage] || 'bg-surface-2 text-text-secondary'} text-xs font-bold">
      {stageIcons[stage] || stage}
    </span>
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2">
        <span class="font-medium text-text-primary">Stage {stage}</span>
        <span class="px-1.5 py-0.5 text-2xs rounded font-medium {stageBadgeColors[stage]}">
          {STAGE_NAMES[stage]}
        </span>
        {#if config?.enabled && config?.boardRevision}
          <span class="px-1.5 py-0.5 text-2xs rounded bg-surface-2 font-mono text-text-tertiary">
            {config.boardRevision.ckBoardsName}
          </span>
        {/if}
      </div>
      <p class="text-2xs text-text-tertiary truncate">{STAGE_DESCRIPTIONS[stage]}</p>
    </div>

    <div class="flex items-center gap-2">
      {#if config?.enabled}
        <span class="px-2 py-1 text-xs rounded font-medium bg-success-muted text-success">Enabled</span>
      {:else}
        <button
          class="px-2 py-1 text-xs rounded font-medium bg-accent text-white hover:bg-accent-hover"
          onclick={(e) => { e.stopPropagation(); startConfiguring(); }}
        >
          Enable
        </button>
      {/if}
      {#if !configuring}
        <ChevronDown size={14} class="text-text-tertiary transition-transform {expanded ? 'rotate-180' : ''}" />
      {/if}
    </div>
  </button>

  <!-- Configuring wizard (when enabling) -->
  {#if configuring}
    <div class="border-t border-accent/30 bg-accent/5 px-4 py-4 space-y-4">
      <h4 class="text-sm font-semibold text-text-primary flex items-center gap-2">
        <Settings size={14} class="text-accent" />
        Configure {STAGE_NAMES[stage]} Stage
      </h4>

      <!-- Target revision -->
      <div>
        <label for="stage-rev-{stage}" class="mb-1 block text-2xs font-medium text-text-tertiary">Target Hardware Revision</label>
        <select
          id="stage-rev-{stage}"
          bind:value={formRevisionId}
          class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
        >
          <option value="">— Select revision —</option>
          {#each revisions as rev}
            <option value={rev.id}>{rev.version.toUpperCase()} ({rev.ckBoardsName})</option>
          {/each}
        </select>
      </div>

      <!-- Test config -->
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label for="stage-testdir-{stage}" class="mb-1 block text-2xs font-medium text-text-tertiary">Test Directory</label>
          <input id="stage-testdir-{stage}" type="text" bind:value={formTestDir} placeholder="tests/smoke/"
            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none" />
        </div>
        <div>
          <label for="stage-marker-{stage}" class="mb-1 block text-2xs font-medium text-text-tertiary">Pytest Marker</label>
          <input id="stage-marker-{stage}" type="text" bind:value={formTestMarker} placeholder="-m smoke"
            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none" />
        </div>
      </div>

      <!-- Timing -->
      <div class="grid gap-3 sm:grid-cols-3">
        <div>
          <label for="stage-timeout-{stage}" class="mb-1 block text-2xs font-medium text-text-tertiary">Test Timeout (s)</label>
          <input id="stage-timeout-{stage}" type="number" bind:value={formTestTimeout} min="30"
            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none" />
        </div>
        <div>
          <label for="stage-duration-{stage}" class="mb-1 block text-2xs font-medium text-text-tertiary">Max Duration (s)</label>
          <input id="stage-duration-{stage}" type="number" bind:value={formMaxDuration} min="60"
            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none" />
        </div>
        <div>
          <label for="stage-priority-{stage}" class="mb-1 block text-2xs font-medium text-text-tertiary">Priority</label>
          <input id="stage-priority-{stage}" type="number" bind:value={formPriority} min="0" max="200"
            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none" />
        </div>
      </div>

      <!-- Toggles -->
      <div class="flex flex-wrap gap-4">
        <label class="inline-flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
          <input type="checkbox" bind:checked={formBlocksMerge} class="rounded border-border accent-accent" />
          Blocks merge
        </label>
        <label class="inline-flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
          <input type="checkbox" bind:checked={formAutoProgress} class="rounded border-border accent-accent" />
          Auto-progress to next stage
        </label>
        <label class="inline-flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
          <input type="checkbox" bind:checked={formRequiresBench} class="rounded border-border accent-accent" />
          Requires hardware bench
        </label>
      </div>

      <!-- Info -->
      <div class="rounded bg-surface-0 border border-border-subtle px-3 py-2 text-2xs text-text-tertiary flex items-center gap-2">
        <Zap size={12} class="text-accent" />
        This stage triggers {STAGE_BUILD_COUNTS[stage] || '?'} firmware builds automatically when run.
      </div>

      <!-- Actions -->
      <div class="flex gap-2">
        <button
          onclick={saveAndEnable}
          disabled={saving}
          class="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Enable Stage'}
        </button>
        <button
          onclick={() => { configuring = false; expanded = false; }}
          class="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2"
        >
          Cancel
        </button>
      </div>
    </div>
  {/if}

  <!-- Enabled stage summary (when expanded, not configuring) -->
  {#if expanded && !configuring && config?.enabled}
    <div class="border-t border-border px-4 py-3 space-y-3">
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        <div>
          <span class="block text-2xs text-text-tertiary">Revision</span>
          <span class="font-mono text-text-primary">{config.boardRevision?.ckBoardsName || '—'}</span>
        </div>
        <div>
          <span class="block text-2xs text-text-tertiary">Test Dir</span>
          <span class="font-mono text-text-primary">{config.testDirectory || '—'}</span>
        </div>
        <div>
          <span class="block text-2xs text-text-tertiary">Timeout</span>
          <span class="text-text-primary">{config.testTimeout}s</span>
        </div>
        <div>
          <span class="block text-2xs text-text-tertiary">Builds</span>
          <span class="text-text-primary">{STAGE_BUILD_COUNTS[stage]} per run</span>
        </div>
      </div>

      <div class="flex flex-wrap gap-2">
        {#if config.blocksMerge}
          <span class="inline-flex items-center gap-1 rounded bg-warning-muted px-1.5 py-0.5 text-2xs text-warning">
            <Shield size={10} /> Blocks merge
          </span>
        {/if}
        {#if config.autoProgress}
          <span class="inline-flex items-center gap-1 rounded bg-accent/10 px-1.5 py-0.5 text-2xs text-accent">
            <GitBranch size={10} /> Auto-progress
          </span>
        {/if}
        {#if config.requiresBench}
          <span class="inline-flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-tertiary">
            <Zap size={10} /> Needs hardware
          </span>
        {/if}
      </div>

      <div class="flex items-center gap-2 border-t border-border-subtle pt-3">
        <button
          onclick={startConfiguring}
          class="text-xs text-text-secondary hover:text-text-primary"
        >
          Edit Config
        </button>
        <button
          onclick={disable}
          class="text-xs text-error hover:text-error"
        >
          Disable
        </button>
      </div>
    </div>
  {/if}
</div>
