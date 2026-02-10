<script lang="ts">
  import { Plus, Check, X, Pencil, Trash2 } from 'lucide-svelte';
  import { api } from '$lib/api';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import ConfirmDeleteDialog from '$lib/components/ui/confirm-delete-dialog.svelte';
  import type { Chipset } from '$lib/types/models';

  interface Props {
    chipsets: Chipset[];
    canManage: boolean;
    onRefresh: () => void;
  }

  let { chipsets, canManage, onRefresh }: Props = $props();

  let error = $state<string | null>(null);
  let showForm = $state(false);
  let editingId = $state<string | null>(null);
  let submitting = $state(false);

  let formName = $state('');
  let formManufacturer = $state('');
  let formIsModem = $state(false);
  let formDescription = $state('');
  let formActive = $state(true);

  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  function resetForm() {
    formName = '';
    formManufacturer = '';
    formIsModem = false;
    formDescription = '';
    formActive = true;
    editingId = null;
    showForm = false;
  }

  function startEdit(c: Chipset) {
    formName = c.name;
    formManufacturer = c.manufacturer || '';
    formIsModem = c.isModem;
    formDescription = c.description || '';
    formActive = c.active;
    editingId = c.id;
    showForm = true;
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    error = null;
    submitting = true;

    const body = {
      name: formName,
      manufacturer: formManufacturer || null,
      isModem: formIsModem,
      description: formDescription || null,
      active: formActive,
    };

    try {
      if (editingId) {
        await api.put(`/v2/catalog/chipsets/${editingId}`, body);
      } else {
        await api.post('/v2/catalog/chipsets', body);
      }
      resetForm();
      onRefresh();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to save chipset';
    } finally {
      submitting = false;
    }
  }

  function promptDelete(id: string) {
    const target = chipsets.find((c) => c.id === id);
    deleteTarget = { id, name: target?.name || '' };
  }

  async function handleDelete(id: string) {
    error = null;
    try {
      await api.delete(`/v2/catalog/chipsets/${id}`);
      onRefresh();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete chipset';
    }
  }
</script>

<div>
  <ErrorAlert message={error} />

  <div class="mb-3 flex items-center justify-between">
    <h3 class="text-sm font-semibold text-text-primary">Chipsets</h3>
    {#if canManage && !showForm}
      <button
        onclick={() => { resetForm(); showForm = true; }}
        class="flex items-center gap-1.5 rounded-lg bg-accent px-2.5 py-1.5 text-2xs font-medium text-white hover:bg-accent-hover"
      >
        <Plus size={16} />
        Add chipset
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
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Name</span>
          <input
            type="text"
            required
            bind:value={formName}
            placeholder="e.g. nRF52840"
            class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </label>
        <label>
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Manufacturer</span>
          <input
            type="text"
            bind:value={formManufacturer}
            placeholder="e.g. Nordic Semiconductor"
            class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </label>
        <label>
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Description</span>
          <input
            type="text"
            bind:value={formDescription}
            placeholder="Optional"
            class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </label>
        <div class="flex flex-col gap-2 pt-5">
          <label class="flex items-center gap-2 text-sm text-text-primary">
            <input type="checkbox" bind:checked={formIsModem} class="rounded border-border" />
            Modem chipset
          </label>
          <label class="flex items-center gap-2 text-sm text-text-primary">
            <input type="checkbox" bind:checked={formActive} class="rounded border-border" />
            Active
          </label>
        </div>
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

  {#if chipsets.length > 0}
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr class="border-b border-border">
            <th class="table-header">Name</th>
            <th class="table-header">Manufacturer</th>
            <th class="table-header">Modem</th>
            <th class="table-header">Status</th>
            {#if canManage}
              <th class="table-header text-right">Actions</th>
            {/if}
          </tr>
        </thead>
        <tbody>
          {#each chipsets as c (c.id)}
            <tr class="table-row">
              <td class="table-cell font-medium text-text-primary">{c.name}</td>
              <td class="table-cell text-text-secondary">{c.manufacturer || '-'}</td>
              <td class="table-cell">
                {#if c.isModem}
                  <span class="rounded-full bg-accent-muted px-2 py-0.5 text-2xs font-medium text-accent">Modem</span>
                {:else}
                  <span class="text-text-tertiary">-</span>
                {/if}
              </td>
              <td class="table-cell">
                <span
                  class={[
                    'inline-flex items-center rounded-full px-2 py-0.5 text-2xs font-medium',
                    c.active ? 'bg-success-muted text-success' : 'bg-surface-2 text-text-tertiary'
                  ].join(' ')}
                >
                  {c.active ? 'Active' : 'Inactive'}
                </span>
              </td>
              {#if canManage}
                <td class="table-cell text-right">
                  <button
                    onclick={() => startEdit(c)}
                    class="mr-2 rounded px-2 py-1 text-2xs text-text-secondary hover:bg-surface-2"
                    aria-label="Edit"
                  >
                    <Pencil size={14} class="inline" />
                  </button>
                  <button
                    onclick={() => promptDelete(c.id)}
                    class="rounded px-2 py-1 text-2xs text-error hover:bg-error-muted"
                    aria-label="Delete"
                  >
                    <Trash2 size={14} class="inline" />
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
      No chipsets configured yet
    </div>
  {/if}

  <ConfirmDeleteDialog
    open={!!deleteTarget}
    entityType="chipset"
    entityName={deleteTarget?.name || ''}
    onConfirm={() => { handleDelete(deleteTarget!.id); deleteTarget = null; }}
    onCancel={() => (deleteTarget = null)}
  />
</div>
