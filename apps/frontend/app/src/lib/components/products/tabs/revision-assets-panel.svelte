<script lang="ts">
  import { onMount } from 'svelte';
  import {
    Package, ChevronDown, ChevronRight, Upload, Download,
    FileCode, Loader2, Radio, Cpu,
  } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import TimeDisplay from '$lib/components/ui/time-display.svelte';
  import { apiFetch, apiUpload } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { BoardRevision, AssetSet, AssetFile } from '$lib/types/models';
  import type { ProductStageConfig, StageType } from '$lib/types/stages';
  import { stageName } from '$lib/types/stages';

  interface Props {
    productId: string;
    revision: BoardRevision;
    stageConfigs: ProductStageConfig[];
    canManage: boolean;
  }

  let { productId, revision, stageConfigs, canManage }: Props = $props();

  let assetSets = $state<AssetSet[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let expandedId = $state<string | null>(null);

  // Upload state
  let uploadingStageConfigId = $state<string | null>(null);
  let uploadVersion = $state('');
  let uploadVariant = $state('debug');
  let uploadError = $state<string | null>(null);
  let uploading = $state(false);

  // Modem upload state
  let modemVersion = $state('');
  let modemUploading = $state(false);

  // Stage configs for this revision
  const revConfigs = $derived(
    stageConfigs.filter(c => c.boardRevisionId === revision.id)
  );

  // Group asset sets by stage config
  function assetsForConfig(configId: string): AssetSet[] {
    return assetSets
      .filter(a => a.stageConfigId === configId)
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  }

  // Ungrouped asset sets (from builds or legacy, no stageConfigId)
  const ungroupedAssets = $derived(
    assetSets.filter(a => !a.stageConfigId)
  );

  async function loadAssets() {
    loading = true;
    error = null;
    try {
      const res = await apiFetch<ApiResponse<{ data: AssetSet[] }>>(
        `/v2/products/${productId}/asset-sets?boardRevisionId=${revision.id}&limit=100`
      );
      const data = res.data;
      assetSets = Array.isArray(data) ? data : (data as any)?.data ?? [];
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load assets';
    } finally {
      loading = false;
    }
  }

  async function handleZipUpload(stageConfigId: string, e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    if (!uploadVersion.trim()) {
      uploadError = 'Version is required';
      return;
    }

    uploading = true;
    uploadError = null;
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('stageConfigId', stageConfigId);
      formData.append('version', uploadVersion.trim());
      formData.append('variant', uploadVariant);

      await apiUpload(`/v2/products/${productId}/asset-sets/upload-zip`, formData);
      uploadingStageConfigId = null;
      uploadVersion = '';
      await loadAssets();
    } catch (e) {
      uploadError = e instanceof Error ? e.message : 'Upload failed';
    } finally {
      uploading = false;
      input.value = '';
    }
  }

  async function handleModemUpload(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file || !modemVersion.trim()) return;

    modemUploading = true;
    error = null;
    try {
      const boardId = revision.boardId;
      const formData = new FormData();
      formData.append('file', file);
      formData.append('version', modemVersion.trim());
      await apiUpload(
        `/v2/products/${productId}/boards/${boardId}/revisions/${revision.id}/modem-firmware`,
        formData
      );
      modemVersion = '';
      // Trigger parent refresh to update revision data
      window.dispatchEvent(new CustomEvent('concord:refresh'));
    } catch (e) {
      error = e instanceof Error ? e.message : 'Modem upload failed';
    } finally {
      modemUploading = false;
      input.value = '';
    }
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  }

  onMount(() => { loadAssets(); });
</script>

