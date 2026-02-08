<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Plus, Check } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, apiUpload, api } from '$lib/api';
  import { PageHeader, ErrorAlert, EmptyState, LoadingState, ConfirmDeleteDialog, FormCard } from '$lib/components/ui';
  import CodebaseCard from '$lib/components/codebases/codebase-card.svelte';
  import CodebaseDetail from '$lib/components/codebases/codebase-detail.svelte';
  import type { Codebase } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('Concord.Admin.Codebases.Manage'));

  let codebases = $state<Codebase[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Form state
  let showForm = $state(false);
  let editingId = $state<string | null>(null);
  let formName = $state('');
  let formDescription = $state('');
  let formRepoUrl = $state('');
  let formDefaultBranch = $state('main');
  let submitting = $state(false);

  // Delete confirmation
  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  // Detail state
  let selectedCodebase = $state<Codebase | null>(null);

  async function fetchCodebases() {
    try {
      const res = await apiFetch<ApiResponse<Codebase[]>>('/v2/codebases');
      codebases = res.data;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load codebases';
    } finally {
      loading = false;
    }
  }

  async function fetchDetail(id: string) {
    try {
      const res = await apiFetch<ApiResponse<Codebase>>(`/v2/codebases/${id}`);
      selectedCodebase = res.data;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load codebase';
    }
  }

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.Codebases.View')) {
      goto('/');
      return;
    }
    fetchCodebases();
  });

  function resetForm() {
    formName = '';
    formDescription = '';
    formRepoUrl = '';
    formDefaultBranch = 'main';
    editingId = null;
    showForm = false;
  }

  function startEdit(c: Codebase) {
    formName = c.name;
    formDescription = c.description || '';
    formRepoUrl = c.repoUrl || '';
    formDefaultBranch = c.defaultBranch;
    editingId = c.id;
    showForm = true;
    selectedCodebase = null;
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    error = null;
    submitting = true;

    const body = {
      name: formName,
      description: formDescription || null,
      repoUrl: formRepoUrl || null,
      defaultBranch: formDefaultBranch,
    };

    try {
      if (editingId) {
        await api.put(`/v2/codebases/${editingId}`, body);
      } else {
        await api.post('/v2/codebases', body);
      }
      resetForm();
      fetchCodebases();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to save codebase';
    } finally {
      submitting = false;
    }
  }

  function promptDelete(id: string) {
    const target = codebases.find((c) => c.id === id);
    deleteTarget = { id, name: target?.name || '' };
  }

  async function handleDelete(id: string) {
    error = null;
    try {
      await api.delete(`/v2/codebases/${id}`);
      if (selectedCodebase?.id === id) selectedCodebase = null;
      fetchCodebases();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete';
    }
  }

  async function handleImageUpload(file: File) {
    if (!selectedCodebase) return;
    try {
      const formData = new FormData();
      formData.append('file', file);
      await apiUpload(`/v2/codebases/${selectedCodebase.id}/image`, formData);
      fetchCodebases();
      fetchDetail(selectedCodebase.id);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to upload image';
    }
  }
</script>

<svelte:head>
  <title>Codebases — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="Codebases"
      description="Manage codebases, releases, and artifacts."
    />
  </div>

  {#if loading}
    <LoadingState message="Loading codebases..." />
  {:else if selectedCodebase}
    <CodebaseDetail
      codebase={selectedCodebase}
      {canManage}
      onBack={() => (selectedCodebase = null)}
      onRefresh={() => fetchDetail(selectedCodebase!.id)}
      onImageUpload={handleImageUpload}
    />
  {:else}
    <ErrorAlert message={error} />

    {#if showForm && canManage}
      <FormCard title={editingId ? 'Edit codebase' : 'New codebase'} onClose={resetForm}>
        <form onsubmit={handleSubmit}>
          <div class="mb-3 grid grid-cols-2 gap-3">
            <label>
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Name</span>
              <input
                type="text"
                required
                bind:value={formName}
                placeholder="e.g. Concord OS"
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </label>
            <label>
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Default Branch</span>
              <input
                type="text"
                required
                bind:value={formDefaultBranch}
                placeholder="e.g. main"
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </label>
          </div>
          <div class="mb-3 grid grid-cols-2 gap-3">
            <label>
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Repository URL</span>
              <input
                type="url"
                bind:value={formRepoUrl}
                placeholder="https://github.com/..."
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

    <!-- Add button -->
    {#if canManage && !showForm}
      <div class="mb-4 flex justify-end">
        <button
          onclick={() => { resetForm(); showForm = true; }}
          class="flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover"
        >
          <Plus size={16} />
          New codebase
        </button>
      </div>
    {/if}

    <!-- Grid -->
    {#if codebases.length === 0}
      <EmptyState message="No codebases yet" />
    {:else}
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {#each codebases as c (c.id)}
          <CodebaseCard
            codebase={c}
            {canManage}
            onEdit={startEdit}
            onDelete={promptDelete}
            onSelect={(cb) => fetchDetail(cb.id)}
          />
        {/each}
      </div>
    {/if}

    <ConfirmDeleteDialog
      open={!!deleteTarget}
      entityType="codebase"
      entityName={deleteTarget?.name || ''}
      onConfirm={() => { handleDelete(deleteTarget!.id); deleteTarget = null; }}
      onCancel={() => (deleteTarget = null)}
    />
  {/if}
</div>
