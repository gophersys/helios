<script lang="ts">
  import { onMount } from 'svelte';
  import type { ProductStageConfig, Secret, StageType } from '$lib/types/stages';
  import { stageName, stageDescription } from '$lib/types/stages';
  import type { BoardRevision } from '$lib/types/models';
  import { listStageConfigs, initializeStages, createStageConfig, updateStageConfig, deleteStageConfig } from '$lib/services/stages';
  import { apiFetch } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import StageConfigWizard from './stage-config-wizard.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import ConfirmDeleteDialog from '$lib/components/ui/confirm-delete-dialog.svelte';
  import {
    Loader2, Settings, CircuitBoard, GitBranch, Zap, Clock, Hand,
    GitPullRequest, GitMerge, Plus, Trash2,
  } from 'lucide-svelte';

  interface Props {
    productId: string;
    productName?: string;
    revisions?: BoardRevision[];
    boardRevisionId?: string;
    fwRepoSlug?: string;
    stageType?: StageType;
    emptyLabel?: string;
    enableLabel?: string;
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
    emptyLabel = 'Validation not configured',
    enableLabel = 'Enable Validation',
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
  let initializing = $state(false);

  // Wizard state
  let wizardOpen = $state(false);
  let wizardStage = $state(1);
  let wizardConfig = $state<ProductStageConfig | undefined>(undefined);
  let wizardRevision = $state<BoardRevision | null>(null);

  // Delete state
  let deleteTarget = $state<{ stage: number; name: string } | null>(null);

  /** Configs filtered to the current board revision (used for empty-state check) */
  const filteredConfigs = $derived(
    boardRevisionId ? configs.filter((c) => c.boardRevisionId === boardRevisionId) : configs
  );

  const activeRevisions = $derived(
    revisions
      .filter((r) => r.status === 'ACTIVE')
      .filter((r) => !boardRevisionId || r.id === boardRevisionId)
  );

  onMount(async () => {
    await Promise.all([loadConfigs(), loadSecrets()]);
  });

  async function loadConfigs() {
    loading = true;
    error = null;
    try {
      const all = await listStageConfigs(productId, stageType);
      configs = all;
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
      if (stageType === 'MANUFACTURING') {
        const cfg = await createStageConfig(productId, { type: 'MANUFACTURING', stage: 1, name: 'Manufacturing', boardRevisionId });
        configs = [cfg];
      } else {
        configs = await initializeStages(productId, boardRevisionId);
      }
      onRefresh?.();
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : 'Failed to enable';
    } finally {
      initializing = false;
    }
  }

  /** Get all configs for a given stage number, filtered by boardRevisionId when set */
  function getConfigsForStage(stageNum: number): ProductStageConfig[] {
    return configs.filter((c) => c.stage === stageNum && (!boardRevisionId || c.boardRevisionId === boardRevisionId));
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

  async function handleDisableConfig(cfg: ProductStageConfig) {
    error = null;
    try {
      await updateStageConfig(productId, cfg.stage, { enabled: false });
      await loadConfigs();
      onRefresh?.();
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : 'Failed to disable stage';
    }
  }

  async function handleEnableConfig(cfg: ProductStageConfig) {
    error = null;
    try {
      await updateStageConfig(productId, cfg.stage, { enabled: true });
      await loadConfigs();
      onRefresh?.();
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : 'Failed to enable stage';
    }
  }

  async function handleDeleteConfig(stageNum: number) {
    error = null;
    try {
      await deleteStageConfig(productId, stageNum);
      await loadConfigs();
      onRefresh?.();
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : 'Failed to delete stage config';
    }
  }
</script>

<div class="space-y-4">
  <ErrorAlert message={error} />

  {#if loading}
    <div class="flex items-center gap-2 py-8 text-sm text-text-tertiary justify-center">
      <Loader2 size={16} class="animate-spin" /> Loading stages...
    </div>
  {:else if filteredConfigs.length === 0}
    <div class="text-center py-8">
      <p class="text-sm text-text-secondary mb-4">{emptyLabel}</p>
      <button class="btn btn-sm btn-primary" disabled={initializing} onclick={handleInitialize}>
        {initializing ? 'Enabling...' : enableLabel}
      </button>
    </div>
  {:else}
    <!-- Stage list — grouped by stage number, showing per-revision configs -->
    {#each stageNumbers as stageNum}
      {@const stageConfigs = getConfigsForStage(stageNum)}
      {@const name = stageName(stageType, stageNum)}
      {@const desc = stageDescription(stageType, stageNum)}
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

        <!-- Stage config (single revision — subtabs handle revision selection) -->
        {#if activeRevisions.length > 0}
          {@const rev = activeRevisions[0]}
          {@const cfg = getConfig(stageNum, rev.id)}
          <div class="px-4 py-3">
            {#if cfg && cfg.enabled}
              <!-- Enabled — show config summary + actions -->
              <div class="flex items-center gap-4">
                <div class="flex-1 flex items-center gap-3 text-2xs text-text-tertiary">
                  {#if cfg.watchBranch}
                    <span class="flex items-center gap-1 font-mono bg-surface-0 rounded px-2 py-0.5">
                      <GitBranch size={10} /> {cfg.watchBranch}
                    </span>
                  {/if}
                  {#if cfg.triggerTypes?.length}
                    <span class="flex items-center gap-1">
                      {#each cfg.triggerTypes as t}
                        {@const TIcon = triggerIcon(t)}
                        <span class="flex items-center gap-1 bg-surface-0 rounded px-2 py-0.5">
                          <TIcon size={10} /> {t.replace('_', ' ')}
                        </span>
                      {/each}
                    </span>
                  {/if}
                  {#if cfg.buildMatrix?.length}
                    <span class="bg-surface-0 rounded px-2 py-0.5">{cfg.buildMatrix.length} build{cfg.buildMatrix.length !== 1 ? 's' : ''}</span>
                  {/if}
                </div>
                <button
                  onclick={() => openWizard(stageNum, rev, cfg)}
                  class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-2xs font-medium text-text-secondary hover:bg-surface-2 hover:text-text-primary transition-colors"
                >
                  <Settings size={12} /> Edit
                </button>
                {#if canManage}
                  <button
                    onclick={() => handleDisableConfig(cfg)}
                    class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-2xs font-medium text-text-tertiary hover:bg-warning-muted hover:text-warning transition-colors"
                    title="Disable this stage"
                  >
                    Disable
                  </button>
                  <button
                    onclick={() => deleteTarget = { stage: cfg.stage, name: `${stageName(stageType, cfg.stage)}` }}
                    class="flex items-center justify-center rounded-lg p-1.5 text-text-tertiary hover:bg-error-muted hover:text-error transition-colors"
                    title="Delete stage config"
                  >
                    <Trash2 size={12} />
                  </button>
                {/if}
              </div>
            {:else if cfg && !cfg.enabled}
              <!-- Exists but disabled -->
              <div class="flex items-center gap-4">
                <div class="flex-1">
                  <span class="text-2xs text-text-tertiary">Disabled</span>
                </div>
                {#if canManage}
                  <button
                    onclick={() => handleEnableConfig(cfg)}
                    class="flex items-center gap-1.5 rounded-lg border border-accent/30 bg-accent-muted px-3 py-1.5 text-2xs font-medium text-accent hover:bg-accent/15 transition-colors"
                  >
                    Enable
                  </button>
                {/if}
                <button
                  onclick={() => openWizard(stageNum, rev, cfg)}
                  class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-2xs font-medium text-text-secondary hover:bg-surface-2 hover:text-text-primary transition-colors"
                >
                  <Settings size={12} /> Edit
                </button>
                {#if canManage}
                  <button
                    onclick={() => deleteTarget = { stage: cfg.stage, name: `${stageName(stageType, cfg.stage)}` }}
                    class="flex items-center justify-center rounded-lg p-1.5 text-text-tertiary hover:bg-error-muted hover:text-error transition-colors"
                    title="Delete stage config"
                  >
                    <Trash2 size={12} />
                  </button>
                {/if}
              </div>
            {:else}
              <!-- Not configured -->
              <div class="flex items-center gap-4">
                <div class="flex-1">
                  <span class="text-2xs text-text-tertiary">Not configured</span>
                </div>
                <button
                  onclick={() => openWizard(stageNum, rev, cfg)}
                  class="flex items-center gap-1.5 rounded-lg border border-accent/30 bg-accent-muted px-3 py-1.5 text-2xs font-medium text-accent hover:bg-accent/15 transition-colors"
                >
                  <Plus size={12} /> Configure
                </button>
              </div>
            {/if}
          </div>
        {/if}
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

<ConfirmDeleteDialog
  open={!!deleteTarget}
  entityType="stage config"
  entityName={deleteTarget?.name || ''}
  onConfirm={() => { handleDeleteConfig(deleteTarget!.stage); deleteTarget = null; }}
  onCancel={() => (deleteTarget = null)}
/>
