<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import {
    ChevronLeft, Pencil, Trash2, Check, X, Loader2,
    Wifi, WifiOff, Cable, Clock, History, Factory, FlaskConical,
    Lock, AlertTriangle, Archive,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import { createPollingInterval } from '$lib/hooks/use-polling.svelte';
  import { PageHeader, ErrorAlert, LoadingState, EmptyState } from '$lib/components/ui';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import Tabs from '$lib/components/ui/tabs.svelte';
  import SelectionBar from '$lib/components/ui/selection-bar.svelte';
  import FixtureLayoutGrid from '$lib/components/fixtures/fixture-layout-grid.svelte';
  import SlotAssignmentPopover from '$lib/components/fixtures/slot-assignment-popover.svelte';
  import type { Fixture, FixtureSlot, ConcordNode } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('fixtures:manage'));
  const fixtureId = $derived($page.params.id);

  let fixture = $state<Fixture | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let activeTab = $state('slots');

  // Edit state
  let editing = $state(false);
  let editName = $state('');
  let editDescription = $state('');
  let editActive = $state(true);
  let editPurpose = $state<'DEV' | 'RELEASE'>('RELEASE');
  let saving = $state(false);

  // Delete state
  let showDeleteConfirm = $state(false);
  let deleting = $state(false);

  // Slot assignment
  let availableNodes = $state<ConcordNode[]>([]);

  // Slot popover
  let popoverSlot = $state<FixtureSlot | null>(null);
  let popoverOpen = $state(false);

  function openSlotPopover(slotIndex: number) {
    if (!fixture) return;
    const slot = (fixture.slots ?? []).find((s) => s.slotIndex === slotIndex);
    if (slot) {
      popoverSlot = slot;
      popoverOpen = true;
    }
  }

  function closeSlotPopover() {
    popoverOpen = false;
    popoverSlot = null;
  }

  // Sessions history
  let sessions = $state<any[]>([]);
  let sessionsLoading = $state(false);

  // Audit history
  let auditEntries = $state<any[]>([]);
  let auditLoading = $state(false);

  // Session selection (batch actions)
  let selectedSessionIds = $state<Set<string>>(new Set());
  let batchLoading = $state(false);

  function toggleSession(id: string) {
    const next = new Set(selectedSessionIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    selectedSessionIds = next;
  }

  function selectAllSessions() {
    selectedSessionIds = new Set(sessions.map((s: any) => s.id));
  }

  function clearSessionSelection() {
    selectedSessionIds = new Set();
  }

  let confirmBatchDelete = $state(false);

  async function batchAction(action: 'archive' | 'delete') {
    if (selectedSessionIds.size === 0) return;

    // Delete always requires confirmation
    if (action === 'delete' && !confirmBatchDelete) {
      confirmBatchDelete = true;
      return;
    }
    confirmBatchDelete = false;

    batchLoading = true;
    error = null;
    try {
      const res = await api.post<ApiResponse<any>>('/v2/manufacturing/sessions/batch', {
        action,
        sessionIds: [...selectedSessionIds],
      });
      const result = res.data;
      if (result.failed?.length > 0) {
        error = `${result.succeeded.length} ${action}d, ${result.failed.length} failed: ${result.failed[0].reason}`;
      }
      selectedSessionIds = new Set();
      fetchSessions();
      fetchFixture();
    } catch (err: any) {
      error = err instanceof Error ? err.message : `Batch ${action} failed`;
    } finally {
      batchLoading = false;
    }
  }

  async function fetchFixture() {
    try {
      const res = await apiFetch<ApiResponse<Fixture>>(`/v2/fixtures/${fixtureId}`);
      fixture = res.data;
    } catch (err: any) {
      error = err instanceof Error ? err.message : 'Failed to load fixture';
    } finally {
      loading = false;
    }
  }

  async function fetchAvailableNodes() {
    if (!fixture) return;
    try {
      const res = await apiFetch<ApiResponse<{ data: ConcordNode[] }>>('/v2/devices/mtibs');
      const allNodes = res.data.data || res.data;
      availableNodes = (allNodes as ConcordNode[]).filter(
        n => n.type === fixture!.type && !n.fixtureSlot
      );
    } catch { /* non-critical */ }
  }

  async function fetchSessions() {
    sessionsLoading = true;
    try {
      const res = await apiFetch<ApiResponse<any>>(`/v2/manufacturing/sessions?fixtureId=${fixtureId}&limit=50`);
      const payload = res.data;
      sessions = Array.isArray(payload) ? payload : (payload as any)?.data ?? [];
    } catch { sessions = []; }
    finally { sessionsLoading = false; }
  }

  async function fetchAuditHistory() {
    auditLoading = true;
    try {
      const res = await apiFetch<ApiResponse<any>>(`/v2/system/history/entity/Fixture/${fixtureId}`);
      const payload = res.data;
      auditEntries = Array.isArray(payload) ? payload : (payload as any)?.data ?? [];
    } catch { auditEntries = []; }
    finally { auditLoading = false; }
  }

  // Slot assign/unassign
  async function handleAssign(slotId: string, nodeId: string) {
    error = null;
    try {
      await api.post(`/v2/fixtures/${fixtureId}/slots/${slotId}/assign`, { nodeId });
      fetchFixture();
      fetchAvailableNodes();
    } catch (err: any) {
      error = err instanceof Error ? err.message : 'Failed to assign node';
    }
  }

  async function handleUnassign(slotId: string) {
    error = null;
    try {
      await api.post(`/v2/fixtures/${fixtureId}/slots/${slotId}/assign`, { nodeId: null });
      fetchFixture();
      fetchAvailableNodes();
    } catch (err: any) {
      error = err instanceof Error ? err.message : 'Failed to unassign node';
    }
  }

  // Edit
  function startEdit() {
    if (!fixture) return;
    editName = fixture.name;
    editDescription = fixture.description || '';
    editActive = fixture.active;
    editPurpose = (fixture.purpose ?? 'RELEASE') as 'DEV' | 'RELEASE';
    editing = true;
  }

  async function saveEdit() {
    if (!fixture) return;
    saving = true;
    error = null;
    try {
      const payload: Record<string, unknown> = {
        name: editName.trim(),
        description: editDescription.trim() || null,
        active: editActive,
      };
      // Only include purpose when it's actually changing — backend
      // refuses purpose flips on a locked fixture, and we want a
      // no-op edit (e.g. just renaming) to succeed even mid-session.
      if (editPurpose !== fixture.purpose) {
        payload.purpose = editPurpose;
      }
      await api.put(`/v2/fixtures/${fixtureId}`, payload);
      editing = false;
      fetchFixture();
    } catch (err: any) {
      error = err instanceof Error ? err.message : 'Failed to update';
    } finally { saving = false; }
  }

  const purposeLocked = $derived(fixture?.lockState === 'IN_USE');

  // Delete
  async function handleDelete() {
    deleting = true;
    error = null;
    try {
      await api.delete(`/v2/fixtures/${fixtureId}`);
      goto('/fixtures');
    } catch (err: any) {
      error = err instanceof Error ? err.message : 'Failed to delete';
      showDeleteConfirm = false;
    } finally { deleting = false; }
  }

  const slots = $derived(fixture?.slots ?? []);
  const assignedCount = $derived(slots.filter(s => s.nodeId).length);
  /** Slots whose live MTIB state is READY — single source of truth.
   *  Replaces the old "online" counter that read ``node.status`` from
   *  a now-deleted DB column. */
  const readyCount = $derived(
    slots.filter(s => s.mtibStatus?.state === 'READY').length
  );

  // Map fixture slots into the layout-grid's expected shape. ``mtibStatus``
  // (live: READY/DEPLOYING/NOT_DEPLOYED/PROBE_FAILED/DISABLED) is the
  // single source of truth for slot tile colours and slot modal pills.
  const layoutSlots = $derived(
    slots.map((s) => ({
      id: s.id,
      slotIndex: s.slotIndex,
      label: s.label,
      node: s.node ?? null,
      mtibStatus: s.mtibStatus ?? null,
      mtibReady: s.mtibStatus?.state === 'READY',
    }))
  );

  const hasStandaloneSlot = $derived(
    Boolean((fixture?.metadata as Record<string, unknown> | null)?.hasStandaloneSlot)
  );

  // Map fixture.health → StatusBadge-supported status string.
  const healthBadge = $derived(fixture?.health ?? 'UNASSIGNED');

  // Load data on tab switch
  $effect(() => {
    if (activeTab === 'sessions' && sessions.length === 0 && !sessionsLoading) fetchSessions();
    if (activeTab === 'history' && auditEntries.length === 0 && !auditLoading) fetchAuditHistory();
  });

  // ── Auto-refresh ────────────────────────────────────────────
  // No node-health WS channel exists today (observability_ws.py only
  // streams per-node power/GPIO/ADC samples, not slot.mtibStatus
  // transitions). A 5s poll on GET /v2/fixtures/{id} keeps the slot
  // tile colours, the assignability banner, and the readyCount stat
  // in sync without sustaining an extra socket per fixture page. The
  // poll silently no-ops when the tab is backgrounded.
  const REFRESH_INTERVAL_MS = 5000;
  const refreshPoller = createPollingInterval(
    () => { void fetchFixture(); },
    REFRESH_INTERVAL_MS,
  );

  onMount(() => {
    if (!auth.hasPermission('fixtures:view')) { goto('/'); return; }
    fetchFixture().then(() => {
      if (canManage) fetchAvailableNodes();
      refreshPoller.start();
    });
    // Sessions populate the headline stat card. Lazy-loading them on tab
    // switch leaves the card stuck at "—" even when the fixture has been
    // used many times — fetch upfront so the number lands with the page.
    fetchSessions();
  });

  onDestroy(() => {
    refreshPoller.stop();
  });

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  }

  function relativeTime(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }
