<script lang="ts">
  import { Cpu, Pencil, Check, X, CircuitBoard, Plus, AlertTriangle, FlaskConical, RefreshCw, Loader2 } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import type { Product, BoardRevision, ProductTarget } from '$lib/types/models';
  import { api } from '$lib/api';

  interface Props {
    product: Product;
    canManage: boolean;
    onRefresh: () => void;
  }

  let { product, canManage, onRefresh }: Props = $props();

  let error = $state<string | null>(null);

  // ── Computed ────────────────────────────────────────────
  const boards = $derived(product.boards || []);
  const board = $derived(boards[0]); // products have exactly one board
  const allRevisions = $derived(
    boards.flatMap((b) =>
      (b.revisions || []).map((r) => ({ ...r, boardId: b.id }))
    )
  );
  const stageConfigs = $derived((product as any).stageConfigs || []);

  function sortedTargets(targets: ProductTarget[]): ProductTarget[] {
    return [...targets].sort((a, b) => (a.role === 'app' ? -1 : b.role === 'app' ? 1 : 0));
  }

  function stagesUsingRevision(revId: string): string[] {
    return stageConfigs
      .filter((s: any) => s.boardRevisionId === revId && s.enabled)
      .map((s: any) => s.name);
  }

  // ── Edit revision ──────────────────────────────────────
  let editingRevisionId = $state<string | null>(null);
  let editRevDeviceType = $state<number>(0);
  let editRevDeviceVariant = $state<number>(0);
  let editRevTargets = $state<{ id: string; role: string; soc: string; appId: number }[]>([]);
  let savingRevision = $state(false);

  function startEdit(rev: BoardRevision): void {
    editingRevisionId = rev.id;
    editRevDeviceType = rev.deviceType ?? 0;
    editRevDeviceVariant = rev.deviceVariant ?? 0;
    editRevTargets = (rev.targets || []).map((t) => ({
      id: t.id, role: t.role, soc: t.soc, appId: t.appId,
    }));
    error = null;
  }

  function cancelEdit(): void {
    editingRevisionId = null;
    error = null;
  }

  async function saveEdit(): Promise<void> {
    if (!editingRevisionId || !board) return;
    savingRevision = true;
    error = null;
    try {
      await api.put(
        `/v2/products/${product.id}/boards/${board.id}/revisions/${editingRevisionId}`,
        { deviceType: editRevDeviceType, deviceVariant: editRevDeviceVariant }
      );
      for (const target of editRevTargets) {
        await api.put(
          `/v2/products/${product.id}/boards/${board.id}/revisions/${editingRevisionId}/targets/${target.id}`,
          { role: target.role, soc: target.soc, appId: target.appId }
        );
      }
      editingRevisionId = null;
      onRefresh();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to save revision';
    } finally {
      savingRevision = false;
    }
  }

  // ── Status transitions ─────────────────────────────────
  let changingStatusId = $state<string | null>(null);

  async function changeStatus(rev: { id: string; boardId: string }, newStatus: string): Promise<void> {
    changingStatusId = rev.id;
    error = null;
    try {
      await api.put(
        `/v2/products/${product.id}/boards/${rev.boardId}/revisions/${rev.id}`,
        { status: newStatus }
      );
      onRefresh();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to change status';
    } finally {
      changingStatusId = null;
    }
  }

  // ── Sync from ck_boards ─────────────────────────────────
  let syncing = $state(false);
  let syncResult = $state<{ synced: number; added: { version: string }[] } | null>(null);

  async function syncFromRepo(): Promise<void> {
    syncing = true;
    error = null;
    syncResult = null;
    try {
      const res = await api.post(`/v2/products/${product.id}/sync-revisions`, {});
      syncResult = (res as any).data ?? res;
      if ((syncResult?.synced ?? 0) > 0) {
        onRefresh();
      }
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to sync revisions';
    } finally {
      syncing = false;
    }
  }

  // ── Add revision ───────────────────────────────────────
  let showAddForm = $state(false);
  let addVersion = $state('');
  let addCkBoardsName = $state('');
  let addSocs = $state('');
  let addingRevision = $state(false);

  async function addRevision(): Promise<void> {
    if (!board || !addVersion.trim() || !addCkBoardsName.trim()) return;
    addingRevision = true;
    error = null;
    try {
      await api.post(`/v2/products/${product.id}/boards/${board.id}/revisions`, {
        version: addVersion.trim(),
        ckBoardsName: addCkBoardsName.trim(),
        socs: addSocs.split(',').map((s) => s.trim()).filter(Boolean),
        status: 'DRAFT',
      });
      showAddForm = false;
      addVersion = '';
      addCkBoardsName = '';
      addSocs = '';
      onRefresh();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to add revision';
    } finally {
      addingRevision = false;
    }
  }
</script>

