<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    ChevronLeft,
    ChevronRight,
    ChevronsLeft,
    ChevronsRight,
    Plus,
    Pencil,
    Trash2,
    Wrench,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import type { TestBedDesign, TestBedDesignSummary, Pagination } from '$lib/types/models';
  import { formatTimeAgo, formatDateTime } from '$lib/utils/formatting';
  import EmptyState from '$lib/components/ui/empty-state.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import FormCard from '$lib/components/ui/form-card.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import TextInput from '$lib/components/ui/text-input.svelte';
  import {
    fetchDesigns,
    fetchDesign,
    createDesign,
    updateDesign,
    deleteDesign,
  } from '$lib/services/validation';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('validation:manage'));

  // List state
  let designs = $state<TestBedDesignSummary[]>([]);
  let pagination = $state<Pagination>({ page: 1, limit: 50, total: 0, pages: 0 });
  let loading = $state(true);
  let error = $state<string | null>(null);
  let page = $state(1);
  let productFilter = $state('');

  // Form state
  let showForm = $state(false);
  let editingId = $state<string | null>(null);
  let formName = $state('');
  let formBoardRevisionId = $state('');
  let formRevision = $state('');
  let formProfileTemplate = $state('{}');
  let formSchematicUrl = $state('');
  let formBomUrl = $state('');
  let formAssemblyGuide = $state('');
  let formNotes = $state('');
  let submitting = $state(false);

  // Delete confirmation
  let deleteTarget = $state<TestBedDesignSummary | null>(null);
  let deleting = $state(false);

  async function loadDesigns(): Promise<void> {
    loading = true;
    error = null;
    try {
      const result = await fetchDesigns({ page, limit: 50, product: productFilter || undefined });
      designs = result.data;
      pagination = result.pagination;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load TestBed designs';
    } finally {
      loading = false;
    }
  }

  function resetForm(): void {
    showForm = false;
    editingId = null;
    formName = '';
    formBoardRevisionId = '';
    formRevision = '';
    formProfileTemplate = '{}';
    formSchematicUrl = '';
    formBomUrl = '';
    formAssemblyGuide = '';
    formNotes = '';
  }

  async function openEditForm(id: string): Promise<void> {
    try {
      const design = await fetchDesign(id);
      editingId = id;
      formName = design.name;
      formBoardRevisionId = design.boardRevisionId;
      formRevision = design.revision;
      formProfileTemplate = JSON.stringify(design.profileTemplate, null, 2);
      formSchematicUrl = design.schematicUrl || '';
      formBomUrl = design.bomUrl || '';
      formAssemblyGuide = design.assemblyGuide || '';
      formNotes = design.notes || '';
      showForm = true;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load design';
    }
  }

  async function handleSubmit(e: Event): Promise<void> {
    e.preventDefault();
    error = null;
    submitting = true;

    // Parse profile template
    let profileTemplate: Record<string, unknown>;
    try {
      profileTemplate = JSON.parse(formProfileTemplate);
    } catch {
      error = 'Invalid JSON in profile template';
      submitting = false;
      return;
    }

    const data = {
      name: formName,
      boardRevisionId: formBoardRevisionId,
      revision: formRevision,
      profileTemplate,
      schematicUrl: formSchematicUrl || undefined,
      bomUrl: formBomUrl || undefined,
      assemblyGuide: formAssemblyGuide || undefined,
      notes: formNotes || undefined,
    };

    try {
      if (editingId) {
        await updateDesign(editingId, data);
      } else {
        await createDesign(data);
      }
      resetForm();
      await loadDesigns();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to save design';
    } finally {
      submitting = false;
    }
  }

  async function handleDelete(): Promise<void> {
    if (!deleteTarget) return;
    deleting = true;
    error = null;
    try {
      await deleteDesign(deleteTarget.id);
      deleteTarget = null;
      await loadDesigns();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to delete design';
    } finally {
      deleting = false;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('validation:view')) {
      goto('/');
      return;
    }
    loadDesigns();
  });

  $effect(() => {
    const _p = page;
    loadDesigns();
  });

  $effect(() => {
    const _f = productFilter;
    page = 1;
  });
</script>

