<script lang="ts">
  import { Plus, ChevronDown, ChevronRight, Trash2, Download } from 'lucide-svelte';
  import { apiFetch, api } from '$lib/api';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import ConfirmDeleteDialog from '$lib/components/ui/confirm-delete-dialog.svelte';
  import FirmwareBuildUpload from './firmware-build-upload.svelte';
  import type { FirmwareBuild, Chipset } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  interface Props {
    productId: string;
    builds: FirmwareBuild[];
    chipsets: Chipset[];
    canManage: boolean;
    onRefresh: () => void;
  }

  let { productId, builds, chipsets, canManage, onRefresh }: Props = $props();

  let error = $state<string | null>(null);
  let expandedChipsets = $state(new Set<string>());
  let uploadChipsetId = $state<string | null>(null);
  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  interface ChipsetGroup {
    chipsetId: string;
    chipsetName: string;
    builds: FirmwareBuild[];
    isModem: boolean;
  }

  const groupedBuilds = $derived.by(() => {
    const groups: Record<string, { builds: FirmwareBuild[]; name: string; isModem: boolean }> = {};
    // Initialize groups from available chipsets
    for (const chip of chipsets) {
      groups[chip.id] = { builds: [], name: chip.name, isModem: chip.isModem };
    }
    // Add builds to groups (may include chipsets not in chipsets list)
    for (const build of builds) {
      if (!groups[build.chipsetId]) {
        groups[build.chipsetId] = {
          builds: [],
          name: build.chipset.name,
          isModem: build.chipset.isModem,
        };
      }
      groups[build.chipsetId].builds.push(build);
    }
    return Object.entries(groups)
      .map(([chipsetId, group]) => ({
        chipsetId,
        chipsetName: group.name,
        builds: group.builds,
        isModem: group.isModem,
      }))
      .sort((a, b) => a.chipsetName.localeCompare(b.chipsetName));
  });

  function toggleExpanded(chipsetId: string) {
    const next = new Set(expandedChipsets);
    if (next.has(chipsetId)) {
      next.delete(chipsetId);
    } else {
      next.add(chipsetId);
    }
    expandedChipsets = next;
  }

  async function handleDownload(buildId: string) {
    try {
      const res = await apiFetch<ApiResponse<{ url: string }>>(`/v2/catalog/firmware-builds/${buildId}/download`);
      window.open(res.data.url, '_blank');
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to get download URL';
    }
  }

  function promptDelete(buildId: string) {
    const build = builds.find((b) => b.id === buildId);
    deleteTarget = { id: buildId, name: build ? `${build.chipset.name} v${build.version}` : '' };
  }

  async function handleDelete(buildId: string) {
    error = null;
    try {
      await api.delete(`/v2/catalog/${productId}/firmware-builds/${buildId}`);
      onRefresh();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete build';
    }
  }
</script>

<div>
  <ErrorAlert message={error} />

  <div class="mb-3 flex items-center justify-between">
    <h3 class="text-sm font-semibold text-text-primary">Firmware Builds</h3>
  </div>

  {#if chipsets.length === 0}
    <div class="py-6 text-center text-sm text-text-tertiary">
      Add chipsets first to manage firmware builds.
    </div>
  {:else}
    <div class="space-y-2">
      {#each groupedBuilds as group (group.chipsetId)}
        {@const isExpanded = expandedChipsets.has(group.chipsetId)}
        <div class="rounded-lg border border-border bg-surface-0">
          <!-- Chipset header -->
          <div
            role="button"
            tabindex="0"
            onclick={() => toggleExpanded(group.chipsetId)}
            onkeydown={(e) => e.key === 'Enter' && toggleExpanded(group.chipsetId)}
            class="flex cursor-pointer items-center gap-3 px-3 py-2.5 hover:bg-surface-1"
          >
            {#if isExpanded}
              <ChevronDown size={16} class="shrink-0 text-text-tertiary" />
            {:else}
              <ChevronRight size={16} class="shrink-0 text-text-tertiary" />
            {/if}
            <span class="font-semibold text-text-primary text-sm">{group.chipsetName}</span>
            {#if group.isModem}
              <span class="rounded-full bg-surface-2 px-2 py-0.5 text-2xs font-medium text-text-secondary">Modem</span>
            {/if}
            <span class="ml-auto text-2xs text-text-tertiary">
              {group.builds.length} build{group.builds.length !== 1 ? 's' : ''}
            </span>
          </div>

          {#if isExpanded}
            <div class="border-t border-border-subtle px-4 py-3">
              {#if group.builds.length > 0}
                <div class="table-wrapper">
                  <table class="table">
                    <thead>
                      <tr class="border-b border-border">
                        <th class="table-header">Version</th>
                        <th class="table-header">Status</th>
                        <th class="table-header">Mfg</th>
                        <th class="table-header text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {#each group.builds as build (build.id)}
                        <tr class="table-row">
                          <td class="table-cell font-medium text-text-primary">
                            {build.version}
                            {#if build.modemFilename}
                              <span class="ml-1.5 rounded-full bg-surface-2 px-1.5 py-0.5 text-2xs font-medium text-text-secondary">+Modem</span>
                            {/if}
                          </td>
                          <td class="table-cell">
                            <StatusBadge status={build.status} />
                          </td>
                          <td class="table-cell">
                            {#if build.isManufacturing}
                              <span class="rounded-full bg-warning-muted px-2 py-0.5 text-2xs font-medium text-warning">MFG</span>
                            {:else}
                              <span class="text-text-tertiary">-</span>
                            {/if}
                          </td>
                          <td class="table-cell text-right">
                            <div class="flex items-center justify-end gap-1">
                              <button
                                onclick={() => handleDownload(build.id)}
                                class="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-accent"
                                title="Download"
                                aria-label="Download"
                              >
                                <Download size={16} />
                              </button>
                              {#if canManage}
                                <button
                                  onclick={() => promptDelete(build.id)}
                                  class="rounded p-1 text-text-tertiary hover:bg-error-muted hover:text-error"
                                  title="Delete"
                                  aria-label="Delete"
                                >
                                  <Trash2 size={16} />
                                </button>
                              {/if}
                            </div>
                          </td>
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                </div>
              {:else}
                <div class="table-empty">No builds yet</div>
              {/if}

              {#if canManage}
                <div class="mt-3">
                  {#if uploadChipsetId === group.chipsetId}
                    <FirmwareBuildUpload
                      {productId}
                      chipsetId={group.chipsetId}
                      isModem={group.isModem}
                      onSuccess={() => { uploadChipsetId = null; onRefresh(); }}
                      onCancel={() => (uploadChipsetId = null)}
                    />
                  {:else}
                    <button
                      onclick={() => (uploadChipsetId = group.chipsetId)}
                      class="flex items-center gap-1.5 rounded-lg bg-accent px-2.5 py-1.5 text-2xs font-medium text-white hover:bg-accent-hover"
                    >
                      <Plus size={16} />
                      Upload build
                    </button>
                  {/if}
                </div>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}

  <ConfirmDeleteDialog
    open={!!deleteTarget}
    entityType="firmware build"
    entityName={deleteTarget?.name || ''}
    onConfirm={() => { handleDelete(deleteTarget!.id); deleteTarget = null; }}
    onCancel={() => (deleteTarget = null)}
  />
</div>
