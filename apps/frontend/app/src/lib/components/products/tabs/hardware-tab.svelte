<script lang="ts">
  import { Cpu, Pencil, Check, X, CircuitBoard, Plus, AlertTriangle, FlaskConical, RefreshCw, Loader2, Radio, Layers } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import type { Product, BoardRevision, ProductTarget } from '$lib/types/models';
  import { api } from '$lib/api';
  import { formatTimeAgo } from '$lib/utils/formatting';

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

  // ── Build status per revision ───────────────────────────
  interface BuildRecord {
    id: string;
    status: string;
    branch?: string;
    commitSha?: string;
    versionString?: string;
    createdAt?: string;
    board?: string;
  }

  let latestBuilds = $state<BuildRecord[]>([]);
  let buildsLoading = $state(true);

  async function loadBuilds() {
    buildsLoading = true;
    try {
      const res = await api.get(`/v2/builds?productId=${product.id}&limit=50`);
      const data = (res as any)?.data?.data || [];
      latestBuilds = data;
    } catch {
      /* non-critical — build status is informational */
    }
    buildsLoading = false;
  }

  $effect(() => {
    if (product?.id) {
      loadBuilds();
      checkSyncAvailable();
    }
  });

  const buildByBoard = $derived.by(() => {
    const map = new Map<string, BuildRecord>();
    for (const build of latestBuilds) {
      const boardName = (build as any).board;
      if (boardName && !map.has(boardName)) {
        map.set(boardName, build);
      }
    }
    return map;
  });

  function latestBuildForRevision(rev: any): BuildRecord | null {
    const ckName = rev.ckBoardsName;
    if (!ckName) return null;
    return buildByBoard.get(ckName) ?? null;
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

  let cascadeMessage = $state<string | null>(null);

  async function changeStatus(rev: { id: string; boardId: string }, newStatus: string): Promise<void> {
    changingStatusId = rev.id;
    error = null;
    cascadeMessage = null;
    try {
      const res = await api.put(
        `/v2/products/${product.id}/boards/${rev.boardId}/revisions/${rev.id}`,
        { status: newStatus }
      );
      const data = (res as any)?.data ?? res;
      if (data?.disabledStages?.length) {
        const names = data.disabledStages.map((s: any) => s.name).join(', ');
        cascadeMessage = `Disabled ${data.disabledStages.length} linked stage(s): ${names}`;
      }
      onRefresh();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to change status';
    } finally {
      changingStatusId = null;
    }
  }

  // ── Sync from ck_boards ─────────────────────────────────
  let syncing = $state(false);
  let syncAvailable = $state(true);
  let syncResult = $state<{ synced: number; added: { version: string }[] } | null>(null);

  // Check if sync service is available on mount
  async function checkSyncAvailable(): Promise<void> {
    try {
      const res = await api.get('/v2/products/boards/branches');
      syncAvailable = true;
    } catch {
      syncAvailable = false;
    }
  }

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

{#if cascadeMessage}
  <div class="mb-4 rounded-lg border border-warning/30 bg-warning-muted px-4 py-3">
    <p class="text-sm font-medium text-warning">{cascadeMessage}</p>
    <p class="text-2xs text-text-tertiary mt-0.5">Re-enable stages from the Validation tab after reactivating this revision.</p>
  </div>
{/if}

<div class="flex items-center justify-between mb-4">
  <h3 class="text-sm font-semibold text-text-primary">Board Revisions</h3>
  <div class="flex items-center gap-2">
    {#if canManage && board}
      <button
        onclick={syncFromRepo}
        disabled={syncing || !syncAvailable}
        class="btn btn-sm btn-secondary"
        title={syncAvailable ? 'Sync hardware revisions from ck_boards main branch' : 'Board discovery unavailable — BITBUCKET_SSH_KEY not configured'}
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
      <button onclick={() => (showAddForm = false)} class="btn btn-sm btn-icon btn-ghost">
        <X size={14} />
      </button>
    </div>
    <div class="grid gap-3 sm:grid-cols-3">
      <label class="block">
        <span class="mb-1 block text-2xs font-medium text-text-tertiary">Version *</span>
        <input type="text" bind:value={addVersion} placeholder="e.g. C0" class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-hidden" />
      </label>
      <label class="block">
        <span class="mb-1 block text-2xs font-medium text-text-tertiary">Board Name *</span>
        <input type="text" bind:value={addCkBoardsName} placeholder="e.g. alpha_c0" class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-hidden" />
      </label>
      <label class="block">
        <span class="mb-1 block text-2xs font-medium text-text-tertiary">SoCs (comma-separated)</span>
        <input type="text" bind:value={addSocs} placeholder="nrf52840, nrf9151" class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-hidden" />
      </label>
    </div>
    <div class="flex justify-end gap-2">
      <button onclick={() => (showAddForm = false)} class="btn btn-sm btn-ghost">Cancel</button>
      <button onclick={addRevision} disabled={addingRevision || !addVersion.trim() || !addCkBoardsName.trim()} class="btn btn-sm btn-primary">
        {addingRevision ? 'Adding...' : 'Add Revision'}
      </button>
    </div>
  </div>
{/if}

<!-- Revision list -->
{#if allRevisions.length === 0}
  <div class="py-8 text-center">
    <CircuitBoard size={32} class="mx-auto text-text-tertiary mb-3 opacity-50" />
    <p class="text-sm text-text-secondary">No hardware revisions</p>
    <p class="text-2xs text-text-tertiary mt-1">Add a revision manually or sync from ck_boards to get started.</p>
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
                <button onclick={cancelEdit} class="btn btn-sm btn-icon btn-ghost" title="Cancel" aria-label="Cancel editing revision">
                  <X size={14} />
                </button>
                <button onclick={saveEdit} disabled={savingRevision} class="btn btn-sm btn-icon btn-ghost text-accent" title="Save" aria-label="Save revision">
                  <Check size={14} />
                </button>
              </div>
            </div>
            <div class="grid gap-3 sm:grid-cols-2">
              <label class="block">
                <span class="mb-1 block text-2xs font-medium text-text-tertiary">Device Type</span>
                <input type="number" min="0" bind:value={editRevDeviceType} class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-hidden" />
              </label>
              <label class="block">
                <span class="mb-1 block text-2xs font-medium text-text-tertiary">Device Variant</span>
                <input type="number" min="0" bind:value={editRevDeviceVariant} class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-hidden" />
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
                    <input type="number" min="0" bind:value={target.appId} class="w-20 rounded border border-border bg-surface-0 px-2 py-1 text-xs font-mono text-text-primary focus:border-accent focus:outline-hidden" />
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
                    class="btn btn-sm bg-success-muted text-success hover:bg-success/20">
                    Activate
                  </button>
                {:else if rev.status === 'ACTIVE'}
                  {@const activeStages = stagesUsingRevision(rev.id)}
                  <button onclick={() => {
                    if (activeStages.length > 0) {
                      if (!confirm(`This will disable ${activeStages.length} active stage(s): ${activeStages.join(', ')}.\n\nDeprecate ${rev.version}?`)) return;
                    }
                    changeStatus(rev, 'DEPRECATED');
                  }} disabled={changingStatusId === rev.id}
                    class="btn btn-sm bg-warning-muted text-warning hover:bg-warning/20">
                    {#if activeStages.length > 0}<AlertTriangle size={10} />{/if}
                    Deprecate
                  </button>
                {:else if rev.status === 'DEPRECATED'}
                  <button onclick={() => changeStatus(rev, 'ACTIVE')} disabled={changingStatusId === rev.id}
                    class="btn btn-sm bg-success-muted text-success hover:bg-success/20 mr-1">
                    Reactivate
                  </button>
                  <button onclick={() => {
                    if (!confirm(`End-of-life ${rev.version}? This permanently marks the revision as unsupported. Builds and validation will no longer target it.`)) return;
                    changeStatus(rev, 'EOL');
                  }} disabled={changingStatusId === rev.id}
                    class="btn btn-sm bg-error-muted text-error hover:bg-error/20">
                    EOL
                  </button>
                {/if}
                <button onclick={() => startEdit(rev)} title="Edit revision config" aria-label="Edit revision config"
                  class="btn btn-sm btn-icon btn-ghost">
                  <Pencil size={14} />
                </button>
              {/if}
            </div>
          </div>

          <!-- Target chips -->
          {#if rev.targets && rev.targets.length > 0}
            <div class="flex flex-wrap items-center gap-1.5 mb-3">
              {#each sortedTargets(rev.targets) as target}
                <span class="inline-flex items-center gap-1 rounded-full bg-surface-2 px-2 py-0.5 text-2xs">
                  <Cpu size={10} class="text-accent" />
                  <span class="font-medium capitalize text-text-primary">{target.role}</span>
                  <span class="text-text-tertiary">:</span>
                  <span class="font-mono text-text-secondary">{target.soc}</span>
                  <span class="text-text-tertiary ml-0.5">#{target.appId}</span>
                </span>
              {/each}
            </div>
          {/if}

          <!-- Info row -->
          <div class="flex flex-wrap items-center gap-3 text-2xs text-text-secondary">
            <span>DeviceType <span class="font-mono text-text-primary">{rev.deviceType ?? '—'}</span></span>
            <span>Variant <span class="font-mono text-text-primary">{rev.deviceVariant ?? '—'}</span></span>
            {#if rev.modemFirmwares?.length}
              <span class="flex items-center gap-1">
                <Radio size={10} class="text-text-tertiary" />
                {rev.modemFirmwares.length} modem fw
              </span>
            {/if}
            {#if stagesUsingRevision(rev.id).length > 0}
              <span class="flex items-center gap-1">
                <Layers size={10} class="text-text-tertiary" />
                {stagesUsingRevision(rev.id).length} stage{stagesUsingRevision(rev.id).length === 1 ? '' : 's'}
              </span>
            {/if}
          </div>

          <!-- Latest build -->
          {@const latestBuild = latestBuildForRevision(rev)}
          <div class="mt-2 flex items-center gap-2">
            {#if latestBuild}
              <a href="/builds" class="inline-flex items-center gap-1.5 rounded-md bg-surface-2 px-2 py-0.5 text-2xs hover:bg-surface-3 transition-colors no-underline">
                <StatusBadge status={latestBuild.status} />
                {#if latestBuild.branch}
                  <span class="text-text-secondary font-mono truncate max-w-24">{latestBuild.branch}</span>
                {/if}
                {#if latestBuild.createdAt}
                  <span class="text-text-tertiary">{formatTimeAgo(latestBuild.createdAt)}</span>
                {/if}
              </a>
            {:else if !buildsLoading}
              <span class="text-2xs text-text-tertiary">No builds</span>
            {/if}
          </div>

          <!-- Linked stages detail -->
          {#if stagesUsingRevision(rev.id).length > 0}
            <div class="mt-2 flex items-center gap-2 text-2xs text-text-tertiary">
              <FlaskConical size={12} />
              <span>Used by: {stagesUsingRevision(rev.id).join(', ')}</span>
            </div>
          {/if}
        {/if}
      </div>
    {/each}
  </div>
{/if}
