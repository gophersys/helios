<script lang="ts">
  import type { ProductStageConfig, Secret } from '$lib/types/stages';
  import { STAGE_NAMES, STAGE_DESCRIPTIONS, STAGE_BUILD_COUNTS } from '$lib/types/stages';
  import { updateStageConfig } from '$lib/services/stages';
  import type { BoardRevision } from '$lib/types/models';
  import { ChevronDown, Settings, Zap, GitBranch, Key, Loader2 } from 'lucide-svelte';
  import { apiFetch } from '$lib/api';
  import type { ApiResponse } from '$lib/types';

  interface Props {
    stage: number;
    config: ProductStageConfig | undefined;
    productId: string;
    revisions: BoardRevision[];
    secrets: Secret[];
    fwRepoSlug?: string;
    onUpdated: () => void;
  }

  let { stage, config, productId, revisions, secrets, fwRepoSlug = '', onUpdated }: Props = $props();

  let expanded = $state(false);
  let configuring = $state(false);
  let saving = $state(false);

  // Config form
  let formRevisionId = $state('');
  let formBranch = $state('main');
  let formSigningKeyId = $state('');
  let formTriggerTypes = $state<string[]>(['manual']);

  const triggerOptions = [
    { value: 'pr_push', label: 'Pull request', desc: 'Run when a PR targeting the branch is opened or updated' },
    { value: 'pr_merge', label: 'Merge', desc: 'Run when code is merged into the branch' },
    { value: 'auto', label: 'After previous stage', desc: 'Automatically run when the previous stage passes' },
    { value: 'schedule', label: 'Schedule', desc: 'Run on a cron schedule against the branch' },
    { value: 'manual', label: 'Manual', desc: 'Only run when manually triggered' },
  ];

  // Smart defaults per stage
  const defaultTriggers: Record<number, string[]> = {
    1: ['pr_push'],           // Smoke: run on every PR
    2: ['auto'],              // Driver: after Smoke passes
    3: ['auto'],              // Integration: after Driver passes
    4: ['schedule'],          // Regression: scheduled cron
    5: ['pr_merge', 'manual'], // FUOTA: on merge + manual
  };

  function toggleTrigger(value: string) {
    if (formTriggerTypes.includes(value)) {
      formTriggerTypes = formTriggerTypes.filter(t => t !== value);
      if (formTriggerTypes.length === 0) formTriggerTypes = ['manual'];
    } else {
      formTriggerTypes = [...formTriggerTypes.filter(t => t !== 'manual'), value];
    }
  }

  // Human-readable trigger summary
  function triggerSummary(types: string | string[], branch: string | null): string {
    const arr = Array.isArray(types) ? types : [types];
    const labels = arr.map(t => {
      switch (t) {
        case 'pr_push': return branch ? `PR → ${branch}` : 'PR';
        case 'pr_merge': return branch ? `Merge → ${branch}` : 'Merge';
        case 'auto': return 'Auto';
        case 'schedule': return 'Cron';
        case 'manual': return 'Manual';
        default: return t;
      }
    });
    return labels.join(' + ');
  }

  const stageBadgeColors: Record<number, string> = {
    1: 'bg-accent-muted text-accent',
    2: 'bg-info-muted text-info',
    3: 'bg-warning-muted text-warning',
    4: 'bg-accent-muted text-accent',
    5: 'bg-error-muted text-error',
  };

  const stageIcons: Record<number, string> = {
    1: 'SM', 2: 'DR', 3: 'IN', 4: 'RG', 5: 'FU',
  };

  const signingKeys = $derived(secrets.filter(s => s.type === 'signing_key'));

  // Branch loading from firmware repo
  let repoBranches = $state<string[]>([]);
  let loadingBranches = $state(false);

  async function loadBranches() {
    if (!fwRepoSlug) return;
    loadingBranches = true;
    try {
      const res = await apiFetch<ApiResponse<{ branches: string[] }>>(`/v2/products/repos/branches?slug=${encodeURIComponent(fwRepoSlug)}`);
      repoBranches = res.data?.branches ?? [];
      if (!formBranch && repoBranches.includes('main')) formBranch = 'main';
      else if (!formBranch && repoBranches.includes('master')) formBranch = 'master';
      else if (!formBranch && repoBranches.length > 0) formBranch = repoBranches[0];
    } catch { /* non-fatal */ }
    finally { loadingBranches = false; }
  }

  function startConfiguring() {
    if (config) {
      formRevisionId = config.boardRevisionId || '';
      formBranch = config.watchBranch || 'main';
      formSigningKeyId = config.signingKeyId || '';
      formTriggerTypes = (config as any).triggerTypes || defaultTriggers[stage] || ['manual'];
    } else {
      formRevisionId = revisions[0]?.id || '';
      formBranch = 'main';
      formSigningKeyId = signingKeys[0]?.id || '';
      formTriggerTypes = defaultTriggers[stage] || ['manual'];
    }
    configuring = true;
    expanded = true;
    loadBranches();
  }

  let buildResult = $state<{ triggered: boolean; runId?: string; error?: string } | null>(null);

  async function enableStage(buildNow: boolean) {
    if (!formRevisionId) return;
    saving = true;
    buildResult = null;
    try {
      const result = await updateStageConfig(productId, stage, {
        enabled: true,
        boardRevisionId: formRevisionId,
        watchBranch: formBranch || null,
        signingKeyId: formSigningKeyId || null,
        triggerTypes: formTriggerTypes,
        buildNow,
      } as any);
      configuring = false;
      if (result.buildTriggered) {
        buildResult = { triggered: true, runId: result.buildRunId ?? undefined };
      } else if (result.buildError) {
        buildResult = { triggered: false, error: result.buildError ?? undefined };
      }
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
  <div
    role="button"
    tabindex="0"
    class="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface-2 transition-colors text-left cursor-pointer"
    onclick={() => { if (!configuring) expanded = !expanded; }}
    onkeydown={(e) => { if (e.key === 'Enter' && !configuring) expanded = !expanded; }}
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
        {#if config?.enabled && config.assetSources?.includes('EXTERNAL_CI')}
          <span class="badge badge-info">External CI</span>
        {/if}
        {#if config?.enabled && config.assetSources?.includes('MANUAL_UPLOAD')}
          <span class="badge badge-neutral">Manual</span>
        {/if}
        {#if config?.enabled && (!config.assetSources || config.assetSources.includes('BUILD_SERVICE'))}
          <span class="px-1.5 py-0.5 text-2xs rounded bg-accent/10 text-accent">
            {triggerSummary((config as any).triggerTypes || 'manual', config.watchBranch)}
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
          class="btn btn-sm btn-primary"
          onclick={(e) => { e.stopPropagation(); startConfiguring(); }}
        >
          Enable
        </button>
      {/if}
      {#if !configuring}
        <ChevronDown size={14} class="text-text-tertiary transition-transform {expanded ? 'rotate-180' : ''}" />
      {/if}
    </div>
  </div>

  <!-- Enable wizard -->
  {#if configuring}
    <div class="border-t border-accent/30 bg-accent/5 px-4 py-4 space-y-4">
      <h4 class="text-sm font-semibold text-text-primary flex items-center gap-2">
        <Settings size={14} class="text-accent" />
        Configure {STAGE_NAMES[stage]}
      </h4>

      <!-- Revision -->
      <div>
        <label for="stage-rev-{stage}" class="mb-1 block text-2xs font-medium text-text-tertiary">Target Hardware Revision *</label>
        <select
          id="stage-rev-{stage}"
          bind:value={formRevisionId}
          class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-hidden"
        >
          <option value="">— Select revision —</option>
          {#each revisions as rev}
            <option value={rev.id}>{rev.version.toUpperCase()} ({rev.ckBoardsName})</option>
          {/each}
        </select>
      </div>

      <!-- Trigger — GitHub Actions style -->
      <div>
        <span class="mb-2 block text-2xs font-medium text-text-tertiary">on:</span>
        <div class="space-y-1">
          {#each triggerOptions as opt}
            <label class="flex items-start gap-2 rounded-lg border px-3 py-2 cursor-pointer transition-colors {formTriggerTypes.includes(opt.value) ? 'border-accent bg-accent/5' : 'border-border-subtle bg-surface-0 hover:bg-surface-1'}">
              <input type="checkbox" checked={formTriggerTypes.includes(opt.value)} onchange={() => toggleTrigger(opt.value)} class="mt-0.5 accent-accent" />
              <div>
                <span class="text-sm font-medium text-text-primary">{opt.label}</span>
                <p class="text-2xs text-text-tertiary">{opt.desc}</p>
              </div>
            </label>
          {/each}
        </div>
      </div>

      <!-- Branch filter (shown when trigger type needs one) -->
      {#if formTriggerTypes.some((t: string) => ["pr_push","pr_merge","schedule"].includes(t))}
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label for="stage-branch-{stage}" class="mb-1 block text-2xs font-medium text-text-tertiary">
            {formTriggerTypes.includes('pr_push') ? 'PRs targeting branch' : formTriggerTypes.includes('pr_merge') ? 'Merge into branch' : 'Build from branch'}
          </label>
          {#if loadingBranches}
            <div class="flex items-center gap-2 py-2 text-2xs text-text-tertiary">
              <Loader2 size={12} class="animate-spin" /> Loading branches...
            </div>
          {:else if repoBranches.length > 0}
            <select
              id="stage-branch-{stage}"
              bind:value={formBranch}
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-hidden"
            >
              {#each repoBranches as branch}
                <option value={branch}>{branch}</option>
              {/each}
            </select>
          {:else}
            <input
              id="stage-branch-{stage}"
              type="text"
              bind:value={formBranch}
              placeholder="main"
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden"
            />
            {#if fwRepoSlug}
              <p class="mt-1 text-2xs text-text-tertiary">Could not load branches from {fwRepoSlug}</p>
            {/if}
          {/if}
        </div>
        <div>
          <label for="stage-key-{stage}" class="mb-1 block text-2xs font-medium text-text-tertiary">Signing Key</label>
          <select
            id="stage-key-{stage}"
            bind:value={formSigningKeyId}
            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-hidden"
          >
            <option value="">— No signing key —</option>
            {#each signingKeys as key}
              <option value={key.id}>{key.name}</option>
            {/each}
          </select>
          {#if signingKeys.length === 0}
            <p class="mt-1 text-2xs text-text-tertiary">No signing keys configured. Add them in Settings → Secrets.</p>
          {/if}
        </div>
      </div>

      {/if}

      <!-- Info -->
      <div class="rounded bg-surface-0 border border-border-subtle px-3 py-2 text-2xs text-text-tertiary flex items-center gap-2">
        <Zap size={12} class="text-accent shrink-0" />
        This stage creates {STAGE_BUILD_COUNTS[stage] || '?'} firmware builds. If open PRs exist on the watched branch, builds start automatically.
      </div>

      <!-- Build result feedback -->
      {#if buildResult}
        {#if buildResult.triggered}
          <div class="rounded bg-success-muted border border-success/30 px-3 py-2 text-sm text-success">
            Build triggered! {buildResult.runId ? `Run ID: ${buildResult.runId}` : ''}
          </div>
        {:else if buildResult.error}
          <div class="rounded bg-error-muted border border-error/30 px-3 py-2 text-sm text-error">
            {buildResult.error}
          </div>
        {/if}
      {/if}

      <!-- Actions -->
      <div class="flex gap-2">
        <button
          onclick={() => enableStage(true)}
          disabled={saving || !formRevisionId}
          class="btn btn-sm btn-primary"
        >
          {saving ? 'Enabling...' : 'Enable'}
        </button>
        <button
          onclick={() => { configuring = false; expanded = false; }}
          class="btn btn-sm"
        >
          Cancel
        </button>
      </div>
    </div>
  {/if}

  <!-- Enabled summary -->
  {#if expanded && !configuring && config?.enabled}
    <div class="border-t border-border px-4 py-3 space-y-3">
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        <div>
          <span class="block text-2xs text-text-tertiary">Revision</span>
          <span class="font-mono text-text-primary">{config.boardRevision?.ckBoardsName || '—'}</span>
        </div>
        <div>
          <span class="block text-2xs text-text-tertiary">Asset Sources</span>
          <span class="flex flex-wrap gap-1">
            {#each config.assetSources || ['BUILD_SERVICE'] as src}
              {#if src === 'EXTERNAL_CI'}
                <span class="badge badge-info">External CI</span>
              {:else if src === 'MANUAL_UPLOAD'}
                <span class="badge badge-neutral">Manual</span>
              {:else}
                <span class="badge badge-accent">Concord Builds</span>
              {/if}
            {/each}
          </span>
        </div>
        {#if (!config.assetSources || config.assetSources.includes('BUILD_SERVICE'))}
          <div>
            <span class="block text-2xs text-text-tertiary">Trigger</span>
            <span class="text-text-primary">{triggerSummary((config as any).triggerTypes || 'manual', config.watchBranch)}</span>
          </div>
          {#if config.watchBranch}
          <div>
            <span class="block text-2xs text-text-tertiary">Branch</span>
            <span class="font-mono text-text-primary flex items-center gap-1">
              <GitBranch size={12} /> {config.watchBranch}
            </span>
          </div>
          {/if}
        {/if}
        <div>
          <span class="block text-2xs text-text-tertiary">Signing Key</span>
          <span class="text-text-primary flex items-center gap-1">
            {#if config.signingKey}
              <Key size={12} /> {config.signingKey.name}
            {:else}
              —
            {/if}
          </span>
        </div>
      </div>

      <div class="flex items-center gap-2 border-t border-border-subtle pt-3">
        <button onclick={startConfiguring} class="text-xs text-text-secondary hover:text-text-primary">Edit</button>
        <button onclick={disable} class="text-xs text-error hover:text-error">Disable</button>
      </div>
    </div>
  {/if}
</div>
