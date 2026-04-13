<script lang="ts">
  import { onMount } from 'svelte';
  import {
    Package, ChevronDown, ChevronRight, Upload, Download,
    FileCode, Loader2, Radio, Cpu, Trash2, Search,
  } from 'lucide-svelte';
  import FilterBar from '$lib/components/ui/filter-bar.svelte';
  import FilterSelect from '$lib/components/ui/filter-select.svelte';
  import FilterSearch from '$lib/components/ui/filter-search.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import TimeDisplay from '$lib/components/ui/time-display.svelte';
  import EmptyState from '$lib/components/ui/empty-state.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import ConfirmDeleteDialog from '$lib/components/ui/confirm-delete-dialog.svelte';
  import AssetUploadWizard from '$lib/components/products/asset-upload-wizard.svelte';
  import { api, apiFetch, apiUpload, apiDownload } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { BoardRevision, AssetSet, AssetFile, ModemFirmware } from '$lib/types/models';
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

  // Filters
  let searchQuery = $state('');
  let filterStage = $state('');
  let filterSource = $state('');

  // Upload wizard
  let showUploadWizard = $state(false);

  // Modem firmware
  let modemFirmwares = $state<ModemFirmware[]>([]);
  let modemVersion = $state('');
  let modemUploading = $state(false);
  let modemError = $state<string | null>(null);
  let showModemUpload = $state(false);
  let modemLoading = $state(false);

  // Delete
  let deleteTarget = $state<{ id: string; name: string } | null>(null);
  let modemDeleteTarget = $state<{ id: string; version: string } | null>(null);

  // Stage configs for this revision
  const revConfigs = $derived(
    stageConfigs.filter(c => c.boardRevisionId === revision.id)
  );

  // Stage filter options — grouped by type
  const stageOptions = $derived(
    revConfigs.map(c => ({
      value: `${c.type}:${c.stage}`,
      label: `${c.type === 'MANUFACTURING' ? 'Mfg' : 'Val'} — ${stageName(c.type as StageType, c.stage)}`,
    }))
  );

  // Source filter options
  const SOURCE_OPTIONS = [
    { value: 'BUILD_SERVICE', label: 'Concord Build' },
    { value: 'MANUAL_UPLOAD', label: 'Manual' },
    { value: 'EXTERNAL_CI', label: 'External CI' },
  ];

  // Filter logic (AND)
  const filteredAssets = $derived.by(() => {
    let result = assetSets;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(a =>
        a.version?.toLowerCase().includes(q) ||
        a.variant?.toLowerCase().includes(q) ||
        a.commitSha?.toLowerCase().includes(q) ||
        a.branch?.toLowerCase().includes(q)
      );
    }

    if (filterStage) {
      const [type, stageStr] = filterStage.split(':');
      const stageNum = parseInt(stageStr);
      result = result.filter(a => a.stage === stageNum && (a.stageType === type || a.stageType == null));
    }

    if (filterSource) {
      result = result.filter(a => a.source === filterSource);
    }

    return result.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  });

  const hasActiveFilters = $derived(
    !!searchQuery.trim() || !!filterStage || !!filterSource
  );

  // Helpers
  function sourceLabel(source: string): string {
    switch (source) {
      case 'BUILD_SERVICE': return 'Concord Build';
      case 'MANUAL_UPLOAD': return 'Manual';
      case 'EXTERNAL_CI': return 'External CI';
      default: return source;
    }
  }

  function stageLabel(asset: AssetSet): string {
    if (asset.stage == null) return '—';
    const config = revConfigs.find(c => c.stage === asset.stage && (c.type === asset.stageType || asset.stageType == null));
    if (config) return stageName(config.type as StageType, config.stage);
    return `Stage ${asset.stage}`;
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  }

  // Data loading
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

  async function loadModemFirmwares() {
    modemLoading = true;
    try {
      const res = await apiFetch<ApiResponse<ModemFirmware[]>>(
        `/v2/products/${productId}/boards/${revision.boardId}/revisions/${revision.id}/modem-firmware`
      );
      modemFirmwares = Array.isArray(res.data) ? res.data : [];
    } catch {
      modemFirmwares = [];
    } finally {
      modemLoading = false;
    }
  }

  async function handleModemUpload(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file || !modemVersion.trim()) return;

    if (!file.name.endsWith('.zip')) {
      modemError = 'Only .zip files are accepted';
      input.value = '';
      return;
    }

    modemUploading = true;
    modemError = null;
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('version', modemVersion.trim());
      await apiUpload(
        `/v2/products/${productId}/boards/${revision.boardId}/revisions/${revision.id}/modem-firmware`,
        formData
      );
      modemVersion = '';
      showModemUpload = false;
      await loadModemFirmwares();
      onRefresh?.();
    } catch (e) {
      modemError = e instanceof Error ? e.message : 'Modem upload failed';
    } finally {
      modemUploading = false;
      input.value = '';
    }
  }

  async function handleDeleteModemFirmware(fwId: string) {
    error = null;
    try {
      await api.delete(
        `/v2/products/${productId}/boards/${revision.boardId}/revisions/${revision.id}/modem-firmware/${fwId}`
      );
      await loadModemFirmwares();
      onRefresh?.();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to delete modem firmware';
    }
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

  async function handleDownloadZip(assetSetId: string, version: string, variant: string) {
    try {
      const filename = `asset-set-${version}-${variant || 'default'}.zip`;
      await apiDownload(`/v2/asset-sets/${assetSetId}/download`, filename);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Download failed';
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

  onMount(() => { loadAssets(); loadModemFirmwares(); });
</script>

{#if error}
  <div role="alert" class="mb-4 flex items-start gap-3 rounded-lg bg-error-muted px-4 py-3">
    <span class="text-sm text-error">{error}</span>
  </div>
{/if}

<div class="space-y-6">
  <!-- ═══ Modem Firmware ═══ -->
  <div class="rounded-lg border border-border overflow-hidden">
    <div class="flex items-center gap-3 px-4 py-3 bg-surface-2">
      <Radio size={16} class="text-text-tertiary" />
      <span class="text-sm font-semibold text-text-primary">Modem Firmware</span>
      <span class="text-2xs text-text-tertiary">{modemFirmwares.length} version{modemFirmwares.length === 1 ? '' : 's'}</span>
      {#if canManage}
        <div class="ml-auto">
          {#if showModemUpload}
            <div class="flex items-center gap-2">
              <input
                type="text"
                bind:value={modemVersion}
                placeholder="Version (e.g. 2.0.2)"
                class="input input-sm w-36"
              />
              <label class="btn btn-sm btn-primary cursor-pointer {!modemVersion.trim() ? 'opacity-50 pointer-events-none' : ''}">
                {#if modemUploading}<Loader2 size={12} class="animate-spin" />{:else}<Upload size={12} />{/if}
                Upload .zip
                <input type="file" accept=".zip" class="hidden" onchange={handleModemUpload} disabled={modemUploading || !modemVersion.trim()} />
              </label>
              <button onclick={() => { showModemUpload = false; modemVersion = ''; modemError = null; }} class="btn btn-sm btn-ghost">Cancel</button>
            </div>
            {#if modemError}
              <p class="text-2xs text-error mt-1">{modemError}</p>
            {/if}
          {:else}
            <button onclick={() => showModemUpload = true} class="btn btn-sm btn-primary">
              <Upload size={12} /> Upload .zip
            </button>
          {/if}
        </div>
      {/if}
    </div>
    {#if modemLoading}
      <div class="flex items-center gap-2 justify-center py-4 text-2xs text-text-tertiary border-t border-border-subtle">
        <Loader2 size={12} class="animate-spin" /> Loading...
      </div>
    {:else if modemFirmwares.length > 0}
      <div class="divide-y divide-border-subtle">
        {#each modemFirmwares as fw}
          <div class="flex items-center gap-3 px-4 py-2.5">
            <Cpu size={14} class="text-text-tertiary shrink-0" />
            <span class="font-mono text-2xs font-semibold text-text-primary">v{fw.version}</span>
            <span class="text-2xs text-text-tertiary truncate max-w-44" title={fw.filename}>{fw.filename}</span>
            <span class="text-2xs text-text-tertiary">{formatSize(fw.sizeBytes)}</span>
            <div class="flex-1"></div>
            <TimeDisplay datetime={fw.createdAt} />
            {#if canManage}
              <button
                onclick={() => modemDeleteTarget = { id: fw.id, version: fw.version }}
                class="btn btn-sm btn-icon btn-ghost text-text-tertiary hover:text-error hover:bg-error-muted"
                title="Delete v{fw.version}"
              >
                <Trash2 size={12} />
              </button>
            {/if}
          </div>
        {/each}
      </div>
    {:else}
      <div class="px-4 py-4 border-t border-border-subtle text-center">
        <Radio size={20} class="mx-auto text-text-tertiary mb-1.5 opacity-50" />
        <p class="text-2xs text-text-tertiary">No modem firmware uploaded.</p>
        <p class="text-2xs text-text-tertiary mt-0.5">Upload a modem firmware .zip to link it with asset sets.</p>
      </div>
    {/if}
  </div>

  <!-- ═══ Asset Sets — Flat Table ═══ -->
  {#if !loading}
    <FilterBar class="mb-4">
      {#snippet filters()}
        <FilterSelect
          label="Stage"
          value={filterStage}
          onchange={(v) => { filterStage = v; }}
          options={stageOptions}
        />
        <FilterSelect
          label="Source"
          value={filterSource}
          onchange={(v) => { filterSource = v; }}
          options={SOURCE_OPTIONS}
        />
        <FilterSearch bind:value={searchQuery} placeholder="Search assets..." class="w-48" />
      {/snippet}
      <span class="ml-auto text-2xs text-text-tertiary shrink-0">
        {filteredAssets.length} asset set{filteredAssets.length !== 1 ? 's' : ''}
      </span>
      {#if canManage}
        <button onclick={() => showUploadWizard = true} class="btn btn-sm btn-primary">
          <Upload size={14} /> Upload .zip
        </button>
      {/if}
    </FilterBar>
  {/if}

  {#if loading}
    <LoadingState message="Loading assets..." />
  {:else if filteredAssets.length === 0}
    {#if hasActiveFilters && assetSets.length > 0}
      <EmptyState message="No assets match your filters." icon={Search}>
        <p class="text-2xs text-text-tertiary mt-1">
          <button onclick={() => { searchQuery = ''; filterStage = ''; filterSource = ''; }} class="text-accent hover:text-accent-hover">Clear filters</button> to see all {assetSets.length} asset set{assetSets.length === 1 ? '' : 's'}.
        </p>
      </EmptyState>
    {:else}
      <EmptyState message="No assets for this revision." icon={Package}>
        <p class="text-2xs text-text-tertiary mt-1">Upload a firmware .zip or wait for a build run to produce one.</p>
      </EmptyState>
    {/if}
  {:else}
    <!-- Table -->
    <div class="overflow-hidden rounded-lg border border-border">
      <table class="w-full">
        <thead>
          <tr class="border-b border-border bg-surface-2">
            <th class="w-8 px-3 py-2.5"></th>
            <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Version</th>
            <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Stage</th>
            <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Source</th>
            <th class="px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">Git</th>
            <th class="px-4 py-2.5 text-right text-2xs font-medium uppercase tracking-wider text-text-tertiary">Files</th>
            <th class="px-4 py-2.5 text-right text-2xs font-medium uppercase tracking-wider text-text-tertiary">Date</th>
            <th class="w-10"></th>
            {#if canManage}<th class="w-10"></th>{/if}
          </tr>
        </thead>
        <tbody>
          {#each filteredAssets as asset (asset.id)}
            {@const isExpanded = expandedId === asset.id}
            {@const hasFiles = (asset.assets?.length ?? 0) > 0}
            <!-- Data row -->
            <tr
              class="border-b border-border-subtle last:border-0 group transition-colors {hasFiles ? 'cursor-pointer hover:bg-surface-2' : ''}"
              onclick={() => hasFiles && (expandedId = isExpanded ? null : asset.id)}
              onkeydown={(e) => e.key === 'Enter' && hasFiles && (expandedId = isExpanded ? null : asset.id)}
              tabindex={hasFiles ? 0 : undefined}
              role={hasFiles ? 'button' : undefined}
            >
              <td class="w-8 px-3 py-3">
                {#if hasFiles}
                  {#if isExpanded}
                    <ChevronDown size={14} class="text-text-tertiary" />
                  {:else}
                    <ChevronRight size={14} class="text-text-tertiary" />
                  {/if}
                {/if}
              </td>
              <td class="px-4 py-3">
                <div class="flex items-center gap-1.5">
                  <span class="font-mono text-sm font-medium text-text-primary">v{asset.version}</span>
                  {#if asset.variant}
                    <span class="text-2xs text-text-tertiary">({asset.variant})</span>
                  {/if}
                </div>
              </td>
              <td class="px-4 py-3">
                <div class="flex items-center gap-1.5">
                  {#if asset.stageType === 'MANUFACTURING'}
                    <span class="badge badge-warning">Mfg</span>
                  {:else if asset.stageType === 'VALIDATION'}
                    <span class="badge badge-accent">Val</span>
                  {/if}
                  <span class="text-sm text-text-primary">{stageLabel(asset)}</span>
                </div>
              </td>
              <td class="px-4 py-3">
                <StatusBadge status={asset.source === 'BUILD_SERVICE' ? 'BUILD_SERVICE' : asset.source === 'EXTERNAL_CI' ? 'EXTERNAL_CI' : 'MANUAL_UPLOAD'} />
              </td>
              <td class="px-4 py-3">
                {#if asset.branch}
                  <span class="flex items-center gap-1 text-2xs text-text-secondary">
                    <span class="font-mono truncate max-w-24">{asset.branch}</span>
                    {#if asset.commitSha}
                      <span class="font-mono text-text-tertiary">{asset.commitSha.slice(0, 7)}</span>
                    {/if}
                  </span>
                {:else}
                  <span class="text-2xs text-text-tertiary">—</span>
                {/if}
              </td>
              <td class="px-4 py-3 text-right">
                <span class="text-sm text-text-secondary">{asset.assets?.length ?? 0}</span>
              </td>
              <td class="px-4 py-3 text-right">
                <TimeDisplay datetime={asset.createdAt} />
              </td>
              <td class="w-10 text-center">
                <button
                  onclick={(e) => { e.stopPropagation(); handleDownloadZip(asset.id, asset.version, asset.variant); }}
                  class="btn btn-sm btn-icon btn-ghost"
                  title="Download as .zip"
                >
                  <Download size={14} />
                </button>
              </td>
              {#if canManage}
                <td class="w-10 text-center">
                  <button
                    onclick={(e) => { e.stopPropagation(); deleteTarget = { id: asset.id, name: `v${asset.version} (${asset.variant || 'default'})` }; }}
                    class="btn btn-sm btn-icon btn-ghost opacity-0 group-hover:opacity-100 text-text-tertiary hover:text-error hover:bg-error-muted"
                    title="Delete asset set"
                  >
                    <Trash2 size={12} />
                  </button>
                </td>
              {/if}
            </tr>
            <!-- Expanded file details -->
            {#if isExpanded && hasFiles}
              <tr class="border-b border-border-subtle last:border-0">
                <td colspan={canManage ? 9 : 8} class="p-0">
                  <div class="border-t border-border-subtle bg-surface-0 px-8 py-3">
                    {#if asset.modemFirmware}
                      <div class="flex items-center gap-2 mb-3 text-2xs text-text-secondary">
                        <Radio size={10} class="text-text-tertiary" />
                        Modem firmware: <span class="font-mono font-medium">v{asset.modemFirmware.version}</span>
                      </div>
                    {/if}
                    <table class="w-full text-2xs">
                      <thead>
                        <tr class="border-b border-border-subtle">
                          <th class="pb-1.5 text-left font-medium uppercase tracking-wider text-text-tertiary">Label</th>
                          <th class="pb-1.5 text-left font-medium uppercase tracking-wider text-text-tertiary">Role</th>
                          <th class="pb-1.5 text-left font-medium uppercase tracking-wider text-text-tertiary">Type</th>
                          <th class="pb-1.5 text-left font-medium uppercase tracking-wider text-text-tertiary">File</th>
                          <th class="pb-1.5 text-right font-medium uppercase tracking-wider text-text-tertiary">Size</th>
                          <th class="pb-1.5 w-8"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {#each asset.assets as file}
                          <tr class="border-b border-border-subtle last:border-b-0">
                            <td class="py-1.5">
                              <div class="flex items-center gap-1">
                                <FileCode size={10} class="text-text-tertiary" />
                                <span class="font-medium text-text-primary">{file.label}</span>
                              </div>
                            </td>
                            <td class="py-1.5 text-text-secondary">{file.role}{#if file.processor} <span class="text-text-tertiary">({file.processor})</span>{/if}</td>
                            <td class="py-1.5"><span class="badge badge-neutral">{file.artifactType}</span></td>
                            <td class="py-1.5 font-mono text-text-tertiary truncate max-w-44" title={file.filename}>{file.filename}</td>
                            <td class="py-1.5 text-right text-text-tertiary">{formatSize(file.sizeBytes)}</td>
                            <td class="py-1.5 text-right">
                              {#if file.storageKey}
                                <button
                                  onclick={() => handleDownloadFile(file)}
                                  class="btn btn-sm btn-icon btn-ghost"
                                  title="Download {file.filename}"
                                >
                                  <Download size={12} />
                                </button>
                              {/if}
                            </td>
                          </tr>
                        {/each}
                      </tbody>
                    </table>
                  </div>
                </td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
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

<ConfirmDeleteDialog
  open={!!modemDeleteTarget}
  entityType="modem firmware"
  entityName={modemDeleteTarget ? `v${modemDeleteTarget.version}` : ''}
  onConfirm={() => { handleDeleteModemFirmware(modemDeleteTarget!.id); modemDeleteTarget = null; }}
  onCancel={() => (modemDeleteTarget = null)}
/>
