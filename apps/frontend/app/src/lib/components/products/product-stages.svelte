<script lang="ts">
  import { onMount } from 'svelte';
  import type { ProductStageConfig, Secret, StageType } from '$lib/types/stages';
  import { stageName, stageDescription } from '$lib/types/stages';
  import type { BoardRevision } from '$lib/types/models';
  import { listStageConfigs, updateStageConfig } from '$lib/services/stages';
  import { apiFetch } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import StageConfigWizard from './stage-config-wizard.svelte';
  import StageTriggerDialog from './stage-trigger-dialog.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import {
    Loader2, Settings, GitBranch, Zap, Clock, Hand,
    GitPullRequest, GitMerge, Play,
  } from 'lucide-svelte';

  interface Props {
    productId: string;
    productName?: string;
    revisions?: BoardRevision[];
    boardRevisionId?: string;
    fwRepoSlug?: string;
    stageType?: StageType;
    canManage?: boolean;
    onRefresh?: () => void;
  }

  let {
    productId,
    productName = '',
    revisions = [],
    boardRevisionId,
    fwRepoSlug = '',
    stageType = 'VALIDATION' as StageType,
    canManage = false,
    onRefresh,
  }: Props = $props();

  const stageNumbers = $derived(
    stageType === 'MANUFACTURING' ? [1] : [1, 2, 3, 4, 5]
  );

  let configs = $state<ProductStageConfig[]>([]);
  let secrets = $state<Secret[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Wizard
  let wizardOpen = $state(false);
  let wizardStage = $state(1);
  let wizardConfig = $state<ProductStageConfig | undefined>(undefined);
  let wizardRevision = $state<BoardRevision | null>(null);

  // Trigger dialog
  let triggerDialogOpen = $state(false);
  let triggerStageNum = $state(1);

  const activeRevision = $derived(
    revisions.find((r) => r.status === 'ACTIVE' && (!boardRevisionId || r.id === boardRevisionId))
  );

  onMount(async () => {
    await Promise.all([loadConfigs(), loadSecrets()]);
  });

  async function loadConfigs() {
    loading = true;
    error = null;
    try {
      configs = await listStageConfigs(productId, stageType);
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

  function getConfig(stageNum: number, revId: string): ProductStageConfig | undefined {
    return configs.find((c) => c.stage === stageNum && c.boardRevisionId === revId);
  }

  function openWizard(stageNum: number, rev: BoardRevision, existingConfig?: ProductStageConfig) {
    wizardStage = stageNum;
    wizardRevision = rev;
    wizardConfig = existingConfig;
    wizardOpen = true;
  }

  function openTriggerDialog(stageNum: number) {
    triggerStageNum = stageNum;
    triggerDialogOpen = true;
  }

  async function handleDisable(cfg: ProductStageConfig) {
    error = null;
    try {
      await updateStageConfig(productId, cfg.stage, { enabled: false });
      await loadConfigs();
      onRefresh?.();
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : 'Failed to disable stage';
    }
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
</script>

<div class="space-y-3">
  <ErrorAlert message={error} />

  {#if loading}
    <div class="flex items-center gap-2 py-8 text-sm text-text-tertiary justify-center">
      <Loader2 size={16} class="animate-spin" /> Loading stages...
    </div>
  {:else if !activeRevision}
    <div class="text-center py-8">
      <p class="text-sm text-text-secondary">No active board revision.</p>
      <p class="text-2xs text-text-tertiary mt-1">Add a revision in the Hardware tab first.</p>
    </div>
  {:else}
    {#each stageNumbers as stageNum}
      {@const cfg = getConfig(stageNum, activeRevision.id)}
      {@const name = stageName(stageType, stageNum)}
      {@const desc = stageDescription(stageType, stageNum)}
      {@const enabled = cfg?.enabled === true}

      <div class="rounded-lg border {enabled ? 'border-accent/30' : 'border-border'} overflow-hidden">
        <div class="flex items-center gap-4 px-4 py-3 {enabled ? 'bg-accent/5' : 'bg-surface-0/50'}">
          <!-- Stage number -->
          <div class="w-8 h-8 flex items-center justify-center rounded-lg text-sm font-bold shrink-0
            {enabled ? 'bg-accent text-white' : 'bg-surface-2 text-text-tertiary'}">
            {stageNum}
          </div>

          <!-- Name + description -->
          <div class="flex-1 min-w-0">
            <span class="text-sm font-semibold text-text-primary">{name}</span>
            <p class="text-2xs text-text-tertiary truncate">{desc}</p>
          </div>

          <!-- Actions -->
          {#if enabled}
            {#if stageType === 'VALIDATION' && canManage}
              <button onclick={() => openTriggerDialog(stageNum)} class="btn btn-sm btn-primary">
                <Play size={12} /> Run
              </button>
            {/if}
            <button onclick={() => openWizard(stageNum, activeRevision, cfg)} class="btn btn-sm btn-ghost">
              <Settings size={12} /> Edit
            </button>
            {#if canManage}
              <button onclick={() => handleDisable(cfg)} class="btn btn-sm btn-ghost text-warning hover:bg-warning-muted">
                Disable
              </button>
            {/if}
          {:else}
            <button onclick={() => openWizard(stageNum, activeRevision, cfg)} class="btn btn-sm btn-primary">
              Enable
            </button>
          {/if}
        </div>

        <!-- Config summary — always rendered for uniform height -->
        <div class="px-4 py-2 border-t {enabled ? 'border-accent/10' : 'border-border-subtle'} min-h-8 flex flex-wrap items-center gap-2 text-2xs text-text-tertiary">
          {#if enabled && cfg}
            {#if cfg.assetSources?.length}
              {#each cfg.assetSources as src}
                <span class="rounded bg-surface-2 px-2 py-0.5 font-medium">
                  {src === 'BUILD_SERVICE' ? 'Concord Builds' : src === 'EXTERNAL_CI' ? 'External CI' : 'Manual'}
                </span>
              {/each}
            {/if}
            {#if cfg.watchBranch}
              <span class="flex items-center gap-1 font-mono bg-surface-0 rounded px-2 py-0.5">
                <GitBranch size={10} /> {cfg.watchBranch}
              </span>
            {/if}
            {#if cfg.assetSources?.includes('BUILD_SERVICE') && cfg.triggerTypes?.length}
              {#each cfg.triggerTypes as t}
                {@const TIcon = triggerIcon(t)}
                <span class="flex items-center gap-1 bg-surface-0 rounded px-2 py-0.5">
                  <TIcon size={10} /> {t.replace('_', ' ')}
                </span>
              {/each}
            {/if}
            {#if cfg.buildMatrix?.length}
              <span class="flex items-center gap-1 bg-accent-muted text-accent rounded px-2 py-0.5 font-medium">
                {cfg.buildMatrix.length} build label{cfg.buildMatrix.length !== 1 ? 's' : ''}
              </span>
            {:else if cfg.assetSources?.includes('BUILD_SERVICE')}
              <span class="bg-warning-muted text-warning rounded px-2 py-0.5 font-medium">No build labels</span>
            {/if}
          {:else}
            <span class="text-text-tertiary opacity-50">Not enabled</span>
          {/if}
        </div>
      </div>
    {/each}
  {/if}
</div>

<StageConfigWizard
  open={wizardOpen}
  stage={wizardStage}
  {stageType}
  config={wizardConfig}
  targetRevision={wizardRevision}
  {productId}
  {fwRepoSlug}
  {revisions}
  {secrets}
  onClose={() => (wizardOpen = false)}
  onSaved={() => { loadConfigs(); onRefresh?.(); }}
/>

<StageTriggerDialog
  open={triggerDialogOpen}
  stage={triggerStageNum}
  {stageType}
  {productId}
  onClose={() => (triggerDialogOpen = false)}
  onTriggered={() => { loadConfigs(); onRefresh?.(); }}
/>