<div class="space-y-6">
  <!-- Modem Firmware -->
  <div class="rounded-lg border border-border overflow-hidden">
    <div class="flex items-center gap-3 px-4 py-3 bg-surface-0/50">
      <Radio size={16} class="text-text-tertiary" />
      <span class="text-sm font-semibold text-text-primary">Modem Firmware</span>
      {#if revision.modemVersion}
        <span class="text-2xs text-text-tertiary">v{revision.modemVersion}</span>
        <StatusBadge status="ACTIVE" />
      {/if}
    </div>
    <div class="px-4 py-3 border-t border-border-subtle">
      {#if revision.hasModemFirmware && revision.modemVersion}
        <div class="flex items-center gap-3">
          <Cpu size={14} class="text-text-tertiary" />
          <span class="text-sm text-text-primary">v{revision.modemVersion}</span>
          <span class="text-2xs text-text-tertiary">Uploaded</span>
          {#if canManage}
            <div class="ml-auto flex items-center gap-2">
              <input
                type="text"
                bind:value={modemVersion}
                placeholder="New version"
                class="w-24 rounded border border-border bg-surface-0 px-2 py-1 text-2xs text-text-primary"
              />
              <label class="flex items-center gap-1.5 rounded-lg border border-accent/30 bg-accent-muted px-2.5 py-1 text-2xs font-medium text-accent hover:bg-accent/15 cursor-pointer transition-colors">
                <Upload size={12} /> Replace
                <input type="file" accept=".zip" class="hidden" onchange={handleModemUpload} disabled={modemUploading || !modemVersion.trim()} />
              </label>
            </div>
          {/if}
        </div>
      {:else}
        <div class="flex items-center gap-3">
          <span class="text-2xs text-text-tertiary">No modem firmware uploaded</span>
          {#if canManage}
            <div class="ml-auto flex items-center gap-2">
              <input
                type="text"
                bind:value={modemVersion}
                placeholder="Version"
                class="w-24 rounded border border-border bg-surface-0 px-2 py-1 text-2xs text-text-primary"
              />
              <label class="flex items-center gap-1.5 rounded-lg border border-accent/30 bg-accent-muted px-2.5 py-1 text-2xs font-medium text-accent hover:bg-accent/15 cursor-pointer transition-colors">
                <Upload size={12} /> Upload .zip
                <input type="file" accept=".zip" class="hidden" onchange={handleModemUpload} disabled={modemUploading || !modemVersion.trim()} />
              </label>
            </div>
          {/if}
        </div>
      {/if}
    </div>
  </div>

  <!-- Stage assets — one section per stage config -->
  {#if revConfigs.length === 0 && !loading}
    <div class="text-center py-6 text-2xs text-text-tertiary">
      No stages configured for this revision. Enable validation or manufacturing first.
    </div>
  {/if}

  {#each revConfigs as config}
    {@const stageAssets = assetsForConfig(config.id)}
    {@const latest = stageAssets[0]}
    {@const typeLabel = stageName(config.type as StageType, config.stage)}

    <div class="rounded-lg border border-border overflow-hidden">
      <!-- Stage header -->
      <div class="flex items-center gap-3 px-4 py-3 bg-surface-0/50">
        <div class="w-6 h-6 flex items-center justify-center rounded text-2xs font-bold shrink-0
          {config.enabled ? 'bg-accent text-white' : 'bg-surface-2 text-text-tertiary'}">
          {config.type === 'MANUFACTURING' ? 'M' : config.stage}
        </div>
        <span class="text-sm font-semibold text-text-primary">{typeLabel}</span>
        {#if latest}
          <span class="text-2xs text-text-tertiary">v{latest.version} · {latest.variant}</span>
          <StatusBadge status={latest.status} />
          <StatusBadge status={latest.source} />
          <span class="text-2xs text-text-tertiary">{latest.assets?.length ?? 0} files</span>
        {:else}
          <span class="text-2xs text-text-tertiary">No assets</span>
        {/if}

        {#if canManage}
          <div class="ml-auto">
            {#if uploadingStageConfigId === config.id}
              <div class="flex items-center gap-2">
                <input
                  type="text"
                  bind:value={uploadVersion}
                  placeholder="Version"
                  class="w-20 rounded border border-border bg-surface-0 px-2 py-1 text-2xs text-text-primary"
                />
                <select bind:value={uploadVariant} class="rounded border border-border bg-surface-0 px-2 py-1 text-2xs text-text-primary">
                  <option value="debug">debug</option>
                  <option value="release">release</option>
                  <option value="mfg">mfg</option>
                </select>
                <label class="flex items-center gap-1 rounded-lg bg-accent px-2.5 py-1 text-2xs font-medium text-white hover:bg-accent-hover cursor-pointer transition-colors">
                  {#if uploading}<Loader2 size={12} class="animate-spin" />{:else}<Upload size={12} />{/if}
                  .zip
                  <input type="file" accept=".zip" class="hidden" onchange={(e) => handleZipUpload(config.id, e)} disabled={uploading} />
                </label>
                <button onclick={() => { uploadingStageConfigId = null; uploadError = null; }} class="text-2xs text-text-tertiary hover:text-text-secondary">Cancel</button>
              </div>
            {:else}
              <button
                onclick={() => { uploadingStageConfigId = config.id; uploadVersion = ''; uploadError = null; }}
                class="flex items-center gap-1 rounded-lg border border-accent/30 bg-accent-muted px-2.5 py-1 text-2xs font-medium text-accent hover:bg-accent/15 transition-colors"
              >
                <Upload size={12} /> Upload
              </button>
            {/if}
          </div>
        {/if}
      </div>

      {#if uploadError && uploadingStageConfigId === config.id}
        <div class="px-4 py-2 border-t border-error/20 bg-error-muted text-2xs text-error">{uploadError}</div>
      {/if}

      <!-- Asset set list -->
      {#if stageAssets.length > 0}
        <div class="divide-y divide-border-subtle">
          {#each stageAssets as asset}
            <div>
              <button
                onclick={() => expandedId = expandedId === asset.id ? null : asset.id}
                class="w-full flex items-center gap-3 px-4 py-2 hover:bg-surface-0/50 transition-colors text-left"
              >
                {#if expandedId === asset.id}
                  <ChevronDown size={12} class="text-text-tertiary" />
                {:else}
                  <ChevronRight size={12} class="text-text-tertiary" />
                {/if}
                <span class="font-mono text-2xs font-medium text-text-primary">v{asset.version}</span>
                <span class="text-2xs text-text-tertiary">{asset.variant}</span>
                <StatusBadge status={asset.source} />
                {#if asset.commitSha}
                  <span class="font-mono text-2xs text-text-tertiary">{asset.commitSha.slice(0, 7)}</span>
                {/if}
                <div class="flex-1"></div>
                <span class="text-2xs text-text-tertiary">{asset.assets?.length ?? 0} files</span>
                <TimeDisplay datetime={asset.createdAt} />
              </button>

              {#if expandedId === asset.id && asset.assets?.length}
                <div class="border-t border-border-subtle bg-surface-0/30 px-4 py-2">
                  <table class="w-full text-2xs">
                    <thead>
                      <tr class="border-b border-border-subtle">
                        <th class="pb-1 text-left font-medium uppercase tracking-wider text-text-tertiary">Label</th>
                        <th class="pb-1 text-left font-medium uppercase tracking-wider text-text-tertiary">Role</th>
                        <th class="pb-1 text-left font-medium uppercase tracking-wider text-text-tertiary">Type</th>
                        <th class="pb-1 text-left font-medium uppercase tracking-wider text-text-tertiary">File</th>
                        <th class="pb-1 text-right font-medium uppercase tracking-wider text-text-tertiary">Size</th>
                      </tr>
                    </thead>
                    <tbody>
                      {#each asset.assets as file}
                        <tr class="border-b border-border-subtle last:border-b-0">
                          <td class="py-1">
                            <div class="flex items-center gap-1">
                              <FileCode size={10} class="text-text-tertiary" />
                              <span class="font-medium text-text-primary">{file.label}</span>
                            </div>
                          </td>
                          <td class="py-1 text-text-secondary">{file.role}{#if file.processor} <span class="text-text-tertiary">({file.processor})</span>{/if}</td>
                          <td class="py-1"><span class="rounded-full bg-surface-2 px-1.5 py-0.5 text-text-secondary">{file.artifactType}</span></td>
                          <td class="py-1 font-mono text-text-tertiary truncate max-w-[180px]" title={file.filename}>{file.filename}</td>
                          <td class="py-1 text-right text-text-tertiary">{formatSize(file.sizeBytes)}</td>
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/each}

  <!-- Ungrouped assets (from builds or legacy) -->
  {#if ungroupedAssets.length > 0}
    <div class="rounded-lg border border-border overflow-hidden">
      <div class="flex items-center gap-3 px-4 py-3 bg-surface-0/50">
        <Package size={16} class="text-text-tertiary" />
        <span class="text-sm font-semibold text-text-primary">Other Assets</span>
        <span class="text-2xs text-text-tertiary">{ungroupedAssets.length} set{ungroupedAssets.length === 1 ? '' : 's'}</span>
      </div>
      <div class="divide-y divide-border-subtle">
        {#each ungroupedAssets as asset}
          <button
            onclick={() => expandedId = expandedId === asset.id ? null : asset.id}
            class="w-full flex items-center gap-3 px-4 py-2 hover:bg-surface-0/50 transition-colors text-left"
          >
            <span class="font-mono text-2xs font-medium text-text-primary">v{asset.version}</span>
            <StatusBadge status={asset.source} />
            <StatusBadge status={asset.status} />
            <div class="flex-1"></div>
            <span class="text-2xs text-text-tertiary">{asset.assets?.length ?? 0} files</span>
            <TimeDisplay datetime={asset.createdAt} />
          </button>
        {/each}
      </div>
    </div>
  {/if}

  {#if loading}
    <div class="flex items-center gap-2 justify-center py-6 text-2xs text-text-tertiary">
      <Loader2 size={14} class="animate-spin" /> Loading assets...
    </div>
  {/if}
</div>