<ErrorAlert message={error} />

<div class="flex items-center justify-between mb-4">
  <h3 class="text-sm font-semibold text-text-primary">Board Revisions</h3>
  <div class="flex items-center gap-2">
    {#if canManage && board}
      <button
        onclick={syncFromRepo}
        disabled={syncing}
        class="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-2xs font-medium text-text-secondary hover:bg-surface-2 hover:text-text-primary transition-colors disabled:opacity-50"
        title="Sync hardware revisions from ck_boards main branch"
      >
        {#if syncing}
          <Loader2 size={12} class="animate-spin" />
        {:else}
          <RefreshCw size={12} />
        {/if}
        Sync from ck_boards
      </button>
      {#if !showAddForm}
        <button onclick={() => (showAddForm = true)} class="btn btn-sm btn-primary">
          <Plus size={14} /> Add Revision
        </button>
      {/if}
    {/if}
  </div>
</div>

<!-- Sync result notification -->
{#if syncResult}
  <div class="mb-4 rounded-lg border px-4 py-3 {syncResult.synced > 0 ? 'border-success/30 bg-success-muted' : 'border-border bg-surface-0'}">
    {#if syncResult.synced > 0}
      <p class="text-sm font-medium text-success">
        Added {syncResult.synced} new revision{syncResult.synced > 1 ? 's' : ''}: {syncResult.added.map(r => r.version).join(', ')}
      </p>
      <p class="text-2xs text-text-tertiary mt-0.5">AppIDs are set to 0 — update them using the edit button.</p>
    {:else}
      <p class="text-sm text-text-secondary">All revisions are up to date with ck_boards.</p>
    {/if}
  </div>
{/if}

<!-- Add revision form -->
{#if showAddForm && canManage}
  <div class="mb-4 rounded-lg border border-accent/30 bg-accent-muted p-4 space-y-3">
    <div class="flex items-center justify-between">
      <span class="text-sm font-medium text-text-primary">New Revision</span>
      <button onclick={() => (showAddForm = false)} class="rounded p-1 text-text-tertiary hover:text-text-primary">
        <X size={14} />
      </button>
    </div>
    <div class="grid gap-3 sm:grid-cols-3">
      <label class="block">
        <span class="mb-1 block text-2xs font-medium text-text-tertiary">Version *</span>
        <input type="text" bind:value={addVersion} placeholder="e.g. C0" class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none" />
      </label>
      <label class="block">
        <span class="mb-1 block text-2xs font-medium text-text-tertiary">Board Name *</span>
        <input type="text" bind:value={addCkBoardsName} placeholder="e.g. alpha_c0" class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-none" />
      </label>
      <label class="block">
        <span class="mb-1 block text-2xs font-medium text-text-tertiary">SoCs (comma-separated)</span>
        <input type="text" bind:value={addSocs} placeholder="nrf52840, nrf9151" class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-none" />
      </label>
    </div>
    <div class="flex justify-end gap-2">
      <button onclick={() => (showAddForm = false)} class="btn btn-sm">Cancel</button>
      <button onclick={addRevision} disabled={addingRevision || !addVersion.trim() || !addCkBoardsName.trim()} class="btn btn-sm btn-primary">
        {addingRevision ? 'Adding...' : 'Add Revision'}
      </button>
    </div>
  </div>
{/if}

<!-- Revision list -->
{#if allRevisions.length === 0}
  <div class="py-8 text-center text-sm text-text-tertiary">
    No hardware revisions. Add one to get started.
  </div>
{:else}
  <div class="space-y-3">
    {#each allRevisions as rev}
      <div class="rounded-lg border border-border bg-surface-0 p-4">
        {#if editingRevisionId === rev.id}
          <!-- Edit mode -->
          <div class="space-y-3">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <CircuitBoard size={16} class="text-accent" />
                <span class="text-sm font-semibold text-text-primary">{rev.version}</span>
                <StatusBadge status={rev.status} />
              </div>
              <div class="flex items-center gap-1">
                <button onclick={cancelEdit} class="rounded p-1 text-text-tertiary hover:text-text-primary" title="Cancel" aria-label="Cancel editing revision">
                  <X size={14} />
                </button>
                <button onclick={saveEdit} disabled={savingRevision} class="rounded p-1 text-accent hover:bg-accent/10 disabled:opacity-50" title="Save" aria-label="Save revision">
                  <Check size={14} />
                </button>
              </div>
            </div>
            <div class="grid gap-3 sm:grid-cols-2">
              <label class="block">
                <span class="mb-1 block text-2xs font-medium text-text-tertiary">Device Type</span>
                <input type="number" min="0" bind:value={editRevDeviceType} class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-none" />
              </label>
              <label class="block">
                <span class="mb-1 block text-2xs font-medium text-text-tertiary">Device Variant</span>
                <input type="number" min="0" bind:value={editRevDeviceVariant} class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-none" />
              </label>
            </div>
            <div class="space-y-2">
              <span class="text-2xs font-medium text-text-tertiary">Targets</span>
              {#each [...editRevTargets].sort((a, b) => a.role === 'app' ? -1 : b.role === 'app' ? 1 : 0) as target}
                <div class="flex items-center gap-3 rounded border border-border-subtle bg-surface-1 px-3 py-2">
                  <Cpu size={14} class="text-accent shrink-0" />
                  <span class="text-sm font-medium capitalize text-text-primary w-16">{target.role}</span>
                  <span class="font-mono text-2xs text-text-tertiary">{target.soc}</span>
                  <div class="flex-1"></div>
                  <label class="flex items-center gap-1.5">
                    <span class="text-2xs text-text-tertiary">AppID</span>
                    <input type="number" min="0" bind:value={target.appId} class="w-20 rounded border border-border bg-surface-0 px-2 py-1 text-xs font-mono text-text-primary focus:border-accent focus:outline-none" />
                  </label>
                </div>
              {/each}
            </div>
          </div>
        {:else}
          <!-- Read mode -->
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2">
              <CircuitBoard size={16} class="text-accent" />
              <span class="text-sm font-semibold text-text-primary">{rev.version}</span>
              <StatusBadge status={rev.status} />
              <span class="font-mono text-2xs text-text-tertiary">{rev.ckBoardsName}</span>
            </div>
            <div class="flex items-center gap-1">
              {#if canManage}
                <!-- Status actions -->
                {#if rev.status === 'DRAFT'}
                  <button onclick={() => changeStatus(rev, 'ACTIVE')} disabled={changingStatusId === rev.id}
                    class="rounded-md bg-success-muted px-2.5 py-1 text-2xs font-medium text-success hover:bg-success/20 disabled:opacity-50">
                    Activate
                  </button>
                {:else if rev.status === 'ACTIVE'}
                  <button onclick={() => changeStatus(rev, 'DEPRECATED')} disabled={changingStatusId === rev.id}
                    class="rounded-md bg-warning-muted px-2.5 py-1 text-2xs font-medium text-warning hover:bg-warning/20 disabled:opacity-50">
                    Deprecate
                  </button>
                {:else if rev.status === 'DEPRECATED'}
                  <button onclick={() => changeStatus(rev, 'ACTIVE')} disabled={changingStatusId === rev.id}
                    class="rounded-md bg-success-muted px-2.5 py-1 text-2xs font-medium text-success hover:bg-success/20 disabled:opacity-50 mr-1">
                    Reactivate
                  </button>
                  <button onclick={() => changeStatus(rev, 'EOL')} disabled={changingStatusId === rev.id}
                    class="rounded-md bg-error-muted px-2.5 py-1 text-2xs font-medium text-error hover:bg-error/20 disabled:opacity-50">
                    EOL
                  </button>
                {/if}
                <button onclick={() => startEdit(rev)} title="Edit revision config" aria-label="Edit revision config"
                  class="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary ml-1">
                  <Pencil size={14} />
                </button>
              {/if}
            </div>
          </div>

          <!-- Info row -->
          <div class="flex items-center gap-4 text-2xs text-text-secondary mb-3">
            <span>DeviceType <span class="font-mono text-text-primary">{rev.deviceType ?? '—'}</span></span>
            <span>Variant <span class="font-mono text-text-primary">{rev.deviceVariant ?? '—'}</span></span>
            {#if rev.socs?.length}
              <span>SoCs: <span class="font-mono text-text-primary">{rev.socs.join(', ')}</span></span>
            {/if}
          </div>

          <!-- Targets -->
          {#if rev.targets && rev.targets.length > 0}
            <div class="space-y-1.5">
              {#each sortedTargets(rev.targets) as target}
                <div class="flex items-center gap-3 rounded border border-border-subtle bg-surface-1 px-3 py-2">
                  <Cpu size={14} class="text-accent" />
                  <span class="text-sm font-medium capitalize text-text-primary">{target.role}</span>
                  <span class="font-mono text-2xs text-text-secondary">{target.soc}</span>
                  <div class="flex-1"></div>
                  <span class="font-mono text-2xs text-text-tertiary">AppID {target.appId}</span>
                </div>
              {/each}
            </div>
          {/if}

          <!-- Linked stages -->
          {@const linkedStages = stagesUsingRevision(rev.id)}
          {#if linkedStages.length > 0}
            <div class="mt-3 flex items-center gap-2 text-2xs text-text-tertiary">
              <FlaskConical size={12} />
              <span>Used by: {linkedStages.join(', ')}</span>
            </div>
          {/if}
        {/if}
      </div>
    {/each}
  </div>
{/if}
