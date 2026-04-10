<script lang="ts">
  import { onMount } from 'svelte';
  import {
    Package, ChevronDown, ChevronRight, Upload, Download,
    FileCode, Loader2, Radio, Cpu, Trash2, Search, X,
  } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import TimeDisplay from '$lib/components/ui/time-display.svelte';
  import ConfirmDeleteDialog from '$lib/components/ui/confirm-delete-dialog.svelte';
  import AssetUploadWizard from '$lib/components/products/asset-upload-wizard.svelte';
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

  // Search & filter state
  let searchQuery = $state('');
  let filterSource = $state<string | null>(null);
  let filterStatus = $state<string | null>(null);
  let filterStageConfigId = $state<string | null>(null);

  // Upload wizard state
  let showUploadWizard = $state(false);

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

  // Filter asset sets by search query + smart filters (AND logic)
  function matchesFilters(asset: AssetSet): boolean {
    // Text search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const textMatch =
        (asset.version?.toLowerCase().includes(q)) ||
        (asset.variant?.toLowerCase().includes(q)) ||
        (asset.status?.toLowerCase().includes(q)) ||
        (asset.commitSha?.toLowerCase().includes(q)) ||
        (asset.branch?.toLowerCase().includes(q)) ||
        false;
      if (!textMatch) return false;
    }
    // Source filter
    if (filterSource && asset.source !== filterSource) return false;
    // Status filter
    if (filterStatus && asset.status !== filterStatus) return false;
    // Stage filter
    if (filterStageConfigId) {
      const matchesStage = asset.stageConfigId === filterStageConfigId ||
        (asset.source === 'BUILD_SERVICE' && !asset.stageConfigId &&
          revConfigs.some(c => c.id === filterStageConfigId && c.stage === asset.stage));
      if (!matchesStage) return false;
    }
    return true;
  }

  const filteredAssetSets = $derived(assetSets.filter(matchesFilters));

  // Derive available filter options from actual data
  const availableSources = $derived(
    [...new Set(assetSets.map(a => a.source))].sort()
  );
  const availableStatuses = $derived(
    [...new Set(assetSets.map(a => a.status))].sort()
  );
  const availableStageConfigs = $derived(
    revConfigs.filter(c => assetSets.some(a =>
      a.stageConfigId === c.id ||
      (a.source === 'BUILD_SERVICE' && !a.stageConfigId && a.stage === c.stage)
    ))
  );
  const hasActiveFilters = $derived(
    !!filterSource || !!filterStatus || !!filterStageConfigId || !!searchQuery.trim()
  );

  function toggleFilter(type: 'source' | 'status' | 'stage', value: string) {
    if (type === 'source') {
      filterSource = filterSource === value ? null : value;
    } else if (type === 'status') {
      filterStatus = filterStatus === value ? null : value;
    } else if (type === 'stage') {
      filterStageConfigId = filterStageConfigId === value ? null : value;
    }
  }

  function clearFilters() {
    filterSource = null;
    filterStatus = null;
    filterStageConfigId = null;
    searchQuery = '';
  }

  // Group asset sets by stage config — includes backward compat for pre-fix build assets
  function assetsForConfig(config: ProductStageConfig): AssetSet[] {
    return filteredAssetSets
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
    filteredAssetSets.filter(a => {
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

  function sourceBadgeClass(source: string): string {
    switch (source) {
      case 'BUILD_SERVICE': return 'bg-accent-muted text-accent';
      case 'MANUAL_UPLOAD': return 'bg-warning-muted text-warning';
      case 'EXTERNAL_CI': return 'bg-blue-500/10 text-blue-400';
      default: return 'bg-surface-2 text-text-secondary';
    }
  }

  function statusBadgeClass(status: string): string {
    switch (status) {
      case 'PENDING': return 'bg-warning-muted text-warning';
      case 'COMPLETE': return 'bg-success-muted text-success';
      case 'VALIDATED': return 'bg-blue-500/10 text-blue-400';
      case 'FAILED': return 'bg-error-muted text-error';
      default: return 'bg-surface-2 text-text-secondary';
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

  <!-- Filter bar and upload controls -->
  {#if !loading}
    <div class="space-y-2">
      <div class="flex items-center gap-3">
        <div class="flex-1 flex flex-wrap items-center gap-2">
          <!-- Source filters -->
          {#each availableSources as source}
            <button
              onclick={() => toggleFilter('source', source)}
              class="text-2xs px-2 py-1 rounded-full border transition-colors
                {filterSource === source
                  ? 'bg-accent text-white border-accent'
                  : 'border-border text-text-tertiary hover:text-text-secondary hover:border-border'}"
            >
              {sourceLabel(source)}
            </button>
          {/each}

          <!-- Status filters -->
          {#each availableStatuses as status}
            <button
              onclick={() => toggleFilter('status', status)}
              class="text-2xs px-2 py-1 rounded-full border transition-colors
                {filterStatus === status
                  ? 'bg-accent text-white border-accent'
                  : 'border-border text-text-tertiary hover:text-text-secondary hover:border-border'}"
            >
              {status}
            </button>
          {/each}

          <!-- Stage filters -->
          {#each availableStageConfigs as config}
            <button
              onclick={() => toggleFilter('stage', config.id)}
              class="text-2xs px-2 py-1 rounded-full border transition-colors
                {filterStageConfigId === config.id
                  ? 'bg-accent text-white border-accent'
                  : 'border-border text-text-tertiary hover:text-text-secondary hover:border-border'}"
            >
              {stageName(config.type as StageType, config.stage)}
            </button>
          {/each}

          <!-- Text search -->
          <div class="relative">
            <Search size={12} class="absolute left-2 top-1/2 -translate-y-1/2 text-text-tertiary" />
            <input
              type="text"
              bind:value={searchQuery}
              placeholder="Search..."
              class="text-2xs pl-6 pr-2 py-1 rounded-full border border-border bg-surface-0 w-32 text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
            />
          </div>

          <!-- Clear filters -->
          {#if hasActiveFilters}
            <button
              onclick={clearFilters}
              class="flex items-center gap-1 text-2xs text-accent hover:underline"
            >
              <X size={10} />
              Clear
            </button>
          {/if}
        </div>

        <!-- Upload button -->
        {#if canManage}
          <button
            onclick={() => showUploadWizard = true}
            class="flex items-center gap-1 rounded-lg border border-accent/30 bg-accent-muted px-3 py-2 text-sm font-medium text-accent hover:bg-accent/15 transition-colors shrink-0"
          >
            <Upload size={14} />
            Upload .zip
          </button>
        {/if}
      </div>
    </div>
  {/if}

  <!-- Stage assets — one section per stage config -->
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
          <span class="rounded-full px-1.5 py-0.5 text-2xs font-medium {sourceBadgeClass(latest.source)}">
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

      </div>

      <!-- Asset set list -->
      {#if stageAssets.length > 0}
        <div class="divide-y divide-border-subtle">
          {#each stageAssets as asset}
            {@const assetTitle = `v${asset.version}${asset.variant ? ` (${asset.variant})` : ''}`}
            <div>
              <div class="flex items-center">
                <button
                  onclick={() => expandedId = expandedId === asset.id ? null : asset.id}
                  class="flex-1 flex items-center gap-3 px-4 py-2.5 hover:bg-surface-0/50 transition-colors text-left"
                >
                  {#if expandedId === asset.id}
                    <ChevronDown size={12} class="text-text-tertiary shrink-0" />
                  {:else}
                    <ChevronRight size={12} class="text-text-tertiary shrink-0" />
                  {/if}
                  <span class="font-mono text-2xs font-semibold text-text-primary">{assetTitle}</span>
                  <span class="rounded-full px-1.5 py-0.5 text-2xs font-medium {sourceBadgeClass(asset.source)}">{sourceLabel(asset.source)}</span>
                  <span class="rounded-full px-1.5 py-0.5 text-2xs font-medium {statusBadgeClass(asset.status)}">{asset.status}</span>
                  {#if asset.commitSha}
                    <span class="font-mono text-2xs text-text-tertiary">{asset.commitSha.slice(0, 7)}</span>
                  {/if}
                  {#if asset.branch}
                    <span class="text-2xs text-text-tertiary truncate max-w-[120px]" title={asset.branch}>{asset.branch}</span>
                  {/if}
                  <div class="flex-1"></div>
                  <span class="text-2xs text-text-tertiary shrink-0">{asset.assets?.length ?? 0} files</span>
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

  <!-- Ungrouped assets (from builds, legacy, or when no stages configured) -->
  {#if ungroupedAssets.length > 0}
    <div class="rounded-lg border border-border overflow-hidden">
      {#if revConfigs.length > 0}
        <div class="flex items-center gap-3 px-4 py-3 bg-surface-0/50">
          <Package size={16} class="text-text-tertiary" />
          <span class="text-sm font-semibold text-text-primary">Other Assets</span>
          <span class="text-2xs text-text-tertiary">{ungroupedAssets.length} set{ungroupedAssets.length === 1 ? '' : 's'}</span>
        </div>
      {/if}
      <div class="divide-y divide-border-subtle">
        {#each ungroupedAssets as asset}
          {@const assetTitle = `v${asset.version}${asset.variant ? ` (${asset.variant})` : ''}`}
          <div>
            <div class="flex items-center">
              <button
                onclick={() => expandedId = expandedId === asset.id ? null : asset.id}
                class="flex-1 flex items-center gap-3 px-4 py-2.5 hover:bg-surface-0/50 transition-colors text-left"
              >
                {#if expandedId === asset.id}
                  <ChevronDown size={12} class="text-text-tertiary shrink-0" />
                {:else}
                  <ChevronRight size={12} class="text-text-tertiary shrink-0" />
                {/if}
                <span class="font-mono text-2xs font-semibold text-text-primary">{assetTitle}</span>
                <span class="rounded-full px-1.5 py-0.5 text-2xs font-medium {sourceBadgeClass(asset.source)}">{sourceLabel(asset.source)}</span>
                <span class="rounded-full px-1.5 py-0.5 text-2xs font-medium {statusBadgeClass(asset.status)}">{asset.status}</span>
                {#if asset.commitSha}
                  <span class="font-mono text-2xs text-text-tertiary">{asset.commitSha.slice(0, 7)}</span>
                {/if}
                {#if asset.branch}
                  <span class="text-2xs text-text-tertiary truncate max-w-[120px]" title={asset.branch}>{asset.branch}</span>
                {/if}
                <div class="flex-1"></div>
                <span class="text-2xs text-text-tertiary shrink-0">{asset.assets?.length ?? 0} files</span>
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
    </div>
  {/if}

  <!-- Empty state: no assets at all or no filter results -->
  {#if !loading && filteredAssetSets.length === 0}
    <div class="text-center py-6">
      {#if hasActiveFilters && assetSets.length > 0}
        <p class="text-sm text-text-secondary">No assets match the current filters</p>
        <p class="text-2xs text-text-tertiary mt-1">
          <button onclick={clearFilters} class="text-accent hover:underline">Clear filters</button> to see all assets.
        </p>
      {:else}
        <p class="text-sm text-text-secondary">No firmware assets for this revision</p>
        <p class="text-2xs text-text-tertiary mt-1">Upload a firmware .zip or wait for the build pipeline to produce one.</p>
      {/if}
    </div>
  {/if}

  {#if loading}
    <div class="flex items-center gap-2 justify-center py-6 text-2xs text-text-tertiary">
      <Loader2 size={14} class="animate-spin" /> Loading assets...
    </div>
  {/if}
</div>

{#if showUploadWizard}
  <AssetUploadWizard
    {productId}
    revision={{ id: revision.id, version: revision.version, ckBoardsName: revision.ckBoardsName }}
    stageConfigs={revConfigs}
    onComplete={() => { showUploadWizard = false; loadAssets(); onRefresh?.(); }}
    onCancel={() => showUploadWizard = false}
  />
{/if}

<ConfirmDeleteDialog
  open={!!deleteTarget}
  entityType="asset set"
  entityName={deleteTarget?.name || ''}
  onConfirm={() => { handleDeleteAssetSet(deleteTarget!.id); deleteTarget = null; }}
  onCancel={() => (deleteTarget = null)}
/>
