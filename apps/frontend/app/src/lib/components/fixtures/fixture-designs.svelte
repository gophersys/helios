<script lang="ts">
  import { onMount } from 'svelte';
  import { Plus, Check, Pencil, Trash2 } from 'lucide-svelte';
  import { apiFetch, api } from '$lib/api';
  import { ErrorAlert, EmptyState, LoadingState, ConfirmDeleteDialog, Select, FormCard } from '$lib/components/ui';
  import type { FixtureDesign, Product, Board, BoardRevision } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  let { canManage }: { canManage: boolean } = $props();

  let designs = $state<FixtureDesign[]>([]);
  let products = $state<Product[]>([]);
  let boards = $state<Board[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Form state
  let showForm = $state(false);
  let editingId = $state<string | null>(null);
  let formName = $state('');
  let formProductId = $state('');
  let formBoardRevisionId = $state('');
  let formRevision = $state('');
  let formProfileTemplate = $state('{}');
  let submitting = $state(false);

  // Delete
  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  // Board revisions derived from selected product's boards
  const boardRevisions = $derived.by(() => {
    const revisions: { id: string; label: string }[] = [];
    for (const board of boards) {
      for (const rev of board.revisions ?? []) {
        revisions.push({
          id: rev.id,
          label: `${board.name} ${rev.version}${rev.ckBoardsName ? ` (${rev.ckBoardsName})` : ''}`
        });
      }
    }
    return revisions;
  });

  async function fetchDesigns() {
    try {
      const res = await apiFetch<ApiResponse<{ data: FixtureDesign[] }>>('/v2/fixtures/designs');
      const payload = res.data;
      designs = Array.isArray(payload) ? payload : (payload as { data: FixtureDesign[] }).data || [];
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load designs';
    } finally {
      loading = false;
    }
  }

  async function fetchProducts() {
    try {
      const res = await apiFetch<ApiResponse<{ data: Product[] }>>('/v2/products');
      const payload = res.data;
      products = Array.isArray(payload) ? payload : (payload as { data: Product[] }).data || [];
    } catch {
      // Non-critical
    }
  }

  async function fetchBoardsForProduct(productId: string) {
    if (!productId) {
      boards = [];
      return;
    }
    try {
      const res = await apiFetch<ApiResponse<Product>>(`/v2/products/${productId}`);
      boards = res.data.boards ?? [];
    } catch {
      boards = [];
    }
  }

  // Fetch boards when product changes
  $effect(() => {
    if (formProductId) {
      fetchBoardsForProduct(formProductId);
    } else {
      boards = [];
    }
  });

  // Reset board revision when product changes
  $effect(() => {
    // When boards change, check if selected revision is still valid
    if (formBoardRevisionId && boardRevisions.length > 0) {
      const stillValid = boardRevisions.some(r => r.id === formBoardRevisionId);
      if (!stillValid) formBoardRevisionId = '';
    }
  });

  onMount(() => {
    fetchDesigns();
    fetchProducts();
  });

  function resetForm() {
    formName = '';
    formProductId = '';
    formBoardRevisionId = '';
    formRevision = '';
    formProfileTemplate = '{}';
    editingId = null;
    showForm = false;
  }

  function startEdit(d: FixtureDesign) {
    formName = d.name;
    formBoardRevisionId = d.boardRevisionId;
    formRevision = d.revision;
    formProfileTemplate = JSON.stringify(d.profileTemplate, null, 2);
    editingId = d.id;
    showForm = true;

    // Find the product for this board revision
    // We'll need to look through products to find which one owns this revision
    for (const p of products) {
      for (const b of p.boards ?? []) {
        for (const rev of b.revisions ?? []) {
          if (rev.id === d.boardRevisionId) {
            formProductId = p.id;
            return;
          }
        }
      }
    }
    // If product not found via inline boards, fetch all products and try to match
    formProductId = '';
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    error = null;
    submitting = true;

    // Validate JSON
    let profileTemplate: Record<string, unknown>;
    try {
      profileTemplate = JSON.parse(formProfileTemplate);
    } catch {
      error = 'Profile template must be valid JSON';
      submitting = false;
      return;
    }

    const body = {
      name: formName,
      boardRevisionId: formBoardRevisionId || null,
      revision: formRevision,
      profileTemplate,
    };

    try {
      if (editingId) {
        await api.put(`/v2/fixtures/designs/${editingId}`, body);
      } else {
        await api.post('/v2/fixtures/designs', body);
      }
      resetForm();
      fetchDesigns();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to save design';
    } finally {
      submitting = false;
    }
  }

  function promptDelete(id: string) {
    const target = designs.find(d => d.id === id);
    deleteTarget = { id, name: target?.name || '' };
  }

  async function handleDelete(id: string) {
    error = null;
    try {
      await api.delete(`/v2/fixtures/designs/${id}`);
      fetchDesigns();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete design';
    }
  }
</script>

<div>
  <ErrorAlert message={error} />

  {#if canManage && !showForm}
    <div class="mb-4">
      <button
        onclick={() => { resetForm(); showForm = true; }}
        class="btn btn-sm btn-primary"
      >
        <Plus size={16} />
        Create Design
      </button>
    </div>
  {/if}

  {#if showForm && canManage}
    <FormCard title={editingId ? 'Edit design' : 'New design'} onClose={resetForm}>
      <form onsubmit={handleSubmit}>
        <div class="mb-3 grid grid-cols-2 gap-3">
          <label>
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Name</span>
            <input
              type="text"
              required
              bind:value={formName}
              placeholder="e.g. Alpha B0 REV 1.2"
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden"
            />
          </label>
          <label>
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Revision</span>
            <input
              type="text"
              required
              bind:value={formRevision}
              placeholder="e.g. 1.2"
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden"
            />
          </label>
          <Select
            bind:value={formProductId}
            label="Product"
            placeholder="Select product..."
            options={products.map(p => ({ value: p.id, label: p.name }))}
          />
          <Select
            bind:value={formBoardRevisionId}
            label="Board Revision"
            placeholder={formProductId ? 'Select board revision...' : 'Select product first'}
            options={boardRevisions.map(r => ({ value: r.id, label: r.label }))}
            disabled={!formProductId}
            required
          />
          <label class="col-span-2">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Profile Template (JSON)</span>
            <textarea
              bind:value={formProfileTemplate}
              rows={6}
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 font-mono text-xs text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden"
            ></textarea>
          </label>
        </div>
        <div class="flex gap-2">
          <button
            type="submit"
            disabled={submitting}
            class="btn btn-sm btn-primary"
          >
            <Check size={16} />
            {submitting ? 'Saving...' : editingId ? 'Save changes' : 'Create'}
          </button>
          <button
            type="button"
            onclick={resetForm}
            class="btn btn-sm btn-ghost"
          >
            Cancel
          </button>
        </div>
      </form>
    </FormCard>
  {/if}

  {#if loading}
    <LoadingState message="Loading designs..." />
  {:else if designs.length === 0}
    <EmptyState message="No fixture designs yet" />
  {:else}
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr>
            <th class="table-header">Name</th>
            <th class="table-header">Revision</th>
            <th class="table-header">Board Revision</th>
            {#if canManage}
              <th class="table-header w-20"></th>
            {/if}
          </tr>
        </thead>
        <tbody>
          {#each designs as d (d.id)}
            <tr class="table-row">
              <td class="table-cell text-sm font-medium text-text-primary">{d.name}</td>
              <td class="table-cell text-sm text-text-secondary">{d.revision}</td>
              <td class="table-cell text-sm text-text-secondary">
                {d.boardRevision ? `${d.boardRevision.version} (${d.boardRevision.ckBoardsName})` : d.boardRevisionId}
              </td>
              {#if canManage}
                <td class="table-cell">
                  <div class="flex gap-1">
                    <button
                      onclick={() => startEdit(d)}
                      class="rounded-lg p-1.5 text-text-tertiary hover:text-text-primary"
                      title="Edit"
                      aria-label="Edit design"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      onclick={() => promptDelete(d.id)}
                      class="rounded-lg p-1.5 text-text-tertiary hover:text-error"
                      title="Delete"
                      aria-label="Delete design"
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

  <ConfirmDeleteDialog
    open={!!deleteTarget}
    entityType="fixture design"
    entityName={deleteTarget?.name || ''}
    onConfirm={() => { handleDelete(deleteTarget!.id); deleteTarget = null; }}
    onCancel={() => (deleteTarget = null)}
  />
</div>
