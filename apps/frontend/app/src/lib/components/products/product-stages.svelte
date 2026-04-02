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
  import { Loader2, Settings, CircuitBoard, GitBranch, Zap, Clock, Hand, GitPullRequest, GitMerge } from 'lucide-svelte';

  interface Props {
    productId: string;
    productName?: string;
    revisions?: BoardRevision[];
    fwRepoSlug?: string;
  }

  let { productId, productName = '', revisions = [], fwRepoSlug = '' }: Props = $props();

  let configs = $state<ProductStageConfig[]>([]);
  let secrets = $state<Secret[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let initializing = $state(false);

  // Wizard state
  let wizardOpen = $state(false);
  let wizardStage = $state(1);

  const enabledCount = $derived(configs.filter((c) => c.enabled).length);

  onMount(async () => {
    await Promise.all([loadConfigs(), loadSecrets()]);
  });

  async function loadConfigs() {
    loading = true;
    error = null;
    try {
      configs = await listStageConfigs(productId);
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

  function getConfig(stage: number): ProductStageConfig | undefined {
    return configs.find((c) => c.stage === stage);
  }

  function openWizard(stage: number) {
    wizardStage = stage;
    wizardOpen = true;
  }

  async function handleQuickToggle(stage: number, enabled: boolean) {
    error = null;
    try {
      await updateStageConfig(productId, stage, { enabled });
      await loadConfigs();
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : 'Failed to update stage';
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

  function revisionLabel(revId: string | null | undefined): string {
    if (!revId) return '—';
    const rev = revisions.find((r) => r.id === revId);
    return rev ? `${rev.version} (${rev.ckBoardsName})` : '—';
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
      <p class="text-2xs text-text-tertiary mb-4">Initialize the 5 standard stages, then configure the ones you need.</p>
      <button
        class="btn btn-sm btn-primary"
        disabled={initializing}
        onclick={handleInitialize}
      >
        {initializing ? 'Initializing...' : 'Initialize Stages'}
      </button>
    </div>
  {:else}
    <div class="flex items-center justify-between mb-2">
      <h3 class="text-sm font-semibold text-text-primary">Validation Stages</h3>
      <span class="text-2xs text-text-tertiary">{enabledCount} of {configs.length} enabled</span>
    </div>

    <div class="rounded-lg border border-border overflow-hidden">
      {#each [1, 2, 3, 4, 5] as stageNum}
        {@const cfg = getConfig(stageNum)}
        {@const name = STAGE_NAMES[stageNum] || `Stage ${stageNum}`}
        <div class="flex items-center gap-4 px-4 py-3 border-b border-border-subtle last:border-b-0 hover:bg-surface-2/30 transition-colors">
          <!-- Stage number pill -->
          <div class="w-7 h-7 flex items-center justify-center rounded-lg text-xs font-bold shrink-0
            {cfg?.enabled ? 'bg-accent text-white' : 'bg-surface-2 text-text-tertiary'}">
            {stageNum}
          </div>

          <!-- Name + status -->
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium text-text-primary">{name}</span>
              {#if cfg?.enabled}
                <StatusBadge status="ACTIVE" />
              {:else}
                <span class="text-2xs text-text-tertiary">Disabled</span>
              {/if}
            </div>

            {#if cfg?.enabled}
              <!-- Config summary -->
              <div class="mt-0.5 flex items-center gap-3 text-2xs text-text-tertiary">
                {#if cfg.boardRevisionId}
                  <span class="flex items-center gap-1">
                    <CircuitBoard size={10} />
                    {revisionLabel(cfg.boardRevisionId)}
                  </span>
                {/if}
                {#if cfg.watchBranch}
                  <span class="flex items-center gap-1 font-mono">
                    <GitBranch size={10} />
                    {cfg.watchBranch}
                  </span>
                {/if}
                {#if cfg.triggerTypes?.length}
                  <span class="flex items-center gap-1">
                    {#each cfg.triggerTypes.slice(0, 3) as t}
                      {@const TIcon = triggerIcon(t)}
                      <TIcon size={10} />
                    {/each}
                  </span>
                {/if}
              </div>
            {/if}
          </div>

          <!-- Enable/disable toggle -->
          <button
            onclick={() => cfg && handleQuickToggle(stageNum, !cfg.enabled)}
            class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors shrink-0
              {cfg?.enabled ? 'bg-accent' : 'bg-surface-3'}"
            title={cfg?.enabled ? 'Disable stage' : 'Enable stage'}
          >
            <span class="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow-sm transition-transform
              {cfg?.enabled ? 'translate-x-4.5' : 'translate-x-0.5'}" />
          </button>

          <!-- Configure button -->
          <button
            onclick={() => openWizard(stageNum)}
            class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-2xs font-medium text-text-secondary hover:bg-surface-2 hover:text-text-primary transition-colors shrink-0"
            title="Configure stage"
          >
            <Settings size={12} />
            Configure
          </button>
        </div>
      {/each}
    </div>
  {/if}
</div>

<!-- Stage Configuration Wizard -->
<StageConfigWizard
  open={wizardOpen}
  stage={wizardStage}
  config={getConfig(wizardStage)}
  {productId}
  {revisions}
  {secrets}
  onClose={() => (wizardOpen = false)}
  onSaved={loadConfigs}
/>
