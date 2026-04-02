<script lang="ts">
  import { Plus, Check } from 'lucide-svelte';
  import { apiFetch, apiUpload, api } from '$lib/api';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { BackButton, ConfirmDeleteDialog, StatusBadge, ErrorAlert, EmptyState, LoadingState, Select, FormCard } from '$lib/components/ui';
  import ImageUpload from '$lib/components/ui/image-upload.svelte';
  import AssemblyCard from './assembly-card.svelte';
  import BomEditor from './bom-editor.svelte';
  import type { Assembly, AssemblyRevision, InventoryRevisionOption, InventoryComponent } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('products:manage'));

  let assemblies = $state<Assembly[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let availableRevisions = $state<InventoryRevisionOption[]>([]);

  // Form state
  let showForm = $state(false);
  let editingId = $state<string | null>(null);
  let formName = $state('');
  let formDescription = $state('');
  let submitting = $state(false);

  // Delete confirmation
  let deleteTarget = $state<{ id: string; name: string } | null>(null);
  let deleteRevTarget = $state<{ id: string; name: string } | null>(null);

  // Detail view
  let selectedAssembly = $state<Assembly | null>(null);

  // Revision form
  let showRevForm = $state(false);
  let revVersion = $state('');
  let revStatus = $state('ACTIVE');
  let revNotes = $state('');
  let revBom = $state<{ inventoryRevisionId: string; quantity: number }[]>([]);
  let revSubmitting = $state(false);

  interface ComponentData {
    id: string;
    name: string;
    category: string;
    revisions?: {
      id: string;
      version: string;
      status: string;
      componentId: string;
    }[];
  }

  async function fetchAssemblies() {
    try {
      const res = await apiFetch<ApiResponse<{ data: Assembly[] }>>('/v2/inventory/assemblies');
      const payload = res.data;
      assemblies = Array.isArray(payload) ? payload : (payload as { data: Assembly[] }).data || [];
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load assemblies';
    } finally {
      loading = false;
    }
  }

  async function fetchAvailableRevisions() {
    try {
      const res = await apiFetch<ApiResponse<{ data: ComponentData[] }>>('/v2/inventory/components');
      const compPayload = res.data;
      const compList = Array.isArray(compPayload) ? compPayload : (compPayload as { data: ComponentData[] }).data || [];
      const revisions: InventoryRevisionOption[] = [];
      for (const comp of compList) {
        for (const rev of comp.revisions || []) {
          revisions.push({
            id: rev.id,
            version: rev.version,
            status: rev.status,
            componentId: comp.id,
            componentName: comp.name,
            category: comp.category,
          });
        }
      }
      availableRevisions = revisions;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load component revisions';
    }
  }

  async function fetchDetail(id: string) {
    try {
      const res = await apiFetch<ApiResponse<Assembly>>(`/v2/inventory/assemblies/${id}`);
      selectedAssembly = res.data;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load assembly';
    }
  }

  fetchAssemblies();
  fetchAvailableRevisions();

  function resetForm() {
    formName = '';
    formDescription = '';
    editingId = null;
    showForm = false;
  }

  function startEdit(a: Assembly) {
    formName = a.name;
    formDescription = a.description || '';
    editingId = a.id;
    showForm = true;
    selectedAssembly = null;
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    error = null;
    submitting = true;

    const body = {
      name: formName,
      description: formDescription || null,
    };

    try {
      if (editingId) {
        await api.put(`/v2/inventory/assemblies/${editingId}`, body);
      } else {
        await api.post('/v2/inventory/assemblies', body);
      }
      resetForm();
      fetchAssemblies();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to save assembly';
    } finally {
      submitting = false;
    }
  }

  function promptDelete(id: string) {
    const target = assemblies.find((a) => a.id === id);
    deleteTarget = { id, name: target?.name || '' };
  }

  async function handleDelete(id: string) {
    error = null;
    try {
      await api.delete(`/v2/inventory/assemblies/${id}`);
      if (selectedAssembly?.id === id) selectedAssembly = null;
      fetchAssemblies();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete';
    }
  }

  async function handleImageUpload(assemblyId: string, file: File) {
    try {
      const formData = new FormData();
      formData.append('file', file);
      await apiUpload(`/v2/inventory/assemblies/${assemblyId}/image`, formData);
      fetchAssemblies();
      if (selectedAssembly?.id === assemblyId) fetchDetail(assemblyId);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to upload image';
    }
  }

  async function handleCreateRevision(e: Event) {
    e.preventDefault();
    if (!selectedAssembly) return;
    error = null;
    revSubmitting = true;
    try {
      await api.post(`/v2/inventory/assemblies/${selectedAssembly.id}/revisions`, {
        version: revVersion,
        status: revStatus,
        releaseNotes: revNotes || null,
        bom: revBom,
      });
      revVersion = '';
      revStatus = 'ACTIVE';
      revNotes = '';
      revBom = [];
      showRevForm = false;
      fetchDetail(selectedAssembly.id);
      fetchAssemblies();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to create revision';
    } finally {
      revSubmitting = false;
    }
  }

  function promptDeleteRevision(revisionId: string) {
    if (!selectedAssembly) return;
    const rev = selectedAssembly.revisions?.find((r) => r.id === revisionId);
    deleteRevTarget = { id: revisionId, name: rev?.version || '' };
  }

  async function handleDeleteRevision(revisionId: string) {
    if (!selectedAssembly) return;
    try {
      await api.delete(
        `/v2/inventory/assemblies/${selectedAssembly.id}/revisions/${revisionId}`
      );
      fetchDetail(selectedAssembly.id);
      fetchAssemblies();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete revision';
    }
  }
</script>

{#if loading}
  <LoadingState message="Loading assemblies..." />
{:else if selectedAssembly}
  <!-- Detail view -->
  <div class="animate-fade-in">
    <BackButton label="Back to assemblies" onclick={() => (selectedAssembly = null)} />

    <div class="card card-md">
      <div class="flex gap-6">
        <div class="w-48 shrink-0">
          <ImageUpload
            currentUrl={selectedAssembly.imageUrl}
            onUpload={(file) => handleImageUpload(selectedAssembly!.id, file)}
            disabled={!canManage}
          />
        </div>
        <div class="flex-1">
          <h2 class="text-lg font-semibold text-text-primary">
            {selectedAssembly.name}
          </h2>
          {#if selectedAssembly.description}
            <p class="mt-1 text-sm text-text-secondary">
              {selectedAssembly.description}
            </p>
          {/if}
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
            <div class="mb-3 grid grid-cols-3 gap-3">
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

            <BomEditor
              bom={revBom}
              onchange={(b) => (revBom = b)}
              {availableRevisions}
            />

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
                onclick={() => { showRevForm = false; revBom = []; }}
                class="rounded-lg px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-surface-2"
              >
                Cancel
              </button>
            </div>
          </form>
        {/if}

        {#if selectedAssembly.revisions && selectedAssembly.revisions.length > 0}
          <div class="space-y-3">
            {#each selectedAssembly.revisions as rev (rev.id)}
              <div class="rounded-lg border border-border bg-surface-0 p-3">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-semibold text-text-primary">{rev.version}</span>
                    <StatusBadge status={rev.status} />
                    {#if rev.releaseNotes}
                      <span class="text-2xs text-text-tertiary">{rev.releaseNotes}</span>
                    {/if}
                  </div>
                  {#if canManage}
                    <button
                      onclick={() => promptDeleteRevision(rev.id)}
                      class="rounded px-2 py-1 text-2xs text-error hover:bg-error-muted"
                    >
                      Delete
                    </button>
                  {/if}
                </div>

                <!-- BOM -->
                {#if rev.bom && rev.bom.length > 0}
                  <div class="mt-2 border-t border-border-subtle pt-2">
                    <div class="mb-1 text-2xs font-medium text-text-tertiary">
                      Bill of Materials
                    </div>
                    <div class="space-y-0.5">
                      {#each rev.bom as item (item.id)}
                        <div class="text-2xs text-text-secondary">
                          {item.quantity}x
                          {item.inventoryRevision?.component?.name || 'Unknown'}
                          <span class="text-text-tertiary">
                            ({item.inventoryRevision?.version || '?'})
                          </span>
                        </div>
                      {/each}
                    </div>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {:else}
          <div class="py-6 text-center text-sm text-text-tertiary">
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
      <FormCard title={editingId ? 'Edit assembly' : 'New assembly'} onClose={resetForm}>
        <form onsubmit={handleSubmit}>
          <div class="mb-3 grid grid-cols-2 gap-3">
            <label>
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Name</span>
              <input
                type="text"
                required
                bind:value={formName}
                placeholder="e.g. MTIB Assembly"
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </label>
            <label>
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Description</span>
              <input
                type="text"
                bind:value={formDescription}
                placeholder="Optional description"
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </label>
          </div>
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

    {#if canManage && !showForm}
      <div class="mb-4 flex justify-end">
        <button
          onclick={() => { resetForm(); showForm = true; }}
          class="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
        >
          <Plus size={16} />
          New assembly
        </button>
      </div>
    {/if}

    {#if assemblies.length === 0}
      <EmptyState message="No assemblies yet" />
    {:else}
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {#each assemblies as a (a.id)}
          <AssemblyCard
            assembly={a}
            {canManage}
            onEdit={startEdit}
            onDelete={promptDelete}
            onSelect={(asm) => fetchDetail(asm.id)}
          />
        {/each}
      </div>
    {/if}

    <ConfirmDeleteDialog
      open={!!deleteTarget}
      entityType="assembly"
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
