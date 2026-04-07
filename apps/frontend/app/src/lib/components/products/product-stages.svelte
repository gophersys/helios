<script lang="ts">
  import { onMount } from 'svelte';
  import type { ProductStageConfig, Secret } from '$lib/types/stages';
  import { STAGE_NAMES, STAGE_DESCRIPTIONS } from '$lib/types/stages';
  import type { BoardRevision } from '$lib/types/models';
  import { listStageConfigs, initializeStages, updateStageConfig } from '$lib/services/stages';
  import { apiFetch } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import StageConfigWizard from './stage-config-wizard.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import {
    Loader2, Settings, CircuitBoard, GitBranch, Zap, Clock, Hand,
    GitPullRequest, GitMerge, Plus,
  } from 'lucide-svelte';

  interface Props {
    productId: string;
    productName?: string;
    revisions?: BoardRevision[];
    fwRepoSlug?: string;
    onRefresh?: () => void;
  }

  let { productId, productName = '', revisions = [], fwRepoSlug = '', onRefresh }: Props = $props();

  let configs = $state<ProductStageConfig[]>([]);
  let secrets = $state<Secret[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let initializing = $state(false);

  // Wizard state
  let wizardOpen = $state(false);
  let wizardStage = $state(1);
  let wizardConfig = $state<ProductStageConfig | undefined>(undefined);
  let wizardRevision = $state<BoardRevision | null>(null);

  const activeRevisions = $derived(revisions.filter((r) => r.status === 'ACTIVE'));

  onMount(async () => {
    await Promise.all([loadConfigs(), loadSecrets()]);
  });

  async function loadConfigs() {
    loading = true;
    error = null;
    try {
      configs = await listStageConfigs(productId);
      onRefresh?.();
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : 'Failed to load stage configs';
    } finally {
      loading = false;
    }
  }

  async function loadSecrets() {
    try {
      const res = await apiFetch<ApiResponse<Secret[]>>('/v2/system/secrets');
      secrets = res.data ?? [];
    } catch {
      secrets = [];
    }
  }

  async function handleInitialize() {
    initializing = true;
    error = null;
    try {
      configs = await initializeStages(productId);
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : 'Failed to initialize stages';
    } finally {
      initializing = false;
    }
  }

  /** Get all configs for a given stage number (could be multiple — one per revision) */
  function getConfigsForStage(stageNum: number): ProductStageConfig[] {
    return configs.filter((c) => c.stage === stageNum);
  }

  /** Get a specific config for stage + revision */
  function getConfig(stageNum: number, revId: string): ProductStageConfig | undefined {
    return configs.find((c) => c.stage === stageNum && c.boardRevisionId === revId);
  }

  function openWizard(stageNum: number, rev: BoardRevision | null, existingConfig?: ProductStageConfig) {
    wizardStage = stageNum;
    wizardRevision = rev;
    wizardConfig = existingConfig;
    wizardOpen = true;
  }

  function triggerIcon(type: string) {
    switch (type) {
      case 'pr_push': return GitPullRequest;
      case 'pr_merge': return GitMerge;
      case 'auto': return Zap;
      case 'schedule': return Clock;
      default: return Hand;
    }
  }

  function revisionLabel(revId: string | null | undefined): string {
    if (!revId) return '—';
    const rev = revisions.find((r) => r.id === revId);
    return rev ? rev.version : '—';
  }
</script>

<div class="space-y-4">
  <ErrorAlert message={error} />

  {#if loading}
    <div class="flex items-center gap-2 py-8 text-sm text-text-tertiary justify-center">
      <Loader2 size={16} class="animate-spin" /> Loading stages...
    </div>
  {:else if configs.length === 0}
    <div class="text-center py-8">
      <p class="text-sm text-text-secondary mb-2">No validation stages configured for {productName}.</p>
      <p class="text-2xs text-text-tertiary mb-4">Initialize the 5 standard stages, then configure them per hardware revision.</p>
      <button class="btn btn-sm btn-primary" disabled={initializing} onclick={handleInitialize}>
        {initializing ? 'Initializing...' : 'Initialize Stages'}
      </button>
    </div>
  {:else}
    <!-- Stage list — grouped by stage number, showing per-revision configs -->
    {#each [1, 2, 3, 4, 5] as stageNum}
      {@const stageConfigs = getConfigsForStage(stageNum)}
      {@const name = STAGE_NAMES[stageNum] || `Stage ${stageNum}`}
      {@const desc = STAGE_DESCRIPTIONS[stageNum] || ''}
      {@const hasAnyEnabled = stageConfigs.some((c) => c.enabled)}

      <div class="rounded-lg border border-border overflow-hidden">
        <!-- Stage header -->
        <div class="flex items-center gap-4 px-4 py-3 bg-surface-0/50">
          <div class="w-8 h-8 flex items-center justify-center rounded-lg text-sm font-bold shrink-0
            {hasAnyEnabled ? 'bg-accent text-white' : 'bg-surface-2 text-text-tertiary'}">
            {stageNum}
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-sm font-semibold text-text-primary">{name}</span>
              {#if hasAnyEnabled}
                <StatusBadge status="ACTIVE" />
              {/if}
            </div>
            <p class="text-2xs text-text-tertiary truncate">{desc}</p>
          </div>
        </div>

        <!-- Per-revision configs -->
        <div class="divide-y divide-border-subtle">
          {#each activeRevisions as rev}
            {@const cfg = getConfig(stageNum, rev.id)}
            <div class="flex items-center gap-4 px-4 py-2.5 hover:bg-surface-2/30 transition-colors">
              <!-- Revision badge -->
              <div class="flex items-center gap-2 min-w-[120px]">
                <CircuitBoard size={14} class="text-text-tertiary" />
                <span class="text-sm font-medium text-text-primary">{rev.version}</span>
                <span class="font-mono text-2xs text-text-tertiary">{rev.ckBoardsName}</span>
              </div>

              {#if cfg && cfg.enabled}
                <!-- Enabled — show config summary -->
                <div class="flex-1 flex items-center gap-3 text-2xs text-text-tertiary">
                  {#if cfg.watchBranch}
                    <span class="flex items-center gap-1 font-mono">
                      <GitBranch size={10} /> {cfg.watchBranch}
                    </span>
                  {/if}
                  {#if cfg.triggerTypes?.length}
                    <span class="flex items-center gap-1">
                      {#each cfg.triggerTypes as t}
                        {@const TIcon = triggerIcon(t)}
                        <TIcon size={10} />
                      {/each}
                    </span>
                  {/if}
                </div>
                <StatusBadge status="ACTIVE" />
                <button
                  onclick={() => openWizard(stageNum, rev, cfg)}
                  class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-2xs font-medium text-text-secondary hover:bg-surface-2 hover:text-text-primary transition-colors"
                >
                  <Settings size={12} /> Edit
                </button>
              {:else}
                <!-- Not configured for this revision -->
                <div class="flex-1">
                  <span class="text-2xs text-text-tertiary">Not configured</span>
                </div>
                <button
                  onclick={() => openWizard(stageNum, rev, cfg)}
                  class="flex items-center gap-1.5 rounded-lg border border-accent/30 bg-accent-muted px-3 py-1.5 text-2xs font-medium text-accent hover:bg-accent/15 transition-colors"
                >
                  <Plus size={12} /> Configure
                </button>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/each}
  {/if}
</div>

<StageConfigWizard
  open={wizardOpen}
  stage={wizardStage}
  config={wizardConfig}
  targetRevision={wizardRevision}
  {productId}
  {fwRepoSlug}
  {revisions}
  {secrets}
  onClose={() => (wizardOpen = false)}
  onSaved={loadConfigs}
/>
