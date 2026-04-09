<script lang="ts">
  import { onMount } from 'svelte';
  import {
    Package, ChevronDown, ChevronRight, Download, Loader2, FileCode,
  } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import TimeDisplay from '$lib/components/ui/time-display.svelte';

  import { apiFetch } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { AssetSet } from '$lib/types/models';
  import { STAGE_NAMES } from '$lib/types/stages';

  interface Props {
    productId: string;
    canManage: boolean;
  }

  let { productId, canManage }: Props = $props();

  let assetSets = $state<AssetSet[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let expandedId = $state<string | null>(null);

  // Group asset sets by stage
  const groupedByStage = $derived.by(() => {
    const groups: Record<string, AssetSet[]> = {};
    for (const a of assetSets) {
      const key = a.stage != null ? `Stage ${a.stage}: ${STAGE_NAMES[a.stage] ?? 'Unknown'}` : 'Unassigned';
      if (!groups[key]) groups[key] = [];
      groups[key].push(a);
    }
    return groups;
  });

  const stageKeys = $derived(Object.keys(groupedByStage).sort());

  async function loadAssetSets() {
    loading = true;
    error = null;
    try {
      const res = await apiFetch<ApiResponse<{ data: AssetSet[]; pagination: any }>>(
        `/v2/products/${productId}/asset-sets?limit=100`
      );
      const data = res.data;
      assetSets = Array.isArray(data) ? data : (data as any)?.data ?? [];
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load asset sets';
    } finally {
      loading = false;
    }
  }

  function toggleExpand(id: string) {
    expandedId = expandedId === id ? null : id;
  }

  function formatSourceLabel(source: string): string {
    switch (source) {
      case 'BUILD_SERVICE': return 'Build Service';
      case 'MANUAL_UPLOAD': return 'Manual';
      case 'EXTERNAL_CI': return 'External CI';
      default: return source;
    }
  }

  onMount(() => { loadAssetSets(); });
</script>

<!-- Asset Sets section -->
<div class="mb-8">
  <div class="flex items-center justify-between mb-4">
    <div class="flex items-center gap-2">
      <Package size={16} class="text-accent" />
      <h3 class="text-sm font-semibold text-text-primary">Asset Sets</h3>
      {#if !loading}
        <span class="text-2xs text-text-tertiary">{assetSets.length} total</span>
      {/if}
    </div>
  </div>

  {#if error}
    <div class="rounded-lg border border-error/20 bg-error-muted px-4 py-2.5 text-sm text-error mb-3">{error}</div>
  {/if}

  {#if loading}
    <div class="rounded-lg border border-border bg-surface-0 p-6 text-center">
      <Loader2 size={20} class="animate-spin mx-auto text-text-tertiary" />
    </div>
  {:else if assetSets.length === 0}
    <div class="rounded-lg border border-dashed border-border bg-surface-0 p-6 text-center">
      <Package size={24} class="mx-auto mb-2 text-text-tertiary opacity-30" />
      <p class="text-sm text-text-secondary">No asset sets yet</p>
      <p class="text-2xs text-text-tertiary mt-1">Asset sets appear here when builds complete, or when firmware is uploaded manually.</p>
    </div>
  {:else}
    <div class="space-y-4">
      {#each stageKeys as stageKey}
        <div>
          <h4 class="text-2xs font-medium uppercase tracking-wider text-text-tertiary mb-2">{stageKey}</h4>
          <div class="rounded-lg border border-border overflow-hidden">
            {#each groupedByStage[stageKey] as asset}
              <!-- Asset set row -->
              <div class="border-b border-border-subtle last:border-b-0">
                <button
                  onclick={() => toggleExpand(asset.id)}
                  class="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-surface-0/50 transition-colors text-left"
                >
                  {#if expandedId === asset.id}
                    <ChevronDown size={14} class="text-text-tertiary shrink-0" />
                  {:else}
                    <ChevronRight size={14} class="text-text-tertiary shrink-0" />
                  {/if}

                  <span class="font-mono text-sm font-medium text-text-primary">v{asset.version}</span>
                  <span class="text-2xs text-text-tertiary">{asset.variant}</span>

                  <StatusBadge status={asset.source} />
                  <StatusBadge status={asset.status} />

                  <div class="flex-1"></div>

                  <span class="text-2xs text-text-tertiary">
                    {asset.assets?.length ?? 0} file{(asset.assets?.length ?? 0) === 1 ? '' : 's'}
                  </span>

                  {#if asset.commitSha}
                    <span class="font-mono text-2xs text-text-tertiary" title={asset.commitSha}>
                      {asset.commitSha.slice(0, 7)}
                    </span>
                  {/if}

                  <TimeDisplay datetime={asset.createdAt} />
                </button>

                <!-- Expanded: individual assets -->
                {#if expandedId === asset.id && asset.assets?.length}
                  <div class="border-t border-border-subtle bg-surface-0/30 px-4 py-3">
                    {#if asset.branch}
                      <div class="flex items-center gap-2 mb-2 text-2xs text-text-tertiary">
                        <span>Branch:</span>
                        <span class="font-mono text-text-secondary">{asset.branch}</span>
                      </div>
                    {/if}
                    {#if asset.notes}
                      <p class="text-2xs text-text-secondary mb-2">{asset.notes}</p>
                    {/if}
                    <table class="w-full text-sm">
                      <thead>
                        <tr class="border-b border-border-subtle">
                          <th class="pb-1.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Label</th>
                          <th class="pb-1.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Role</th>
                          <th class="pb-1.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Type</th>
                          <th class="pb-1.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">File</th>
                          <th class="pb-1.5 text-right text-2xs font-medium uppercase tracking-wider text-text-tertiary">Size</th>
                        </tr>
                      </thead>
                      <tbody>
                        {#each asset.assets as file}
                          <tr class="border-b border-border-subtle last:border-b-0">
                            <td class="py-1.5">
                              <div class="flex items-center gap-1.5">
                                <FileCode size={12} class="text-text-tertiary" />
                                <span class="font-medium text-text-primary">{file.label}</span>
                              </div>
                            </td>
                            <td class="py-1.5 text-text-secondary">
                              {file.role}
                              {#if file.processor}
                                <span class="text-2xs text-text-tertiary">({file.processor})</span>
                              {/if}
                            </td>
                            <td class="py-1.5">
                              <span class="rounded-full bg-surface-2 px-2 py-0.5 text-2xs font-medium text-text-secondary">{file.artifactType}</span>
                            </td>
                            <td class="py-1.5 font-mono text-2xs text-text-tertiary truncate max-w-[200px]" title={file.filename}>
                              {file.filename}
                            </td>
                            <td class="py-1.5 text-right text-2xs text-text-tertiary whitespace-nowrap">
                              {#if file.sizeBytes < 1024}
                                {file.sizeBytes} B
                              {:else if file.sizeBytes < 1048576}
                                {(file.sizeBytes / 1024).toFixed(1)} KB
                              {:else}
                                {(file.sizeBytes / 1048576).toFixed(1)} MB
                              {/if}
                            </td>
                          </tr>
                        {/each}
                      </tbody>
                    </table>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