<svelte:head>
  <title>TestBed Designs - Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="TestBed Designs"
      description="Versioned hardware designs for validation fixtures with profile templates."
    />
  </div>

  <ErrorAlert message={error} />

  <!-- Delete confirmation -->
  {#if deleteTarget}
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div class="w-full max-w-md rounded-lg bg-surface-1 p-6 shadow-xl">
        <h3 class="mb-2 text-lg font-semibold text-text-primary">Delete TestBed Design</h3>
        <p class="mb-4 text-sm text-text-secondary">
          Are you sure you want to delete <span class="font-medium">{deleteTarget.name}</span>? This
          action cannot be undone.
        </p>
        <div class="flex justify-end gap-2">
          <button onclick={() => (deleteTarget = null)} class="btn btn-sm">Cancel</button>
          <button onclick={handleDelete} disabled={deleting} class="btn btn-sm btn-danger">
            {deleting ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  {/if}

  <!-- Create/Edit form -->
  {#if showForm}
    <FormCard title={editingId ? 'Edit TestBed Design' : 'New TestBed Design'} onClose={resetForm}>
      <form onsubmit={handleSubmit} class="space-y-3">
        <TextInput
          bind:value={formName}
          label="Name"
          placeholder="e.g. alpha-fixture-v1.2"
          required
        />

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextInput
            bind:value={formBoardRevisionId}
            label="Board Revision ID"
            placeholder="Board revision ID"
            required
            disabled={!!editingId}
          />
          <TextInput
            bind:value={formRevision}
            label="Revision"
            placeholder="e.g. 1.2"
            required
            disabled={!!editingId}
          />
        </div>

        <div>
          <label for="profile" class="mb-1 block text-2xs font-medium text-text-tertiary">
            Profile Template (JSON)
          </label>
          <textarea
            id="profile"
            bind:value={formProfileTemplate}
            rows={6}
            class="font-mono w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden"
          ></textarea>
        </div>

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextInput bind:value={formSchematicUrl} label="Schematic URL" placeholder="https://..." />
          <TextInput bind:value={formBomUrl} label="BOM URL" placeholder="https://..." />
        </div>

        <TextInput
          bind:value={formAssemblyGuide}
          label="Assembly Guide"
          placeholder="Markdown or URL..."
        />

        <div>
          <label for="notes" class="mb-1 block text-2xs font-medium text-text-tertiary">Notes</label>
          <textarea
            id="notes"
            bind:value={formNotes}
            rows={2}
            placeholder="Optional notes about this design..."
            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden"
          ></textarea>
        </div>

        <div class="flex justify-end gap-2 pt-1">
          <button type="button" onclick={resetForm} class="btn btn-sm">Cancel</button>
          <button type="submit" disabled={submitting} class="btn btn-sm btn-primary">
            {submitting ? 'Saving...' : editingId ? 'Update' : 'Create'}
          </button>
        </div>
      </form>
    </FormCard>
  {/if}

  <div class="mb-4 flex flex-wrap items-center gap-3">
    <TextInput
      bind:value={productFilter}
      placeholder="Filter by product..."
      class="w-48"
    />
    <span class="ml-auto text-2xs text-text-tertiary">{pagination.total} designs</span>
    {#if canManage}
      <button
        onclick={() => (showForm = true)}
        class="btn btn-sm btn-primary flex items-center gap-1.5"
      >
        <Plus size={14} />
        New Design
      </button>
    {/if}
  </div>

  {#if loading}
    <LoadingState message="Loading TestBed designs..." />
  {:else if designs.length === 0}
    <EmptyState message="No TestBed designs found." icon={Wrench} />
  {:else}
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr class="border-b border-border">
            <th class="table-header">Name</th>
            <th class="table-header">Board Revision</th>
            <th class="table-header">Revision</th>
            <th class="table-header text-center">Benches</th>
            <th class="table-header text-right">Created</th>
            {#if canManage}
              <th class="table-header w-20"></th>
            {/if}
          </tr>
        </thead>
        <tbody>
          {#each designs as design (design.id)}
            <tr class="table-row">
              <td class="table-cell font-medium text-text-primary">{design.name}</td>
              <td class="table-cell text-text-secondary">{design.boardRevision?.ckBoardsName ?? design.boardRevisionId}</td>
              <td class="table-cell">
                <span class="rounded bg-surface-2 px-2 py-0.5 text-xs text-text-secondary">
                  {design.revision}
                </span>
              </td>
              <td class="table-cell text-center text-text-secondary">{design.benchCount ?? 0}</td>
              <td class="table-cell text-right text-text-tertiary">
                {formatTimeAgo(design.createdAt)}
              </td>
              {#if canManage}
                <td class="table-cell">
                  <div class="flex justify-end gap-1">
                    <button
                      onclick={() => openEditForm(design.id)}
                      title="Edit"
                      class="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      onclick={() => (deleteTarget = design)}
                      title="Delete"
                      class="rounded p-1 text-text-tertiary hover:bg-error/10 hover:text-error"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              {/if}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  {#if pagination.pages > 1}
    <div class="mt-4 flex items-center justify-between">
      <span class="text-2xs text-text-tertiary">Page {pagination.page} of {pagination.pages}</span>
      <div class="flex items-center gap-1">
        <button
          onclick={() => (page = 1)}
          disabled={page <= 1}
          aria-label="First page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronsLeft size={16} />
        </button>
        <button
          onclick={() => (page = Math.max(1, page - 1))}
          disabled={page <= 1}
          aria-label="Previous page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronLeft size={16} />
        </button>
        <button
          onclick={() => (page = Math.min(pagination.pages, page + 1))}
          disabled={page >= pagination.pages}
          aria-label="Next page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronRight size={16} />
        </button>
        <button
          onclick={() => (page = pagination.pages)}
          disabled={page >= pagination.pages}
          aria-label="Last page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronsRight size={16} />
        </button>
      </div>
    </div>
  {/if}
</div>
