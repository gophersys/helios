<script lang="ts">
  import type { ProductStageConfig } from '$lib/types/stages';
  import { STAGE_NAMES, STAGE_DESCRIPTIONS } from '$lib/types/stages';
  import { updateStageConfig } from '$lib/services/stages';
  import StageConfigForm from './stage-config-form.svelte';
  import CodeEditor from '$lib/components/ui/code-editor.svelte';

  interface Props {
    stage: number;
    config: ProductStageConfig | undefined;
    productId: string;
    onUpdated: () => void;
  }

  let { stage, config, productId, onUpdated }: Props = $props();

  let expanded = $state(false);
  let editing = $state(false);

  const stageIcons: Record<number, string> = {
    1: 'SM',
    2: 'SI',
    3: 'IN',
    4: 'NY',
    5: 'FU',
  };

  const stageBadgeColors: Record<number, string> = {
    1: 'bg-blue-500/10 text-blue-400',
    2: 'bg-cyan-500/10 text-cyan-400',
    3: 'bg-amber-500/10 text-amber-400',
    4: 'bg-purple-500/10 text-purple-400',
    5: 'bg-red-500/10 text-red-400',
  };

  async function handleToggleEnabled(e: Event) {
    e.stopPropagation();
    if (!config) return;
    try {
      await updateStageConfig(productId, stage, { enabled: !config.enabled });
      onUpdated();
    } catch (err) {
      console.error('Failed to toggle stage:', err);
    }
  }

  function handleSaved() {
    editing = false;
    onUpdated();
  }

  function handleCancelEdit() {
    editing = false;
  }
</script>

<div class="border border-border rounded-lg bg-surface-1 overflow-hidden">
  <!-- Header -->
  <button
    class="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface-2 transition-colors text-left"
    onclick={() => expanded = !expanded}
  >
    <span class="flex items-center justify-center w-8 h-8 rounded {stageBadgeColors[stage] || 'bg-surface-2 text-text-secondary'} text-xs font-bold">
      {stageIcons[stage] || stage}
    </span>
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2">
        <span class="font-medium text-text-primary">
          Stage {stage}
        </span>
        <span class="px-1.5 py-0.5 text-2xs rounded font-medium {stageBadgeColors[stage] || 'bg-surface-2 text-text-tertiary'}">
          {STAGE_NAMES[stage] || 'Unknown'}
        </span>
      </div>
      <p class="text-sm text-text-tertiary truncate">{STAGE_DESCRIPTIONS[stage]}</p>
    </div>

    <div class="flex items-center gap-3">
      {#if config}
        <div
          role="button"
          tabindex="0"
          class="px-2 py-1 text-xs rounded font-medium cursor-pointer {config.enabled ? 'bg-success-muted text-success' : 'bg-surface-2 text-text-tertiary'}"
          onclick={handleToggleEnabled}
          onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleToggleEnabled(e); } }}
        >
          {config.enabled ? 'Enabled' : 'Disabled'}
        </div>
      {:else}
        <span class="text-xs text-text-tertiary">Not configured</span>
      {/if}
      <svg
        class="w-4 h-4 text-text-tertiary transition-transform {expanded ? 'rotate-180' : ''}"
        fill="none" stroke="currentColor" viewBox="0 0 24 24"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </div>
  </button>

  <!-- Expanded content -->
  {#if expanded}
    <div class="border-t border-border px-4 py-4 overflow-hidden min-w-0">
      {#if editing}
        <StageConfigForm
          {productId}
          {stage}
          {config}
          onSaved={handleSaved}
          onCancel={handleCancelEdit}
        />
      {:else if config}
        <div class="grid grid-cols-2 gap-4 text-sm">
          <div>
            <h4 class="font-medium text-text-secondary mb-2">Build Configuration</h4>
            <dl class="space-y-1">
              <div class="flex justify-between">
                <dt class="text-text-tertiary">Target</dt>
                <dd class="text-text-primary font-mono text-xs">{config.buildTarget || '—'}</dd>
              </div>
              <div class="flex justify-between">
                <dt class="text-text-tertiary">Repo</dt>
                <dd class="text-text-primary font-mono text-xs truncate max-w-[200px]">{config.fwRepoUrl || '—'}</dd>
              </div>
              <div class="flex justify-between">
                <dt class="text-text-tertiary">Branch</dt>
                <dd class="text-text-primary font-mono text-xs">{config.fwRepoBranch || '—'}</dd>
              </div>
              <div class="flex justify-between">
                <dt class="text-text-tertiary">Variant</dt>
                <dd class="text-text-primary">{config.buildVariant || '—'}</dd>
              </div>
              {#if config.buildMatrix}
                <div class="flex justify-between">
                  <dt class="text-text-tertiary">Matrix builds</dt>
                  <dd class="text-text-primary">{config.buildMatrix.length}</dd>
                </div>
              {/if}
            </dl>
          </div>

          <div>
            <h4 class="font-medium text-text-secondary mb-2">Test Configuration</h4>
            <dl class="space-y-1">
              <div class="flex justify-between">
                <dt class="text-text-tertiary">Test dir</dt>
                <dd class="text-text-primary font-mono text-xs">{config.testDirectory || '—'}</dd>
              </div>
              <div class="flex justify-between">
                <dt class="text-text-tertiary">Timeout</dt>
                <dd class="text-text-primary">{config.testTimeout}s</dd>
              </div>
              <div class="flex justify-between">
                <dt class="text-text-tertiary">Max duration</dt>
                <dd class="text-text-primary">{Math.round(config.maxDurationSec / 60)}m</dd>
              </div>
              <div class="flex justify-between">
                <dt class="text-text-tertiary">Needs bench</dt>
                <dd class="text-text-primary">{config.requiresBench ? 'Yes' : 'No'}</dd>
              </div>
            </dl>
          </div>
        </div>

        {#if config.buildScript}
          <div class="mt-4">
            <div class="flex items-center justify-between mb-2">
              <h4 class="font-medium text-text-secondary">Build Script</h4>
              <span class="text-2xs text-text-tertiary">{config.buildScript.split('\n').length} lines</span>
            </div>
            <CodeEditor value={config.buildScript} readonly maxHeight="400px" />
          </div>
        {/if}

        <div class="mt-4 flex justify-end">
          <button
            class="px-3 py-1.5 text-sm bg-surface-2 text-text-primary rounded hover:bg-surface-0 transition-colors"
            onclick={() => editing = true}
          >
            Edit Configuration
          </button>
        </div>
      {:else}
        <p class="text-text-tertiary text-sm">This stage has not been configured yet.</p>
      {/if}
    </div>
  {/if}
</div>