</script>

<svelte:head>
  <title>{fixture?.name ?? 'Fixture'} — Fixtures — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  {#if loading}
    <LoadingState message="Loading fixture..." />
  {:else if !fixture}
    <EmptyState message="Fixture not found." />
  {:else}
    <!-- Back + Header -->
    <div class="mb-6">
      <a href="/fixtures" class="inline-flex items-center gap-1 text-sm text-text-tertiary hover:text-text-secondary mb-4">
        <ChevronLeft size={16} /> Fixtures
      </a>

      <div class="flex items-start justify-between">
        <div class="flex-1">
          {#if editing}
            <div class="space-y-3 max-w-lg">
              <input type="text" bind:value={editName} class="input input-md w-full" placeholder="Fixture name" />
              <input type="text" bind:value={editDescription} class="input input-sm w-full" placeholder="Description (optional)" />
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" bind:checked={editActive} class="h-4 w-4 rounded border-border text-accent" />
                <span class="text-sm text-text-secondary">Active</span>
              </label>

              <div>
                <span class="text-xs uppercase tracking-wide text-text-tertiary">Purpose</span>
                <div class="mt-1 inline-flex rounded-md border border-border overflow-hidden">
                  <button
                    type="button"
                    onclick={() => (editPurpose = 'RELEASE')}
                    disabled={purposeLocked}
                    class={`px-3 py-1 text-sm ${editPurpose === 'RELEASE' ? 'bg-accent text-text-inverse' : 'text-text-secondary hover:bg-surface-2'} ${purposeLocked ? 'opacity-60 cursor-not-allowed' : ''}`}
                  >
                    Release
                  </button>
                  <button
                    type="button"
                    onclick={() => (editPurpose = 'DEV')}
                    disabled={purposeLocked}
                    class={`px-3 py-1 text-sm border-l border-border ${editPurpose === 'DEV' ? 'bg-accent text-text-inverse' : 'text-text-secondary hover:bg-surface-2'} ${purposeLocked ? 'opacity-60 cursor-not-allowed' : ''}`}
                  >
                    Dev
                  </button>
                </div>
                <p class="mt-1 text-2xs text-text-tertiary">
                  {#if editPurpose === 'RELEASE'}
                    Production rig — only released test packages run here.
                  {:else}
                    Sandbox — runs both released and development packages.
                  {/if}
                  {#if purposeLocked}
                    <span class="text-warning">Locked while a session is active.</span>
                  {/if}
                </p>
              </div>

              <div class="flex items-center gap-2">
                <button onclick={saveEdit} disabled={saving || !editName.trim()} class="btn btn-sm btn-primary">
                  {#if saving}<Loader2 size={14} class="animate-spin" />{:else}<Check size={14} />{/if} Save
                </button>
                <button onclick={() => editing = false} class="btn btn-sm btn-ghost">Cancel</button>
              </div>
            </div>
          {:else}
            <div class="flex items-center gap-3">
              <h1 class="text-xl font-semibold text-text-primary">{fixture.name}</h1>
              <StatusBadge status={fixture.type} />
              <StatusBadge status={fixture.purpose === 'DEV' ? 'DEV' : 'RELEASE'} />
              <StatusBadge status={fixture.active ? 'ACTIVE' : 'INACTIVE'} />
              {#if fixture.lockState === 'IN_USE'}
                <StatusBadge status="IN_USE" />
              {:else if fixture.lockState === 'MAINTENANCE'}
                <StatusBadge status="MAINTENANCE" />
              {/if}
            </div>
            {#if fixture.description}
              <p class="mt-1 text-sm text-text-secondary">{fixture.description}</p>
            {/if}
            <p class="mt-1 text-2xs text-text-tertiary">
              Product: <span class="text-text-secondary">{fixture.productName || '—'}</span>
              {#if fixture.boardRevision}
                <span class="mx-1">·</span> Rev: <span class="text-text-secondary">{fixture.boardRevision.version}</span>
              {/if}
              {#if fixture.design}
                <span class="mx-1">·</span> Design: <span class="text-text-secondary">{fixture.design.name}</span>
              {/if}
            </p>
          {/if}
        </div>

        {#if canManage && !editing}
          <div class="flex items-center gap-2">
            <button onclick={startEdit} class="btn btn-sm btn-ghost" title="Edit">
              <Pencil size={14} /> Edit
            </button>
            <button
              onclick={() => showDeleteConfirm = true}
              class="btn btn-sm btn-ghost text-error"
              title="Delete"
              disabled={fixture.lockState === 'IN_USE'}
            >
              <Trash2 size={14} /> Delete
            </button>
          </div>
        {/if}
      </div>
    </div>

    <ErrorAlert message={error} />

    <!-- Delete confirmation -->
    {#if showDeleteConfirm}
      <div class="mb-4 rounded-lg border border-error/30 bg-error-muted p-4">
        <p class="text-sm font-medium text-error">Delete "{fixture.name}"?</p>
        <p class="mt-1 text-2xs text-text-secondary">Undeploys all MTIB servers and frees assigned nodes. Cannot be undone.</p>
        <div class="mt-3 flex items-center gap-2">
          <button onclick={handleDelete} disabled={deleting} class="btn btn-sm btn-danger">
            {#if deleting}<Loader2 size={14} class="animate-spin" />{:else}<Trash2 size={14} />{/if} Delete
          </button>
          <button onclick={() => showDeleteConfirm = false} class="btn btn-sm btn-ghost">Cancel</button>
        </div>
      </div>
    {/if}

    <!-- Assignability banner — single canonical "can a session start?"
         signal. Backend computes ``assignable`` from
         ``lockState === 'FREE' && health === 'ONLINE'`` and surfaces a
         reason string for any false. -->
    {#if fixture.assignable}
      <div class="mb-4 flex items-center gap-2 rounded-lg border border-success/30 bg-success-muted px-3 py-2">
        <Check size={14} class="text-success" />
        <span class="text-sm font-medium text-success">Ready to run a session</span>
      </div>
    {:else if fixture.assignableReason}
      <div class="mb-4 flex items-center gap-2 rounded-lg border border-warning/30 bg-warning-muted px-3 py-2">
        {#if fixture.lockState === 'IN_USE'}
          <Lock size={14} class="text-warning" />
        {:else if fixture.lockState === 'MAINTENANCE'}
          <AlertTriangle size={14} class="text-warning" />
        {:else}
          <WifiOff size={14} class="text-warning" />
        {/if}
        <span class="text-sm font-medium text-warning">{fixture.assignableReason}</span>
        {#if fixture.lockedBy}
          <span class="ml-auto text-2xs font-mono text-text-tertiary">{fixture.lockedBy}</span>
        {/if}
      </div>
    {/if}

    <!-- Stats row -->
    <div class="grid grid-cols-2 gap-3 sm:grid-cols-4 mb-6">
      <div class="card card-sm">
        <div class="flex items-center gap-2 text-text-tertiary mb-1">
          <Cable size={14} />
          <span class="text-2xs font-medium uppercase tracking-wider">Slots</span>
        </div>
        <div class="text-xl font-semibold text-text-primary">{slots.length}</div>
        <div class="text-2xs text-text-tertiary">{fixture.panelRows}×{fixture.panelCols} panel{#if (fixture.metadata as any)?.hasStandaloneSlot} + standalone{/if}</div>
      </div>
      <div class="card card-sm">
        <div class="flex items-center gap-2 text-text-tertiary mb-1">
          <Wifi size={14} />
          <span class="text-2xs font-medium uppercase tracking-wider">Assigned</span>
        </div>
        <div class="text-xl font-semibold text-text-primary">{assignedCount}/{slots.length}</div>
        <div class="text-2xs text-text-tertiary">{readyCount} ready</div>
      </div>
      <div class="card card-sm">
        <div class="flex items-center gap-2 text-text-tertiary mb-1">
          <Factory size={14} />
          <span class="text-2xs font-medium uppercase tracking-wider">Sessions</span>
        </div>
        <div class="text-xl font-semibold text-text-primary">{sessions.length || '—'}</div>
        <div class="text-2xs text-text-tertiary">manufacturing runs</div>
      </div>
      <div class="card card-sm">
        <div class="flex items-center gap-2 text-text-tertiary mb-1">
          {#if fixture.health === 'ONLINE'}
            <Wifi size={14} class="text-success" />
          {:else if fixture.health === 'OFFLINE'}
            <WifiOff size={14} class="text-error" />
          {:else if fixture.health === 'ERROR'}
            <AlertTriangle size={14} class="text-warning" />
          {:else}
            <WifiOff size={14} />
          {/if}
          <span class="text-2xs font-medium uppercase tracking-wider">Health</span>
        </div>
        <div class="mt-0.5">
          <StatusBadge status={healthBadge} />
        </div>
        <div class="text-2xs text-text-tertiary mt-1">
          {#if fixture.healthDetails}
            {fixture.healthDetails.nodesReady}/{fixture.healthDetails.nodesTotal} nodes
            {#if fixture.healthDetails.mtibsTotal > 0}
              · {fixture.healthDetails.mtibsReady}/{fixture.healthDetails.mtibsTotal} MTIBs
            {/if}
          {:else}
            no data
          {/if}
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <Tabs
      variant="underline"
      tabs={[
        { id: 'slots', label: `Slots (${slots.length})` },
        { id: 'sessions', label: 'Sessions' },
        { id: 'history', label: 'History' },
      ]}
      activeTab={activeTab}
      onchange={(id) => activeTab = id}
    />

    <div class="mt-4">
      <!-- Slots Tab -->
      {#if activeTab === 'slots'}
        {#if slots.length === 0}
          <EmptyState message="No slots configured." icon={Cable} />
        {:else}
          <FixtureLayoutGrid
            panelRows={fixture.panelRows}
            panelCols={fixture.panelCols}
            {hasStandaloneSlot}
            slots={layoutSlots}
            onSlotClick={openSlotPopover}
          />
          <SlotAssignmentPopover
            open={popoverOpen}
            slot={popoverSlot}
            {availableNodes}
            {canManage}
            locked={fixture.lockState === 'IN_USE'}
            onClose={closeSlotPopover}
            onAssign={handleAssign}
            onUnassign={handleUnassign}
          />
        {/if}

      <!-- Sessions Tab -->
      {:else if activeTab === 'sessions'}
        {#if sessionsLoading}
          <LoadingState message="Loading sessions..." />
        {:else if sessions.length === 0}
          <EmptyState message="No manufacturing sessions have used this fixture." icon={Factory} />
        {:else}
          <!-- Selection bar for batch actions -->
          {#if canManage}
            <SelectionBar
              selectedCount={selectedSessionIds.size}
              totalCount={sessions.length}
              onSelectAll={selectAllSessions}
              onClearSelection={clearSessionSelection}
              actions={[
                {
                  label: 'Archive',
                  icon: Archive,
                  variant: 'ghost',
                  loading: batchLoading,
                  onclick: () => batchAction('archive'),
                },
                {
                  label: 'Delete',
                  icon: Trash2,
                  variant: 'danger',
                  loading: batchLoading,
                  onclick: () => batchAction('delete'),
                },
              ]}
            />
          {/if}

          <!-- Batch delete confirmation -->
          {#if confirmBatchDelete}
            <div class="mb-3 rounded-lg border border-error/30 bg-error-muted p-4">
              <p class="text-sm font-medium text-error">
                Delete {selectedSessionIds.size} session{selectedSessionIds.size !== 1 ? 's' : ''}?
              </p>
              <p class="mt-1 text-2xs text-text-secondary">All test runs, results, and measurements will be permanently removed. This cannot be undone.</p>
              <div class="mt-3 flex items-center gap-2">
                <button onclick={() => batchAction('delete')} disabled={batchLoading} class="btn btn-sm btn-danger">
                  {#if batchLoading}<Loader2 size={14} class="animate-spin" />{:else}<Trash2 size={14} />{/if}
                  Delete {selectedSessionIds.size} session{selectedSessionIds.size !== 1 ? 's' : ''}
                </button>
                <button onclick={() => confirmBatchDelete = false} class="btn btn-sm btn-ghost">Cancel</button>
              </div>
            </div>
          {/if}

          <div class="table-wrapper">
            <table class="table">
              <thead>
                <tr>
                  {#if canManage}
                    <th class="table-header w-10">
                      <input
                        type="checkbox"
                        checked={selectedSessionIds.size === sessions.length && sessions.length > 0}
                        indeterminate={selectedSessionIds.size > 0 && selectedSessionIds.size < sessions.length}
                        onchange={() => selectedSessionIds.size === sessions.length ? clearSessionSelection() : selectAllSessions()}
                        class="h-4 w-4 rounded border-border text-accent focus:ring-accent"
                      />
                    </th>
                  {/if}
                  <th class="table-header">Session</th>
                  <th class="table-header">Status</th>
                  <th class="table-header">Operator</th>
                  <th class="table-header">Runs</th>
                  <th class="table-header">Started</th>
                  <th class="table-header">Duration</th>
                </tr>
              </thead>
              <tbody>
                {#each sessions as session}
                  <tr class="table-row">
                    {#if canManage}
                      <td class="table-cell">
                        <input
                          type="checkbox"
                          checked={selectedSessionIds.has(session.id)}
                          onchange={() => toggleSession(session.id)}
                          class="h-4 w-4 rounded border-border text-accent focus:ring-accent"
                        />
                      </td>
                    {/if}
                    <td class="table-cell cursor-pointer" onclick={() => goto(`/manufacturing/session/${session.id}`)}>
                      <span class="font-mono text-2xs text-text-tertiary hover:text-accent">{session.id.slice(0, 8)}</span>
                    </td>
                    <td class="table-cell"><StatusBadge status={session.status} /></td>
                    <td class="table-cell text-text-secondary">{session.operator?.name ?? '—'}</td>
                    <td class="table-cell font-mono text-text-secondary">{session.runCount ?? 0}</td>
                    <td class="table-cell text-2xs text-text-tertiary">{session.startedAt ? formatDate(session.startedAt) : '—'}</td>
                    <td class="table-cell text-2xs text-text-tertiary">
                      {#if session.endedAt && session.startedAt}
                        {Math.round((new Date(session.endedAt).getTime() - new Date(session.startedAt).getTime()) / 60000)}m
                      {:else if session.status === 'ACTIVE'}
                        <span class="text-success">Active</span>
                      {:else}
                        —
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}

      <!-- History Tab (audit log) -->
      {:else if activeTab === 'history'}
        {#if auditLoading}
          <LoadingState message="Loading history..." />
        {:else if auditEntries.length === 0}
          <EmptyState message="No history entries." icon={History} />
        {:else}
          <div class="space-y-3">
            {#each auditEntries as entry}
              <div class="flex gap-3 items-start">
                <div class="mt-1 h-2 w-2 rounded-full bg-accent shrink-0"></div>
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-medium text-text-primary">{entry.action}</span>
                    <span class="text-2xs text-text-tertiary">{relativeTime(entry.createdAt)}</span>
                  </div>
                  {#if entry.user}
                    <p class="text-2xs text-text-secondary">{entry.user.name || entry.user.email}</p>
                  {/if}
                  {#if entry.details}
                    <pre class="mt-1 rounded bg-surface-2 px-3 py-2 text-2xs font-mono text-text-tertiary overflow-x-auto">{JSON.stringify(entry.details, null, 2)}</pre>
                  {/if}
                </div>
                <span class="text-2xs text-text-tertiary shrink-0 whitespace-nowrap">{formatDate(entry.createdAt)}</span>
              </div>
            {/each}
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</div>
