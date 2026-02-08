<script lang="ts">
  import { Plus, Check, X } from 'lucide-svelte';
  import { api } from '$lib/api';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import ConfirmDeleteDialog from '$lib/components/ui/confirm-delete-dialog.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import ChipsetTagInput from './chipset-tag-input.svelte';
  import type { BoardRevision } from '$lib/types/models';

  interface Props {
    productId: string;
    revisions: BoardRevision[];
    supportedSocs: string[];
    canManage: boolean;
    onRefresh: () => void;
  }

  let { productId, revisions, supportedSocs, canManage, onRefresh }: Props = $props();

  let error = $state<string | null>(null);
  let showForm = $state(false);
  let editingId = $state<string | null>(null);
  let submitting = $state(false);

  let formVersion = $state('');
  let formChipsets = $state<string[]>([]);
  let formStatus = $state('ACTIVE');
  let formNotes = $state('');

  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  function resetForm() {
    formVersion = '';
    formChipsets = [];
    formStatus = 'ACTIVE';
    formNotes = '';
    editingId = null;
    showForm = false;
  }

  function startEdit(rev: BoardRevision) {
    formVersion = rev.version;
    formChipsets = [...rev.chipsets];
    formStatus = rev.status;
    formNotes = rev.notes || '';
    editingId = rev.id;
    showForm = true;
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    error = null;
    submitting = true;

    const body = {
      version: formVersion,
      chipsets: formChipsets,
      status: formStatus,
      notes: formNotes || null,
    };

    try {
      if (editingId) {
        await api.put(`/v2/products/${productId}/board-revisions/${editingId}`, body);
      } else {
        await api.post(`/v2/products/${productId}/board-revisions`, body);
      }
      resetForm();
      onRefresh();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to save revision';
    } finally {
      submitting = false;
    }
  }

  function promptDelete(id: string) {
    const rev = revisions.find((r) => r.id === id);
    deleteTarget = { id, name: rev?.version || '' };
  }

  async function handleDelete(id: string) {
    error = null;
    try {
      await api.delete(`/v2/products/${productId}/board-revisions/${id}`);
      onRefresh();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete revision';
    }
  }
</script>

<div>
  <ErrorAlert message={error} />

  <div class="mb-3 flex items-center justify-between">
    <h3 class="text-sm font-semibold text-text-primary">Board Revisions</h3>
    {#if canManage && !showForm}
      <button
        onclick={() => { resetForm(); showForm = true; }}
        class="flex items-center gap-1.5 rounded-lg bg-accent px-2.5 py-1.5 text-2xs font-medium text-white hover:bg-accent-hover"
      >
        <Plus size={16} />
        Add revision
      </button>
    {/if}
  </div>

  {#if showForm}
    <form
      onsubmit={handleSubmit}
      class="mb-4 rounded-lg border border-border bg-surface-0 p-3"
    >
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <label>
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Version</span>
          <input
            type="text"
            required
            bind:value={formVersion}
            placeholder="e.g. REV1.0"
            class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </label>
        <div>
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Chipsets</span>
          <ChipsetTagInput
            selected={formChipsets}
            options={supportedSocs}
            onchange={(v) => (formChipsets = v)}
          />
        </div>
        <Select
          bind:value={formStatus}
          label="Status"
          options={[
            { value: 'ACTIVE', label: 'Active' },
            { value: 'DEPRECATED', label: 'Deprecated' },
            { value: 'EOL', label: 'End of Life' },
          ]}
        />
        <label>
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Notes</span>
          <input
            type="text"
            bind:value={formNotes}
            placeholder="Optional"
            class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </label>
      </div>
      <div class="mt-3 flex gap-2">
        <button
          type="submit"
          disabled={submitting}
          class="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          <Check size={16} />
          {submitting ? 'Saving...' : editingId ? 'Save' : 'Create'}
        </button>
        <button
          type="button"
          onclick={resetForm}
          class="rounded-lg px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-surface-2"
        >
          Cancel
        </button>
      </div>
    </form>
  {/if}

  {#if revisions.length > 0}
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr class="border-b border-border">
            <th class="table-header">Version</th>
            <th class="table-header">Chipsets</th>
            <th class="table-header">Status</th>
            <th class="table-header">Notes</th>
            {#if canManage}
              <th class="table-header text-right">Actions</th>
            {/if}
          </tr>
        </thead>
        <tbody>
          {#each revisions as rev (rev.id)}
            <tr class="table-row">
              <td class="table-cell font-medium text-text-primary">{rev.version}</td>
              <td class="table-cell">
                <div class="flex flex-wrap gap-1">
                  {#each rev.chipsets as chip}
                    <span class="rounded-full bg-accent-muted px-2 py-0.5 text-2xs font-medium text-accent">
                      {chip}
                    </span>
                  {/each}
                </div>
              </td>
              <td class="table-cell">
                <StatusBadge status={rev.status} />
              </td>
              <td class="table-cell text-text-secondary">{rev.notes || '-'}</td>
              {#if canManage}
                <td class="table-cell text-right">
                  <button
                    onclick={() => startEdit(rev)}
                    class="mr-2 rounded px-2 py-1 text-2xs text-text-secondary hover:bg-surface-2"
                  >
                    Edit
                  </button>
                  <button
                    onclick={() => promptDelete(rev.id)}
                    class="rounded px-2 py-1 text-2xs text-error hover:bg-error-muted"
                  >
                    Delete
                  </button>
                </td>
              {/if}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <div class="table-empty">
      No board revisions yet
    </div>
  {/if}

  <ConfirmDeleteDialog
    open={!!deleteTarget}
    entityType="board revision"
    entityName={deleteTarget?.name || ''}
    onConfirm={() => { handleDelete(deleteTarget!.id); deleteTarget = null; }}
    onCancel={() => (deleteTarget = null)}
  />
</div>
