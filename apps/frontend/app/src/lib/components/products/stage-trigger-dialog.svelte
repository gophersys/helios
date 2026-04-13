<script lang="ts">
  import { Loader2, Play, CheckCircle, Package } from 'lucide-svelte';
  import Modal from '$lib/components/ui/modal.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import { api } from '$lib/api';
  import { triggerStageRun } from '$lib/services/stages';
  import type { ApiResponse } from '$lib/types';
  import type { AssetSet } from '$lib/types/models';

  interface Props {
    open: boolean;
    productId: string;
    stage: number;
    stageType: string;
    onClose: () => void;
    onTriggered: () => void;
  }

  let { open, productId, stage, stageType, onClose, onTriggered }: Props = $props();

  let assetSets = $state<AssetSet[]>([]);
  let loading = $state(false);
  let selectedAssetSetId = $state<string>('');
  let triggering = $state(false);
  let error = $state<string | null>(null);
  let success = $state(false);

  $effect(() => {
    if (open) {
      // Reset state on open
      selectedAssetSetId = '';
      error = null;
      success = false;
      triggering = false;
      fetchAssetSets();
    }
  });

  async function fetchAssetSets() {
    loading = true;
    error = null;
    try {
      const res = await api.get<ApiResponse<AssetSet[]>>(
        `/v2/products/${productId}/asset-sets?stage=${stage}&stageType=VALIDATION&status=COMPLETE`
      );
      assetSets = res.data || [];
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load asset sets';
      assetSets = [];
    } finally {
      loading = false;
    }
  }

  async function handleTrigger() {
    if (!selectedAssetSetId) return;
    triggering = true;
    error = null;
    try {
      await triggerStageRun(productId, stage, selectedAssetSetId);
      success = true;
      setTimeout(() => {
        onTriggered();
        onClose();
      }, 1200);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to trigger validation run';
    } finally {
      triggering = false;
    }
  }

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }
</script>

<Modal {open} onclose={onClose} title="Run Validation" size="lg">
  {#if success}
    <div class="flex flex-col items-center justify-center py-8 gap-3">
      <CheckCircle size={32} class="text-success" />
      <p class="text-sm font-medium text-text-primary">Validation run queued</p>
      <p class="text-2xs text-text-tertiary">The run will start shortly.</p>
    </div>
  {:else}
    <div class="space-y-4">
      {#if error}
        <div class="rounded-lg bg-error-muted px-3 py-2 text-sm text-error">
          {error}
        </div>
      {/if}

      <p class="text-sm text-text-secondary">
        Select a completed asset set to use for this validation run.
      </p>

      {#if loading}
        <div class="flex items-center justify-center gap-2 py-8 text-sm text-text-tertiary">
          <Loader2 size={16} class="animate-spin" />
          Loading asset sets...
        </div>
      {:else if assetSets.length === 0}
        <div class="flex flex-col items-center justify-center py-8 gap-2">
          <Package size={24} class="text-text-tertiary" />
          <p class="text-sm text-text-secondary">No completed asset sets for this stage.</p>
          <p class="text-2xs text-text-tertiary">Build or upload assets first.</p>
        </div>
      {:else}
        <div class="space-y-2 max-h-[40vh] overflow-y-auto">
          {#each assetSets as set}
            {@const selected = selectedAssetSetId === set.id}
            <button
              onclick={() => (selectedAssetSetId = set.id)}
              class="flex w-full items-center gap-3 rounded-lg border-2 px-4 py-3 text-left transition-all
                {selected ? 'border-accent bg-accent-muted' : 'border-border bg-surface-0 hover:border-text-tertiary'}"
            >
              <div class="flex h-4 w-4 items-center justify-center rounded-full border-2 shrink-0
                {selected ? 'border-accent bg-accent' : 'border-text-tertiary'}">
                {#if selected}
                  <div class="h-1.5 w-1.5 rounded-full bg-white"></div>
                {/if}
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-semibold text-text-primary">{set.version}</span>
                  {#if set.variant}
                    <span class="text-2xs text-text-tertiary">({set.variant})</span>
                  {/if}
                  <StatusBadge status={set.source} />
                </div>
                <div class="flex items-center gap-3 mt-0.5">
                  {#if set.branch}
                    <span class="font-mono text-2xs text-text-tertiary">{set.branch}</span>
                  {/if}
                  {#if set.commitSha}
                    <span class="font-mono text-2xs text-text-tertiary">{set.commitSha.slice(0, 8)}</span>
                  {/if}
                  <span class="text-2xs text-text-tertiary">{formatDate(set.createdAt)}</span>
                </div>
              </div>
            </button>
          {/each}
        </div>
      {/if}
    </div>
  {/if}

  {#snippet footer()}
    {#if !success}
      <button onclick={onClose} disabled={triggering} class="btn btn-sm btn-ghost">
        Cancel
      </button>
      <button
        onclick={handleTrigger}
        disabled={!selectedAssetSetId || triggering}
        class="btn btn-sm btn-primary"
      >
        {#if triggering}
          <Loader2 size={14} class="animate-spin" />
          Triggering...
        {:else}
          <Play size={14} />
          Run Validation
        {/if}
      </button>
    {/if}
  {/snippet}
</Modal>
