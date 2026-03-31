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
    } else {
      formRevisionId = revisions[0]?.id || '';
      formBranch = 'main';
      formSigningKeyId = signingKeys[0]?.id || '';
    }
    configuring = true;
    expanded = true;
    loadBranches();
  }

  async function saveAndEnable() {
    if (!formRevisionId) return;
    saving = true;
    try {
      await updateStageConfig(productId, stage, {
        enabled: true,
        boardRevisionId: formRevisionId,
        watchBranch: formBranch || null,
        signingKeyId: formSigningKeyId || null,
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
        {#if config?.enabled && config?.watchBranch}
          <span class="px-1.5 py-0.5 text-2xs rounded bg-surface-2 text-text-tertiary flex items-center gap-1">
            <GitBranch size={10} /> {config.watchBranch}
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
          class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
        >
          <option value="">— Select revision —</option>
          {#each revisions as rev}
            <option value={rev.id}>{rev.version.toUpperCase()} ({rev.ckBoardsName})</option>
          {/each}
        </select>
      </div>

      <!-- Branch + Signing Key -->
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label for="stage-branch-{stage}" class="mb-1 block text-2xs font-medium text-text-tertiary">Watch Branch</label>
          {#if loadingBranches}
            <div class="flex items-center gap-2 py-2 text-2xs text-text-tertiary">
              <Loader2 size={12} class="animate-spin" /> Loading branches...
            </div>
          {:else if repoBranches.length > 0}
            <select
              id="stage-branch-{stage}"
              bind:value={formBranch}
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-none"
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
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
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
            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
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

      <!-- Info -->
      <div class="rounded bg-surface-0 border border-border-subtle px-3 py-2 text-2xs text-text-tertiary flex items-center gap-2">
        <Zap size={12} class="text-accent shrink-0" />
        Enabling this stage will create {STAGE_BUILD_COUNTS[stage] || '?'} firmware builds when triggered. Start initial builds now, or wait for next push to the watched branch.
      </div>

      <!-- Actions -->
      <div class="flex gap-2">
        <button
          onclick={saveAndEnable}
          disabled={saving || !formRevisionId}
          class="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Enable & Build Now'}
        </button>
        <button
          onclick={async () => { await saveAndEnable(); /* TODO: don't trigger build */ }}
          disabled={saving || !formRevisionId}
          class="rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2 disabled:opacity-50"
        >
          Enable (Build on Next Push)
        </button>
        <button
          onclick={() => { configuring = false; expanded = false; }}
          class="rounded-lg px-4 py-2 text-sm font-medium text-text-tertiary hover:bg-surface-2"
        >
          Cancel
        </button>
      </div>
    </div>
  {/if}

  <!-- Enabled summary -->
  {#if expanded && !configuring && config?.enabled}
    <div class="border-t border-border px-4 py-3 space-y-3">
      <div class="grid grid-cols-3 gap-3 text-sm">
        <div>
          <span class="block text-2xs text-text-tertiary">Revision</span>
          <span class="font-mono text-text-primary">{config.boardRevision?.ckBoardsName || '—'}</span>
        </div>
        <div>
          <span class="block text-2xs text-text-tertiary">Branch</span>
          <span class="font-mono text-text-primary flex items-center gap-1">
            <GitBranch size={12} /> {config.watchBranch || '—'}
          </span>
        </div>
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
