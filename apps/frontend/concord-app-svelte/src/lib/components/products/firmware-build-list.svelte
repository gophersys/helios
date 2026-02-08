<script lang="ts">
  import { Download, Trash2, Plus } from 'lucide-svelte';
  import { apiFetch, api } from '$lib/api';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import ConfirmDeleteDialog from '$lib/components/ui/confirm-delete-dialog.svelte';
  import FirmwareBuildUpload from './firmware-build-upload.svelte';
  import type { FirmwareBuild, BoardRevision } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  interface Props {
    productId: string;
    applicationId: string;
    builds: FirmwareBuild[];
    boardRevisions: BoardRevision[];
    canManage: boolean;
    onRefresh: () => void;
  }

  let { productId, applicationId, builds, boardRevisions, canManage, onRefresh }: Props = $props();

  let error = $state<string | null>(null);
  let showUpload = $state(false);
  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  async function handleDownload(buildId: string) {
    try {
      const res = await apiFetch<ApiResponse<{ url: string }>>(`/v2/products/builds/${buildId}/download`);
      window.open(res.data.url, '_blank');
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to get download URL';
    }
  }

  function promptDelete(buildId: string) {
    const build = builds.find((b) => b.id === buildId);
    deleteTarget = { id: buildId, name: build?.version || '' };
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

<div class="mt-3">
  <ErrorAlert message={error} />

  {#if builds.length > 0}
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr class="border-b border-border">
            <th class="table-header">Version</th>
            <th class="table-header">Board Rev</th>
            <th class="table-header">Status</th>
            <th class="table-header">Mfg</th>
            <th class="table-header text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each builds as build (build.id)}
            <tr class="table-row">
              <td class="table-cell font-medium text-text-primary">{build.version}</td>
              <td class="table-cell text-text-secondary">{build.boardRevisionVersion || '-'}</td>
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
    <div class="mt-2">
      {#if showUpload}
        <FirmwareBuildUpload
          {productId}
          {applicationId}
          {boardRevisions}
          onSuccess={() => { showUpload = false; onRefresh(); }}
          onCancel={() => (showUpload = false)}
        />
      {:else}
        <button
          onclick={() => (showUpload = true)}
          class="flex items-center gap-1.5 rounded-lg bg-accent px-2.5 py-1.5 text-2xs font-medium text-white hover:bg-accent-hover"
        >
          <Plus size={16} />
          Upload build
        </button>
      {/if}
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
