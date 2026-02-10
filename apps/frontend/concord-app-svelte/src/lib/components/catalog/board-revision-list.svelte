<script lang="ts">
  import { Plus, Check, X } from 'lucide-svelte';
  import { api } from '$lib/api';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import ConfirmDeleteDialog from '$lib/components/ui/confirm-delete-dialog.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import ChipsetTagInput from './chipset-tag-input.svelte';
  import type { BoardRevision, FirmwareBuild, Chipset } from '$lib/types/models';

  interface Props {
    productId: string;
    boardId: string;
    revisions: BoardRevision[];
    builds: FirmwareBuild[];
    chipsets: Chipset[];
    canManage: boolean;
    onRefresh: () => void;
  }

  let { productId, boardId, revisions, builds, chipsets, canManage, onRefresh }: Props = $props();

  let error = $state<string | null>(null);
  let showForm = $state(false);
  let editingId = $state<string | null>(null);
  let submitting = $state(false);

  let formVersion = $state('');
  let formChipsetIds = $state<string[]>([]);
  let formStatus = $state('ACTIVE');
  let formSelectedBuilds = $state<Record<string, string>>({});
  let formNotes = $state('');

  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  /** Chipset options for the tag input */
  const chipsetOptions = $derived(
    chipsets.map((c) => ({ id: c.id, name: c.name }))
  );

  /** Get chipset name by ID */
  function chipsetName(id: string): string {
    return chipsets.find((c) => c.id === id)?.name || id;
  }

  /** Check if a chipset is a modem by ID */
  function isModemChipset(id: string): boolean {
    return chipsets.find((c) => c.id === id)?.isModem ?? false;
  }

  /** Get firmware build options filtered to a specific chipset ID */
  function buildsForChipset(chipsetId: string) {
    return builds
      .filter((b) => b.chipsetId === chipsetId)
      .map((b) => {
        let label = `${b.version}`;
        if (b.modemFilename) label += ' + modem';
        return { value: b.id, label };
      });
  }

  /** Look up a build by ID */
  function getBuild(buildId: string): FirmwareBuild | undefined {
    return builds.find((b) => b.id === buildId);
  }

  function resetForm() {
    formVersion = '';
    formChipsetIds = [];
    formStatus = 'ACTIVE';
    formSelectedBuilds = {};
    formNotes = '';
    editingId = null;
    showForm = false;
  }

  function startEdit(rev: BoardRevision) {
    formVersion = rev.version;
    formChipsetIds = rev.chipsets.map((c) => c.id);
    formStatus = rev.status;
    formSelectedBuilds = { ...(rev.selectedBuilds || {}) };
    formNotes = rev.notes || '';
    editingId = rev.id;
    showForm = true;
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    error = null;

    // Validate: each chipset must have a firmware build selected
    if (editingId && formChipsetIds.length > 0) {
      const missing = formChipsetIds.filter(
        (id) => buildsForChipset(id).length > 0 && !formSelectedBuilds[id]
      );
      if (missing.length > 0) {
        error = `Select firmware for: ${missing.map(chipsetName).join(', ')}`;
        return;
      }
    }

    submitting = true;

    const body: Record<string, unknown> = {
      version: formVersion,
      chipsetIds: formChipsetIds,
      status: formStatus,
      notes: formNotes || null,
    };
    if (editingId) {
      // Only include chipsets that have a selection
      const selected: Record<string, string> = {};
      for (const id of formChipsetIds) {
        if (formSelectedBuilds[id]) {
          selected[id] = formSelectedBuilds[id];
        }
      }
      body.selectedBuilds = Object.keys(selected).length > 0 ? selected : null;
    }

    try {
      if (editingId) {
        await api.put(`/v2/catalog/${productId}/boards/${boardId}/revisions/${editingId}`, body);
      } else {
        await api.post(`/v2/catalog/${productId}/boards/${boardId}/revisions`, body);
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
      await api.delete(`/v2/catalog/${productId}/boards/${boardId}/revisions/${id}`);
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
            selected={formChipsetIds}
            options={chipsetOptions}
            onchange={(v) => (formChipsetIds = v)}
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

      <!-- Per-chipset firmware selection (edit mode only) -->
      {#if editingId && formChipsetIds.length > 0}
        {@const chipsWithBuilds = formChipsetIds.filter((id) => buildsForChipset(id).length > 0)}
        {#if chipsWithBuilds.length > 0}
          <div class="mt-3 border-t border-border-subtle pt-3">
            <span class="mb-2 block text-2xs font-semibold text-text-secondary">Selected Firmware per Chipset</span>
            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {#each chipsWithBuilds as chipId}
                {@const isModem = isModemChipset(chipId)}
                {@const options = buildsForChipset(chipId)}
                {@const selectedBuild = formSelectedBuilds[chipId] ? getBuild(formSelectedBuilds[chipId]) : null}
                <div>
                  <Select
                    bind:value={formSelectedBuilds[chipId]}
                    label={isModem ? `${chipsetName(chipId)} (modem)` : chipsetName(chipId)}
                    placeholder="Select build..."
                    {options}
                  />
                  {#if isModem && selectedBuild && !selectedBuild.modemFilename}
                    <p class="mt-1 text-2xs text-warning">No modem firmware on this build — upload one in Firmware Releases.</p>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}
      {/if}

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
            <th class="table-header">Selected Firmware</th>
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
                      {chip.name}
                    </span>
                  {/each}
                </div>
              </td>
              <td class="table-cell">
                {#if rev.selectedBuilds && Object.keys(rev.selectedBuilds).length > 0}
                  <div class="flex flex-col gap-1">
                    {#each Object.entries(rev.selectedBuilds) as [chipId, buildId]}
                      {@const build = getBuild(buildId)}
                      {#if build}
                        <span class="inline-flex items-center gap-1 rounded-full bg-success-muted px-2 py-0.5 text-2xs font-medium text-success">
                          <span class="text-success/70">{chipsetName(chipId)}:</span>
                          {build.version}
                          {#if build.modemFilename}
                            <span class="rounded-full bg-surface-2 px-1.5 text-text-secondary">modem</span>
                          {/if}
                        </span>
                      {/if}
                    {/each}
                  </div>
                {:else}
                  <span class="text-2xs text-text-tertiary">-</span>
                {/if}
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
