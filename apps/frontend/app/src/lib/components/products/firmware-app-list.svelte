<script lang="ts">
  import { Plus, ChevronDown, ChevronRight, Trash2, Download } from 'lucide-svelte';
  import { apiFetch, api } from '$lib/api';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import ConfirmDeleteDialog from '$lib/components/ui/confirm-delete-dialog.svelte';
  import FirmwareBuildUpload from './firmware-build-upload.svelte';
  import type { FirmwareBuild, ProductTarget } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  interface Props {
    productId: string;
    builds: FirmwareBuild[];
    targets: ProductTarget[];
    canManage: boolean;
    onRefresh: () => void;
  }

  let { productId, builds, targets, canManage, onRefresh }: Props = $props();

  let error = $state<string | null>(null);
  let expandedTargets = $state(new Set<string>());
  let uploadTargetId = $state<string | null>(null);
  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  interface TargetGroup {
    targetId: string;
    targetLabel: string;
    builds: FirmwareBuild[];
  }

  const groupedBuilds = $derived.by(() => {
    const groups: Record<string, { builds: FirmwareBuild[]; label: string }> = {};
    // Initialize groups from available targets
    for (const t of targets) {
      groups[t.id] = { builds: [], label: `${t.soc} (${t.role})` };
    }
    // Add builds to groups (may include targets not in targets list)
    for (const build of builds) {
      if (build.targetId) {
        if (!groups[build.targetId]) {
          const t = build.target;
          groups[build.targetId] = {
            builds: [],
            label: t ? `${t.soc} (${t.role})` : build.targetId,
          };
        }
        groups[build.targetId].builds.push(build);
      }
    }
    return Object.entries(groups)
      .map(([targetId, group]) => ({
        targetId,
        targetLabel: group.label,
        builds: group.builds,
      }))
      .sort((a, b) => a.targetLabel.localeCompare(b.targetLabel));
  });

  // Builds with no target
  const untargetedBuilds = $derived(builds.filter((b) => !b.targetId));

  function toggleExpanded(targetId: string) {
    const next = new Set(expandedTargets);
    if (next.has(targetId)) {
      next.delete(targetId);
    } else {
      next.add(targetId);
    }
    expandedTargets = next;
  }

  async function handleDownload(buildId: string) {
    try {
      const res = await apiFetch<ApiResponse<{ url: string }>>(`/v2/products/firmware-builds/${buildId}/download`);
      window.open(res.data.url, '_blank');
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to get download URL';
    }
  }

  function promptDelete(buildId: string) {
    const build = builds.find((b) => b.id === buildId);
    const label = build?.target ? `${build.target.soc} v${build.version}` : `v${build?.version}`;
    deleteTarget = { id: buildId, name: label };
  }

  async function handleDelete(buildId: string) {
    error = null;
    try {
      await api.delete(`/v2/products/${productId}/firmware-builds/${buildId}`);
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

  {#if targets.length === 0}
    <div class="py-6 text-center text-sm text-text-tertiary">
      Add targets first to manage firmware builds.
    </div>
  {:else}
    <div class="space-y-2">
      {#each groupedBuilds as group (group.targetId)}
        {@const isExpanded = expandedTargets.has(group.targetId)}
        <div class="rounded-lg border border-border bg-surface-0">
          <!-- Target header -->
          <div
            role="button"
            tabindex="0"
            onclick={() => toggleExpanded(group.targetId)}
            onkeydown={(e) => e.key === 'Enter' && toggleExpanded(group.targetId)}
            class="flex cursor-pointer items-center gap-3 px-3 py-2.5 hover:bg-surface-1"
          >
            {#if isExpanded}
              <ChevronDown size={16} class="shrink-0 text-text-tertiary" />
            {:else}
              <ChevronRight size={16} class="shrink-0 text-text-tertiary" />
            {/if}
            <span class="font-semibold text-text-primary text-sm">{group.targetLabel}</span>
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
                  {#if uploadTargetId === group.targetId}
                    <FirmwareBuildUpload
                      {productId}
                      targetId={group.targetId}
                      onSuccess={() => { uploadTargetId = null; onRefresh(); }}
                      onCancel={() => (uploadTargetId = null)}
                    />
                  {:else}
                    <button
                      onclick={() => (uploadTargetId = group.targetId)}
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
