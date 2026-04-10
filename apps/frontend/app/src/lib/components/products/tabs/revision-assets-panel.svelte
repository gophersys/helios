<script lang="ts">
  import { onMount } from 'svelte';
  import {
    Package, ChevronDown, ChevronRight, Upload, Download,
    FileCode, Loader2, Radio, Cpu, Trash2,
  } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import TimeDisplay from '$lib/components/ui/time-display.svelte';
  import ConfirmDeleteDialog from '$lib/components/ui/confirm-delete-dialog.svelte';
  import { api, apiFetch, apiUpload, apiDownload } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { BoardRevision, AssetSet, AssetFile } from '$lib/types/models';
  import type { ProductStageConfig, StageType } from '$lib/types/stages';
  import { stageName } from '$lib/types/stages';

  interface Props {
    productId: string;
    revision: BoardRevision;
    stageConfigs: ProductStageConfig[];
    canManage: boolean;
    onRefresh?: () => void;
  }

  let { productId, revision, stageConfigs, canManage, onRefresh }: Props = $props();

  let assetSets = $state<AssetSet[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let expandedId = $state<string | null>(null);

  // Upload state
  let uploadError = $state<string | null>(null);
  let uploadingConfigId = $state<string | null>(null);

  // Modem upload state
  let modemVersion = $state('');
  let modemUploading = $state(false);
  let showModemUpload = $state(false);

  // Delete state
  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  // Stage configs for this revision
  const revConfigs = $derived(
    stageConfigs.filter(c => c.boardRevisionId === revision.id)
  );

  // Group asset sets by stage config — includes backward compat for pre-fix build assets
  function assetsForConfig(config: ProductStageConfig): AssetSet[] {
    return assetSets
      .filter(a =>
        a.stageConfigId === config.id ||
        // Backward compat: build-service assets without stageConfigId but matching stage number
        (a.source === 'BUILD_SERVICE' && !a.stageConfigId && a.stage === config.stage)
      )
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  }

  // Ungrouped: no stageConfigId AND not matched by backward compat
  const groupedConfigIds = $derived(new Set(revConfigs.map(c => c.id)));
  const ungroupedAssets = $derived(
    assetSets.filter(a => {
      if (a.stageConfigId && groupedConfigIds.has(a.stageConfigId)) return false;
      if (a.source === 'BUILD_SERVICE' && !a.stageConfigId) {
        return !revConfigs.some(c => c.stage === a.stage);
      }
      return !a.stageConfigId;
    })
  );

  function sourceLabel(source: string): string {
    switch (source) {
      case 'BUILD_SERVICE': return 'Concord Build';
      case 'MANUAL_UPLOAD': return 'Manual';
      case 'EXTERNAL_CI': return 'External CI';
      default: return source;
    }
  }

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

    uploadingConfigId = stageConfigId;
    uploadError = null;
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('stageConfigId', stageConfigId);
      formData.append('version', 'auto');
      formData.append('variant', 'debug');

      await apiUpload(`/v2/products/${productId}/asset-sets/upload-zip`, formData);
      await loadAssets();
      onRefresh?.();
    } catch (e) {
      uploadError = e instanceof Error ? e.message : 'Upload failed';
    } finally {
      uploadingConfigId = null;
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
      onRefresh?.();
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

  async function handleDeleteAssetSet(id: string) {
    error = null;
    try {
      await api.delete(`/v2/asset-sets/${id}`);
      await loadAssets();
      onRefresh?.();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to delete asset set';
    }
  }

  async function handleDownloadFile(file: AssetFile) {
    if (!file.storageKey) return;
    try {
      await apiDownload(`/v2/storage/download?key=${encodeURIComponent(file.storageKey)}`, file.filename);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Download failed';
    }
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
      <div class="flex items-center gap-3">
        {#if revision.hasModemFirmware && revision.modemVersion}
          <Cpu size={14} class="text-text-tertiary" />
          <span class="text-sm text-text-primary">v{revision.modemVersion}</span>
        {:else}
          <span class="text-2xs text-text-tertiary">No modem firmware uploaded</span>
        {/if}

        {#if canManage}
          <div class="ml-auto">
            {#if showModemUpload}
              <div class="flex items-center gap-2">
                <input
                  type="text"
                  bind:value={modemVersion}
                  placeholder="Version (e.g. 2.0.2)"
                  class="w-36 rounded border border-border bg-surface-0 px-2 py-1 text-2xs text-text-primary"
                />
                <label class="flex items-center gap-1 rounded-lg bg-accent px-2.5 py-1 text-2xs font-medium text-white hover:bg-accent-hover cursor-pointer transition-colors {!modemVersion.trim() ? 'opacity-50 pointer-events-none' : ''}">
                  {#if modemUploading}<Loader2 size={12} class="animate-spin" />{:else}<Upload size={12} />{/if}
                  Select .zip
                  <input type="file" accept=".zip" class="hidden" onchange={handleModemUpload} disabled={modemUploading || !modemVersion.trim()} />
                </label>
                <button onclick={() => { showModemUpload = false; modemVersion = ''; }} class="text-2xs text-text-tertiary hover:text-text-secondary">Cancel</button>
              </div>
            {:else}
              <button
                onclick={() => showModemUpload = true}
                class="flex items-center gap-1 rounded-lg border border-accent/30 bg-accent-muted px-2.5 py-1 text-2xs font-medium text-accent hover:bg-accent/15 transition-colors"
              >
                <Upload size={12} /> {revision.hasModemFirmware ? 'Replace' : 'Upload'}
              </button>
            {/if}
          </div>
        {/if}
      </div>
    </div>
  </div>

  <!-- Stage assets — one section per stage config -->
  {#if revConfigs.length === 0 && !loading}
    <div class="text-center py-6 text-2xs text-text-tertiary">
      No stages configured for this revision. Enable validation or manufacturing first.
    </div>
  {/if}

  {#each revConfigs as config}
    {@const stageAssets = assetsForConfig(config)}
    {@const latest = stageAssets[0]}
    {@const completeness = (latest as any)?.completeness}
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
          <span class="rounded-full px-1.5 py-0.5 text-2xs font-medium
            {latest.source === 'BUILD_SERVICE' ? 'bg-accent-muted text-accent' : latest.source === 'EXTERNAL_CI' ? 'bg-blue-500/10 text-blue-400' : 'bg-surface-2 text-text-secondary'}">
            {sourceLabel(latest.source)}
          </span>
          {#if completeness}
            <span class="rounded-full px-1.5 py-0.5 text-2xs font-medium
              {completeness.complete ? 'bg-success-muted text-success' : 'bg-warning-muted text-warning'}">
              {completeness.present}/{completeness.required} labels
            </span>
          {/if}
          <span class="text-2xs text-text-tertiary">{latest.assets?.length ?? 0} files</span>
        {:else}
          <span class="text-2xs text-text-tertiary">No assets</span>
        {/if}

        {#if canManage}
          <div class="ml-auto">
            <label class="flex items-center gap-1 rounded-lg border border-accent/30 bg-accent-muted px-2.5 py-1 text-2xs font-medium text-accent hover:bg-accent/15 cursor-pointer transition-colors {uploadingConfigId === config.id ? 'opacity-50 pointer-events-none' : ''}">
              {#if uploadingConfigId === config.id}<Loader2 size={12} class="animate-spin" />{:else}<Upload size={12} />{/if}
              Upload .zip
              <input type="file" accept=".zip" class="hidden" onchange={(e) => handleZipUpload(config.id, e)} disabled={uploadingConfigId === config.id} />
            </label>
          </div>
        {/if}
      </div>

      {#if uploadError && uploadingConfigId === config.id}
        <div class="px-4 py-2 border-t border-error/20 bg-error-muted text-2xs text-error">{uploadError}</div>
      {/if}

      <!-- Asset set list -->
      {#if stageAssets.length > 0}
        <div class="divide-y divide-border-subtle">
          {#each stageAssets as asset}
            <div>
              <div class="flex items-center">
                <button
                  onclick={() => expandedId = expandedId === asset.id ? null : asset.id}
                  class="flex-1 flex items-center gap-3 px-4 py-2 hover:bg-surface-0/50 transition-colors text-left"
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
                {#if canManage}
                  <button
                    onclick={() => deleteTarget = { id: asset.id, name: `${asset.version} (${asset.variant})` }}
                    class="flex items-center justify-center rounded-lg p-1.5 mr-2 text-text-tertiary hover:bg-error-muted hover:text-error transition-colors"
                    title="Delete asset set"
                  >
                    <Trash2 size={12} />
                  </button>
                {/if}
              </div>

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
                        <th class="pb-1 w-8"></th>
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
                          <td class="py-1 text-right">
                            {#if file.storageKey}
                              <button
                                onclick={() => handleDownloadFile(file)}
                                class="inline-flex items-center justify-center rounded p-0.5 text-text-tertiary hover:text-accent transition-colors"
                                title="Download {file.filename}"
                              >
                                <Download size={10} />
                              </button>
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

<ConfirmDeleteDialog
  open={!!deleteTarget}
  entityType="asset set"
  entityName={deleteTarget?.name || ''}
  onConfirm={() => { handleDeleteAssetSet(deleteTarget!.id); deleteTarget = null; }}
  onCancel={() => (deleteTarget = null)}
/>
