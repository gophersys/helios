<script lang="ts">
  import { Plus, Check } from 'lucide-svelte';
  import { apiFetch, apiUpload, api } from '$lib/api';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { BackButton, ConfirmDeleteDialog, StatusBadge, ErrorAlert, EmptyState, LoadingState, Select, FormCard } from '$lib/components/ui';
  import ImageUpload from '$lib/components/ui/image-upload.svelte';
  import ComponentCard from './component-card.svelte';
  import type { InventoryComponent, InventoryRevision } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import { getCategoryDisplayName, getCategoryOptions } from '$lib/constants/inventory';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('Concord.Admin.Inventory.Manage'));

  let components = $state<InventoryComponent[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Form state
  let showForm = $state(false);
  let editingId = $state<string | null>(null);
  let formName = $state('');
  let formDescription = $state('');
  let formCategory = $state('HARDWARE');
  let formManufacturer = $state('');
  let formPartNumber = $state('');
  let submitting = $state(false);

  // Delete confirmation
  let deleteTarget = $state<{ id: string; name: string } | null>(null);
  let deleteRevTarget = $state<{ id: string; name: string } | null>(null);

  // Detail / revision state
  let selectedComponent = $state<InventoryComponent | null>(null);
  let revVersion = $state('');
  let revStatus = $state('ACTIVE');
  let revNotes = $state('');
  let showRevForm = $state(false);
  let revSubmitting = $state(false);

  async function fetchComponents() {
    try {
      const res = await apiFetch<ApiResponse<{ data: InventoryComponent[] }>>('/v2/inventory/components');
      const payload = res.data;
      components = Array.isArray(payload) ? payload : (payload as { data: InventoryComponent[] }).data || [];
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load components';
    } finally {
      loading = false;
    }
  }

  async function fetchDetail(id: string) {
    try {
      const res = await apiFetch<ApiResponse<InventoryComponent>>(`/v2/inventory/components/${id}`);
      selectedComponent = res.data;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load component';
    }
  }

  fetchComponents();

  function resetForm() {
    formName = '';
    formDescription = '';
    formCategory = 'HARDWARE';
    formManufacturer = '';
    formPartNumber = '';
    editingId = null;
    showForm = false;
  }

  function startEdit(c: InventoryComponent) {
    formName = c.name;
    formDescription = c.description || '';
    formCategory = c.category;
    formManufacturer = c.manufacturer;
    formPartNumber = c.partNumber;
    editingId = c.id;
    showForm = true;
    selectedComponent = null;
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    error = null;
    submitting = true;

    const body = {
      name: formName,
      description: formDescription || null,
      category: formCategory,
      manufacturer: formManufacturer,
      partNumber: formPartNumber,
    };

    try {
      if (editingId) {
        await api.put(`/v2/inventory/components/${editingId}`, body);
      } else {
        await api.post('/v2/inventory/components', body);
      }
      resetForm();
      fetchComponents();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to save component';
    } finally {
      submitting = false;
    }
  }

  function promptDelete(id: string) {
    const target = components.find((c) => c.id === id);
    deleteTarget = { id, name: target?.name || '' };
  }

  async function handleDelete(id: string) {
    error = null;
    try {
      await api.delete(`/v2/inventory/components/${id}`);
      if (selectedComponent?.id === id) selectedComponent = null;
      fetchComponents();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete';
    }
  }

  async function handleImageUpload(componentId: string, file: File) {
    try {
      const formData = new FormData();
      formData.append('file', file);
      await apiUpload(`/v2/inventory/components/${componentId}/image`, formData);
      fetchComponents();
      if (selectedComponent?.id === componentId) fetchDetail(componentId);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to upload image';
    }
  }

  async function handleCreateRevision(e: Event) {
    e.preventDefault();
    if (!selectedComponent) return;
    error = null;
    revSubmitting = true;
    try {
      await api.post(`/v2/inventory/components/${selectedComponent.id}/revisions`, {
        version: revVersion,
        status: revStatus,
        releaseNotes: revNotes || null,
      });
      revVersion = '';
      revStatus = 'ACTIVE';
      revNotes = '';
      showRevForm = false;
      fetchDetail(selectedComponent.id);
      fetchComponents();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to create revision';
    } finally {
      revSubmitting = false;
    }
  }

  function promptDeleteRevision(revisionId: string) {
    if (!selectedComponent) return;
    const rev = selectedComponent.revisions?.find((r) => r.id === revisionId);
    deleteRevTarget = { id: revisionId, name: rev?.version || '' };
  }

  async function handleDeleteRevision(revisionId: string) {
    if (!selectedComponent) return;
    try {
      await api.delete(
        `/v2/inventory/components/${selectedComponent.id}/revisions/${revisionId}`
      );
      fetchDetail(selectedComponent.id);
      fetchComponents();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete revision';
    }
  }
</script>

{#if loading}
  <LoadingState message="Loading components..." />
{:else if selectedComponent}
  <!-- Detail view -->
  <div class="animate-fade-in">
    <BackButton label="Back to components" onclick={() => (selectedComponent = null)} />

    <div class="card card-md">
      <div class="flex gap-6">
        <!-- Image -->
        <div class="w-48 shrink-0">
          <ImageUpload
            currentUrl={selectedComponent.imageUrl}
            onUpload={(file) => handleImageUpload(selectedComponent!.id, file)}
            disabled={!canManage}
          />
        </div>

        <!-- Info -->
        <div class="flex-1">
          <h2 class="text-lg font-semibold text-text-primary">
            {selectedComponent.name}
          </h2>
          {#if selectedComponent.description}
            <p class="mt-1 text-sm text-text-secondary">
              {selectedComponent.description}
            </p>
          {/if}
          <div class="mt-3 flex gap-4 text-2xs text-text-tertiary">
            <span>
              <strong class="text-text-secondary">Category:</strong>
              {getCategoryDisplayName(selectedComponent.category)}
            </span>
            <span>
              <strong class="text-text-secondary">Manufacturer:</strong>
              {selectedComponent.manufacturer}
            </span>
            <span>
              <strong class="text-text-secondary">MPN:</strong>
              {selectedComponent.partNumber}
            </span>
          </div>
        </div>
      </div>

      <!-- Revisions -->
      <div class="mt-6">
        <div class="mb-3 flex items-center justify-between">
          <h3 class="text-sm font-semibold text-text-primary">Revisions</h3>
          {#if canManage && !showRevForm}
            <button
              onclick={() => (showRevForm = true)}
              class="flex items-center gap-1.5 rounded-lg bg-accent px-2.5 py-1.5 text-2xs font-medium text-white hover:bg-accent-hover"
            >
              <Plus size={16} />
              Add revision
            </button>
          {/if}
        </div>

        {#if showRevForm}
          <form
            onsubmit={handleCreateRevision}
            class="mb-4 rounded-lg border border-border bg-surface-0 p-3"
          >
            <div class="grid grid-cols-3 gap-3">
              <label>
                <span class="mb-1 block text-2xs font-medium text-text-tertiary">Version</span>
                <input
                  type="text"
                  required
                  bind:value={revVersion}
                  placeholder="e.g. REV1.0"
                  class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
              </label>
              <Select
                bind:value={revStatus}
                label="Status"
                options={[
                  { value: 'ACTIVE', label: 'Active' },
                  { value: 'DEPRECATED', label: 'Deprecated' },
                  { value: 'EOL', label: 'End of Life' },
                ]}
              />
              <label>
                <span class="mb-1 block text-2xs font-medium text-text-tertiary">Release Notes</span>
                <input
                  type="text"
                  bind:value={revNotes}
                  placeholder="Optional"
                  class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
              </label>
            </div>
            <div class="mt-3 flex gap-2">
              <button
                type="submit"
                disabled={revSubmitting}
                class="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
              >
                <Check size={16} />
                {revSubmitting ? 'Creating...' : 'Create'}
              </button>
              <button
                type="button"
                onclick={() => (showRevForm = false)}
                class="rounded-lg px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-surface-2"
              >
                Cancel
              </button>
            </div>
          </form>
        {/if}

        {#if selectedComponent.revisions && selectedComponent.revisions.length > 0}
          <div class="table-wrapper">
            <table class="table">
              <thead>
                <tr class="border-b border-border">
                  <th class="table-header">Version</th>
                  <th class="table-header">Status</th>
                  <th class="table-header">Notes</th>
                  {#if canManage}
                    <th class="table-header text-right">Actions</th>
                  {/if}
                </tr>
              </thead>
              <tbody>
                {#each selectedComponent.revisions as rev (rev.id)}
                  <tr class="table-row">
                    <td class="table-cell font-medium text-text-primary">{rev.version}</td>
                    <td class="table-cell">
                      <StatusBadge status={rev.status} />
                    </td>
                    <td class="table-cell text-text-secondary">{rev.releaseNotes || '-'}</td>
                    {#if canManage}
                      <td class="table-cell text-right">
                        <button
                          onclick={() => promptDeleteRevision(rev.id)}
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
            No revisions yet
          </div>
        {/if}
      </div>
    </div>
  </div>
{:else}
  <div>
    <ErrorAlert message={error} />

    {#if showForm && canManage}
      <FormCard title={editingId ? 'Edit component' : 'New component'} onClose={resetForm}>
        <form onsubmit={handleSubmit}>
          <div class="mb-3 grid grid-cols-2 gap-3">
            <label>
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Name</span>
              <input
                type="text"
                required
                bind:value={formName}
                placeholder="e.g. Verdin iMX8MM"
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </label>
            <Select
              bind:value={formCategory}
              label="Category"
              options={getCategoryOptions()}
            />
          </div>
          <div class="mb-3 grid grid-cols-2 gap-3">
            <label>
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Manufacturer</span>
              <input
                type="text"
                required
                bind:value={formManufacturer}
                placeholder="e.g. Toradex"
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </label>
            <label>
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Manufacturer Part Number (MPN)</span>
              <input
                type="text"
                required
                bind:value={formPartNumber}
                placeholder="e.g. MPN-00740-A1"
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </label>
          </div>
          <label class="mb-4 block">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Description</span>
            <input
              type="text"
              bind:value={formDescription}
              placeholder="Optional description"
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
            />
          </label>
          <div class="flex gap-2">
            <button
              type="submit"
              disabled={submitting}
              class="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              <Check size={16} />
              {submitting ? 'Saving...' : editingId ? 'Save changes' : 'Create'}
            </button>
            <button
              type="button"
              onclick={resetForm}
              class="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2"
            >
              Cancel
            </button>
          </div>
        </form>
      </FormCard>
    {/if}

    <!-- Add button -->
    {#if canManage && !showForm}
      <div class="mb-4 flex justify-end">
        <button
          onclick={() => { resetForm(); showForm = true; }}
          class="flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover"
        >
          <Plus size={16} />
          New component
        </button>
      </div>
    {/if}

    <!-- Grid -->
    {#if components.length === 0}
      <EmptyState message="No inventory components yet" />
    {:else}
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {#each components as c (c.id)}
          <ComponentCard
            component={c}
            {canManage}
            onEdit={startEdit}
            onDelete={promptDelete}
            onSelect={(comp) => fetchDetail(comp.id)}
          />
        {/each}
      </div>
    {/if}

    <ConfirmDeleteDialog
      open={!!deleteTarget}
      entityType="component"
      entityName={deleteTarget?.name || ''}
      onConfirm={() => { handleDelete(deleteTarget!.id); deleteTarget = null; }}
      onCancel={() => (deleteTarget = null)}
    />
    <ConfirmDeleteDialog
      open={!!deleteRevTarget}
      entityType="revision"
      entityName={deleteRevTarget?.name || ''}
      onConfirm={() => { handleDeleteRevision(deleteRevTarget!.id); deleteRevTarget = null; }}
      onCancel={() => (deleteRevTarget = null)}
    />
  </div>
{/if}
