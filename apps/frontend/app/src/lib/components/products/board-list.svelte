<script lang="ts">
  import { Plus, Check, ChevronDown, ChevronRight, Pencil, Trash2 } from 'lucide-svelte';
  import { api, apiFetch } from '$lib/api';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import ConfirmDeleteDialog from '$lib/components/ui/confirm-delete-dialog.svelte';
  import BoardRevisionList from './board-revision-list.svelte';
  import type { Board } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  interface Props {
    productId: string;
    boards: Board[];
    canManage: boolean;
    onRefresh: () => void;
  }

  let { productId, boards, canManage, onRefresh }: Props = $props();

  let error = $state<string | null>(null);
  let showForm = $state(false);
  let editingId = $state<string | null>(null);
  let submitting = $state(false);
  let expandedBoards = $state(new Set<string>());
  let boardDetails = $state<Record<string, Board>>({});

  let formName = $state('');
  let formCkBoardsFamily = $state('');
  let formVendor = $state('corekinect');
  let formDescription = $state('');
  let formActive = $state(true);

  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  function resetForm() {
    formName = '';
    formCkBoardsFamily = '';
    formVendor = 'corekinect';
    formDescription = '';
    formActive = true;
    editingId = null;
    showForm = false;
  }

  function startEdit(b: Board) {
    formName = b.name;
    formCkBoardsFamily = b.ckBoardsFamily || '';
    formVendor = b.vendor || 'corekinect';
    formDescription = b.description || '';
    formActive = b.active;
    editingId = b.id;
    showForm = true;
  }

  async function toggleExpanded(boardId: string) {
    const next = new Set(expandedBoards);
    if (next.has(boardId)) {
      next.delete(boardId);
    } else {
      next.add(boardId);
      // Fetch board detail if not already loaded
      if (!boardDetails[boardId]) {
        await fetchBoardDetail(boardId);
      }
    }
    expandedBoards = next;
  }

  async function fetchBoardDetail(boardId: string) {
    try {
      const res = await apiFetch<ApiResponse<Board>>(`/v2/products/${productId}/boards/${boardId}`);
      boardDetails = { ...boardDetails, [boardId]: res.data };
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load board details';
    }
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    error = null;
    submitting = true;

    const body: Record<string, unknown> = {
      name: formName,
      ckBoardsFamily: formCkBoardsFamily || null,
      vendor: formVendor,
      description: formDescription || null,
      active: formActive,
    };

    try {
      const wasEditing = editingId;
      if (editingId) {
        await api.put(`/v2/products/${productId}/boards/${editingId}`, body);
      } else {
        await api.post(`/v2/products/${productId}/boards`, body);
      }
      resetForm();
      onRefresh();
      if (wasEditing) {
        const { [wasEditing]: _, ...rest } = boardDetails;
        boardDetails = rest;
      }
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to save board';
    } finally {
      submitting = false;
    }
  }

  function promptDelete(id: string) {
    const target = boards.find((b) => b.id === id);
    deleteTarget = { id, name: target?.name || '' };
  }

  async function handleDelete(id: string) {
    error = null;
    try {
      await api.delete(`/v2/products/${productId}/boards/${id}`);
      onRefresh();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete board';
    }
  }

  function handleRevisionRefresh(boardId: string) {
    fetchBoardDetail(boardId);
    onRefresh();
  }
</script>

<div>
  <ErrorAlert message={error} />

  <div class="mb-3 flex items-center justify-between">
    <h3 class="text-sm font-semibold text-text-primary">Boards</h3>
    {#if canManage && !showForm}
      <button
        onclick={() => { resetForm(); showForm = true; }}
        class="flex items-center gap-1.5 rounded-lg bg-accent px-2.5 py-1.5 text-2xs font-medium text-white hover:bg-accent-hover"
      >
        <Plus size={16} />
        Add board
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
            placeholder="e.g. Main Board"
            class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden"
          />
        </label>
        <label>
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Board Family</span>
          <input
            type="text"
            bind:value={formCkBoardsFamily}
            placeholder="e.g. alpha"
            class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm font-mono text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden"
          />
        </label>
        <label>
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Description</span>
          <input
            type="text"
            bind:value={formDescription}
            placeholder="Optional"
            class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden"
          />
        </label>
        <div class="flex items-end pb-1">
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

  {#if boards.length > 0}
    <div class="space-y-2">
      {#each boards as b (b.id)}
        {@const isExpanded = expandedBoards.has(b.id)}
        {@const detail = boardDetails[b.id]}
        <div class="rounded-lg border border-border bg-surface-0">
          <div class="flex items-center gap-3 px-3 py-2.5">
            <button
              onclick={() => toggleExpanded(b.id)}
              class="shrink-0 text-text-tertiary hover:text-text-primary"
              aria-label={isExpanded ? 'Collapse' : 'Expand'}
            >
              {#if isExpanded}
                <ChevronDown size={16} />
              {:else}
                <ChevronRight size={16} />
              {/if}
            </button>
            <button
              onclick={() => toggleExpanded(b.id)}
              class="flex-1 text-left"
            >
              <span class="font-semibold text-text-primary text-sm">{b.name}</span>
              {#if b.ckBoardsFamily}
                <span class="ml-2 font-mono text-2xs text-text-secondary">{b.ckBoardsFamily}</span>
              {/if}
              {#if b.description}
                <span class="ml-2 text-2xs text-text-tertiary">{b.description}</span>
              {/if}
            </button>
            <span
              class={[
                'inline-flex items-center rounded-full px-1.5 py-0.5 text-2xs font-medium',
                b.active ? 'bg-success-muted text-success' : 'bg-surface-2 text-text-tertiary'
              ].join(' ')}
            >
              {b.active ? 'Active' : 'Inactive'}
            </span>
            <span class="text-2xs text-text-tertiary">
              {b.revisionCount ?? 0} rev{(b.revisionCount ?? 0) !== 1 ? 's' : ''}
            </span>
            {#if canManage}
              <div class="flex gap-1">
                <button
                  onclick={(e) => { e.stopPropagation(); startEdit(b); }}
                  class="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
                  title="Edit"
                  aria-label="Edit"
                >
                  <Pencil size={14} />
                </button>
                <button
                  onclick={(e) => { e.stopPropagation(); promptDelete(b.id); }}
                  class="rounded p-1 text-text-tertiary hover:bg-error-muted hover:text-error"
                  title="Delete"
                  aria-label="Delete"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            {/if}
          </div>

          {#if isExpanded}
            <div class="border-t border-border-subtle px-4 py-3">
              {#if detail}
                <BoardRevisionList
                  {productId}
                  boardId={b.id}
                  revisions={detail.revisions || []}
                  {canManage}
                  onRefresh={() => handleRevisionRefresh(b.id)}
                />
              {:else}
                <div class="py-4 text-center text-sm text-text-tertiary">Loading...</div>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {:else}
    <div class="table-empty">
      No boards yet. Add a board to start managing revisions.
    </div>
  {/if}

  <ConfirmDeleteDialog
    open={!!deleteTarget}
    entityType="board"
    entityName={deleteTarget?.name || ''}
    onConfirm={() => { handleDelete(deleteTarget!.id); deleteTarget = null; }}
    onCancel={() => (deleteTarget = null)}
  />
</div>
