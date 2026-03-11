<script lang="ts">
  import { Download, Trash2, Plus, Check, X, Link } from 'lucide-svelte';
  import { apiFetch, apiUploadRaw, api } from '$lib/api';
  import ConfirmDeleteDialog from '$lib/components/ui/confirm-delete-dialog.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import ArtifactUpload from '$lib/components/ui/artifact-upload.svelte';
  import { formatSize } from '$lib/utils/formatting';
  import type { Artifact } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  interface Props {
    codebaseId: string;
    releaseId: string;
    artifacts: Artifact[];
    canManage: boolean;
    onRefresh: () => void;
  }

  let { codebaseId, releaseId, artifacts, canManage, onRefresh }: Props = $props();

  let error = $state<string | null>(null);
  let deleteTarget = $state<{ id: string; name: string } | null>(null);
  let showExternalForm = $state(false);
  let showUpload = $state(false);
  let extName = $state('');
  let extUrl = $state('');
  let submitting = $state(false);

  function promptDelete(artifactId: string) {
    const art = artifacts.find((a) => a.id === artifactId);
    deleteTarget = { id: artifactId, name: art?.name || '' };
  }

  async function handleDelete(artifactId: string) {
    error = null;
    try {
      await api.delete(
        `/v2/builds/codebases/${codebaseId}/releases/${releaseId}/artifacts/${artifactId}`
      );
      onRefresh();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete artifact';
    }
  }

  async function handleDownload(artifactId: string) {
    try {
      const res = await apiFetch<ApiResponse<{ url: string }>>(
        `/v2/builds/codebases/artifacts/${artifactId}/download`
      );
      window.open(res.data.url, '_blank');
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to get download URL';
    }
  }

  async function handleCreateExternal(e: Event) {
    e.preventDefault();
    error = null;
    submitting = true;
    try {
      await api.post(`/v2/builds/codebases/${codebaseId}/releases/${releaseId}/artifacts`, {
        name: extName,
        externalUrl: extUrl,
      });
      extName = '';
      extUrl = '';
      showExternalForm = false;
      onRefresh();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to create artifact';
    } finally {
      submitting = false;
    }
  }

  async function handleUploadFile(file: File) {
    error = null;
    try {
      const formData = new FormData();
      formData.append('file', file);

      await apiUploadRaw(
        `/v2/builds/codebases/${codebaseId}/releases/${releaseId}/artifacts/upload`,
        formData
      );

      showUpload = false;
      onRefresh();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to upload artifact';
    }
  }
</script>

<div class="mt-2">
  <ErrorAlert message={error} />

  {#if artifacts.length > 0}
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr class="border-b border-border">
            <th class="table-header">Name</th>
            <th class="table-header">Type</th>
            <th class="table-header">Size</th>
            <th class="table-header text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each artifacts as a (a.id)}
            <tr class="table-row">
              <td class="table-cell">
                <div class="font-medium text-text-primary">{a.name}</div>
                {#if a.filename && a.filename !== a.name}
                  <div class="text-2xs text-text-tertiary">{a.filename}</div>
                {/if}
              </td>
              <td class="table-cell">
                <StatusBadge status={a.type} />
              </td>
              <td class="table-cell text-text-secondary text-2xs">
                {formatSize(a.sizeBytes)}
              </td>
              <td class="table-cell text-right">
                <div class="flex items-center justify-end gap-1">
                  <button
                    onclick={() => handleDownload(a.id)}
                    class="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-accent"
                    title="Download"
                    aria-label="Download"
                  >
                    <Download size={16} />
                  </button>
                  {#if canManage}
                    <button
                      onclick={() => promptDelete(a.id)}
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
    <div class="table-empty">No artifacts</div>
  {/if}

  <!-- Add buttons -->
  {#if canManage}
    <div class="mt-2 flex gap-2">
      {#if !showUpload && !showExternalForm}
        <button
          onclick={() => (showUpload = true)}
          class="flex items-center gap-1 rounded-lg bg-accent px-2.5 py-1.5 text-2xs font-medium text-white hover:bg-accent-hover"
        >
          <Plus size={12} />
          Upload file
        </button>
        <button
          onclick={() => (showExternalForm = true)}
          class="flex items-center gap-1 rounded-lg border border-border px-2.5 py-1.5 text-2xs font-medium text-text-secondary hover:bg-surface-2"
        >
          <Link size={12} />
          Add external link
        </button>
      {/if}
    </div>
  {/if}

  <!-- Upload zone -->
  {#if showUpload}
    <div class="mt-2">
      <ArtifactUpload onUpload={handleUploadFile} />
      <button
        onclick={() => (showUpload = false)}
        class="mt-1 text-2xs text-text-tertiary hover:text-text-secondary"
      >
        Cancel
      </button>
    </div>
  {/if}

  <!-- External link form -->
  {#if showExternalForm}
    <form
      onsubmit={handleCreateExternal}
      class="mt-2 rounded-lg border border-border bg-surface-0 p-3"
    >
      <div class="grid grid-cols-2 gap-2">
        <label>
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Name</span>
          <input
            type="text"
            required
            bind:value={extName}
            placeholder="e.g. Release Notes PDF"
            class="w-full rounded-lg border border-border bg-surface-1 px-3 py-1.5 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </label>
        <label>
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">URL</span>
          <input
            type="url"
            required
            bind:value={extUrl}
            placeholder="https://..."
            class="w-full rounded-lg border border-border bg-surface-1 px-3 py-1.5 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </label>
      </div>
      <div class="mt-2 flex gap-2">
        <button
          type="submit"
          disabled={submitting}
          class="flex items-center gap-1 rounded-lg bg-accent px-2.5 py-1.5 text-2xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          <Check size={12} />
          {submitting ? 'Adding...' : 'Add'}
        </button>
        <button
          type="button"
          onclick={() => { showExternalForm = false; extName = ''; extUrl = ''; }}
          class="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-2xs font-medium text-text-secondary hover:bg-surface-2"
        >
          <X size={12} />
          Cancel
        </button>
      </div>
    </form>
  {/if}

  <ConfirmDeleteDialog
    open={!!deleteTarget}
    entityType="artifact"
    entityName={deleteTarget?.name || ''}
    onConfirm={() => { handleDelete(deleteTarget!.id); deleteTarget = null; }}
    onCancel={() => (deleteTarget = null)}
  />
</div>
