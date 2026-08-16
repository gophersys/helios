<script lang="ts">
  import { RefreshCw, Loader2, Layers } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import { apiFetch, api } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { StageBuildMatrixEntry } from '$lib/types/models';

  interface Props {
    productId: string;
    stage: number;
    configId?: string;
    canManage: boolean;
  }

  let { productId, stage, configId, canManage }: Props = $props();

  let entries = $state<StageBuildMatrixEntry[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let resetting = $state(false);

  async function loadMatrix() {
    loading = true;
    error = null;
    try {
      const cid = configId ? `?configId=${configId}` : '';
      const res = await apiFetch<ApiResponse<StageBuildMatrixEntry[]>>(
        `/v2/products/${productId}/stages/${stage}/build-matrix${cid}`
      );
      entries = Array.isArray(res.data) ? res.data : (res.data as any)?.data ?? [];
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load build matrix';
    } finally {
      loading = false;
    }
  }

  async function resetToDefaults() {
    resetting = true;
    error = null;
    try {
      const cid = configId ? `?configId=${configId}` : '';
      await api.post(`/v2/products/${productId}/stages/${stage}/build-matrix/reset${cid}`, {});
      await loadMatrix();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to reset build matrix';
    } finally {
      resetting = false;
    }
  }

  $effect(() => {
    if (productId && stage) loadMatrix();
  });
</script>

<div>
  <div class="flex items-center justify-between mb-3">
    <div class="flex items-center gap-2">
      <Layers size={14} class="text-text-tertiary" />
      <h4 class="text-sm font-semibold text-text-primary">Build Matrix</h4>
      {#if !loading}
        <span class="text-2xs text-text-tertiary">{entries.length} build{entries.length === 1 ? '' : 's'}</span>
      {/if}
    </div>
    {#if canManage}
      <button
        onclick={resetToDefaults}
        disabled={resetting}
        class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-2xs font-medium text-text-secondary hover:bg-surface-2 transition-colors disabled:opacity-50"
        title="Reset build matrix to defaults"
      >
        {#if resetting}
          <Loader2 size={12} class="animate-spin" /> Resetting...
        {:else}
          <RefreshCw size={12} /> Reset to Defaults
        {/if}
      </button>
    {/if}
  </div>

  {#if error}
    <div class="rounded-lg border border-error/20 bg-error-muted px-4 py-2.5 text-sm text-error mb-3">{error}</div>
  {/if}

  {#if loading}
    <div class="rounded-lg border border-border bg-surface-0 p-6 text-center">
      <div class="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent mx-auto"></div>
    </div>
  {:else if entries.length === 0}
    <div class="rounded-lg border border-dashed border-border bg-surface-0 p-6 text-center">
      <Layers size={24} class="mx-auto mb-2 text-text-tertiary opacity-30" />
      <p class="text-sm text-text-secondary">No build matrix entries</p>
      <p class="text-2xs text-text-tertiary mt-1">Reset to defaults to populate the build matrix for this stage.</p>
    </div>
  {:else}
    <div class="rounded-lg border border-border overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="bg-surface-0/50 border-b border-border-subtle">
            <th class="px-4 py-2 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Label</th>
            <th class="px-4 py-2 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">FW Type</th>
            <th class="px-4 py-2 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Variant</th>
            <th class="px-4 py-2 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Produces</th>
            <th class="px-4 py-2 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Git Ref</th>
          </tr>
        </thead>
        <tbody>
          {#each entries as entry, i}
            <tr class="border-b border-border-subtle last:border-b-0 {i % 2 === 0 ? '' : 'bg-surface-0/30'}">
              <td class="px-4 py-2">
                <span class="font-mono text-sm font-medium text-text-primary">{entry.label}</span>
                {#if entry.description}
                  <p class="text-2xs text-text-tertiary mt-0.5">{entry.description}</p>
                {/if}
              </td>
              <td class="px-4 py-2">
                <span class="text-sm text-text-secondary">{entry.fwType}</span>
              </td>
              <td class="px-4 py-2">
                <span class="text-sm text-text-secondary">{entry.variant}</span>
                {#if entry.configLog}
                  <span class="ml-1 text-2xs text-text-tertiary">(log)</span>
                {/if}
              </td>
              <td class="px-4 py-2">
                <div class="flex gap-1">
                  {#if entry.producesHex}
                    <span class="rounded-full bg-accent-muted px-2 py-0.5 text-2xs font-medium text-accent">HEX</span>
                  {/if}
                  {#if entry.producesCfw}
                    <span class="rounded-full bg-warning-muted px-2 py-0.5 text-2xs font-medium text-warning">CFW</span>
                  {/if}
                </div>
              </td>
              <td class="px-4 py-2">
                <span class="font-mono text-2xs text-text-tertiary">{entry.gitRef}</span>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
