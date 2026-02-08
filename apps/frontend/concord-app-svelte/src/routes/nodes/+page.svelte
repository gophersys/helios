<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { Check, RefreshCw } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import { PageHeader, ErrorAlert, EmptyState, LoadingState, ConfirmDeleteDialog, Select, FormCard } from '$lib/components/ui';
  import NodeCard from '$lib/components/nodes/node-card.svelte';
  import DiscoveredNodeRow from '$lib/components/nodes/discovered-node-row.svelte';
  import type { ConcordNode, DiscoveredNode, NodeSyncResult } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('Concord.Admin.Nodes.Manage'));

  let nodes = $state<ConcordNode[]>([]);
  let discoveredNodes = $state<DiscoveredNode[]>([]);
  let offlineNodes = $state<ConcordNode[]>([]);
  let loading = $state(true);
  let syncing = $state(false);
  let error = $state<string | null>(null);
  let submitting = $state(false);

  // Edit form state
  let showEditForm = $state(false);
  let editingId = $state<string | null>(null);
  let formName = $state('');
  let formHostname = $state('');
  let formType = $state('MANUFACTURING');
  let formIpAddress = $state('');
  let formHardwareRevision = $state('');

  // Register inline form
  let registeringHostname = $state<string | null>(null);
  let registerType = $state('MANUFACTURING');

  // Delete confirmation
  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  // Auto-refresh
  let syncInterval: ReturnType<typeof setInterval> | null = null;
  const SYNC_INTERVAL_MS = 30_000;

  async function fetchNodes() {
    try {
      const res = await apiFetch<ApiResponse<{ data: ConcordNode[] }>>('/v2/nodes');
      const payload = res.data;
      nodes = Array.isArray(payload) ? payload : (payload as { data: ConcordNode[] }).data || [];
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load nodes';
    }
  }

  async function handleSync() {
    error = null;
    syncing = true;
    try {
      const res = await api.post<ApiResponse<NodeSyncResult>>('/v2/nodes/sync');
      const result = res.data;
      discoveredNodes = result.discovered || [];
      offlineNodes = result.offline || [];
      await fetchNodes();
    } catch {
      // Sync may fail locally (no K8s) — silently fall back to just fetching nodes
      if (!nodes.length) await fetchNodes();
    } finally {
      syncing = false;
    }
  }

  async function initialLoad() {
    await fetchNodes();
    loading = false;
    // Also sync to get discovered/offline info
    await handleSync();
  }

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.Nodes.View')) {
      goto('/');
      return;
    }
    initialLoad();
    syncInterval = setInterval(() => {
      if (!syncing) handleSync();
    }, SYNC_INTERVAL_MS);
  });

  onDestroy(() => {
    if (syncInterval) clearInterval(syncInterval);
  });

  // -- Edit --

  function resetEditForm() {
    formName = '';
    formHostname = '';
    formType = 'MANUFACTURING';
    formIpAddress = '';
    formHardwareRevision = '';
    editingId = null;
    showEditForm = false;
  }

  function startEdit(n: ConcordNode) {
    formName = n.name;
    formHostname = n.hostname;
    formType = n.type;
    formIpAddress = n.ipAddress || '';
    formHardwareRevision = n.hardwareRevision || '';
    editingId = n.id;
    showEditForm = true;
  }

  async function handleEditSubmit(e: Event) {
    e.preventDefault();
    if (!editingId) return;
    error = null;
    submitting = true;
    try {
      await api.put(`/v2/nodes/${editingId}`, {
        name: formName,
        hostname: formHostname,
        type: formType,
        ipAddress: formIpAddress || null,
        hardwareRevision: formHardwareRevision || null,
      });
      resetEditForm();
      await fetchNodes();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to save node';
    } finally {
      submitting = false;
    }
  }

  // -- Register from discovered --

  function startRegister(hostname: string) {
    registeringHostname = hostname;
    registerType = 'MANUFACTURING';
  }

  async function handleRegister() {
    if (!registeringHostname) return;
    error = null;
    submitting = true;
    try {
      await api.post('/v2/nodes', {
        name: registeringHostname,
        hostname: registeringHostname,
        type: registerType,
      });
      discoveredNodes = discoveredNodes.filter(n => n.hostname !== registeringHostname);
      registeringHostname = null;
      await fetchNodes();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to register node';
    } finally {
      submitting = false;
    }
  }

  // -- Delete --

  function promptDelete(id: string) {
    const target = nodes.find((n) => n.id === id);
    deleteTarget = { id, name: target?.name || '' };
  }

  async function handleDelete(id: string) {
    error = null;
    try {
      await api.delete(`/v2/nodes/${id}`);
      await fetchNodes();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete node';
    }
  }

  // -- Health check --

  async function handleHealthCheck(id: string) {
    error = null;
    try {
      await api.post(`/v2/nodes/${id}/health`);
      await fetchNodes();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Health check failed';
    }
  }
</script>

<svelte:head>
  <title>Nodes — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="Nodes"
      description="Manage cluster nodes for manufacturing and validation fixtures."
    >
      {#snippet actions()}
        {#if canManage}
          <button
            onclick={handleSync}
            disabled={syncing}
            class="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm font-medium text-text-primary hover:bg-surface-3 disabled:opacity-50"
          >
            <RefreshCw size={16} class={syncing ? 'animate-spin' : ''} />
            {syncing ? 'Syncing...' : 'Sync from Cluster'}
          </button>
        {/if}
      {/snippet}
    </PageHeader>
  </div>

  {#if loading}
    <LoadingState message="Loading nodes..." />
  {:else}
    <ErrorAlert message={error} />

    {#if showEditForm && canManage}
      <FormCard title="Edit node" onClose={resetEditForm}>
        <form onsubmit={handleEditSubmit}>
          <div class="mb-3 grid grid-cols-2 gap-3">
            <label>
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Name</span>
              <input
                type="text"
                required
                bind:value={formName}
                placeholder="e.g. mfg-node-01"
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </label>
            <label>
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Hostname</span>
              <input
                type="text"
                required
                bind:value={formHostname}
                placeholder="e.g. node-01.local"
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </label>
            <Select
              bind:value={formType}
              label="Type"
              options={[
                { value: 'MANUFACTURING', label: 'Manufacturing' },
                { value: 'VALIDATION', label: 'Validation' },
              ]}
            />
            <label>
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">IP Address</span>
              <input
                type="text"
                bind:value={formIpAddress}
                placeholder="Optional"
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </label>
            <label>
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Hardware Revision</span>
              <input
                type="text"
                bind:value={formHardwareRevision}
                placeholder="Optional"
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
              {submitting ? 'Saving...' : 'Save changes'}
            </button>
            <button
              type="button"
              onclick={resetEditForm}
              class="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2"
            >
              Cancel
            </button>
          </div>
        </form>
      </FormCard>
    {/if}

    <!-- Discovered nodes banner -->
    {#if discoveredNodes.length > 0}
      <div class="mb-6">
        <div class="mb-3 flex items-center gap-2">
          <span class="h-2 w-2 rounded-full bg-accent animate-pulse"></span>
          <h2 class="text-sm font-semibold text-text-primary">
            Discovered Nodes ({discoveredNodes.length})
          </h2>
        </div>
        <div class="space-y-2">
          {#each discoveredNodes as dn (dn.hostname)}
            {#if registeringHostname === dn.hostname}
              <!-- Inline register form -->
              <div class="rounded-lg border border-accent bg-accent-muted px-4 py-3">
                <div class="flex items-center justify-between gap-3">
                  <div class="flex items-center gap-3">
                    <div>
                      <p class="text-sm font-medium text-text-primary">{dn.hostname}</p>
                      <p class="text-2xs text-text-tertiary">IP: {dn.ip}</p>
                    </div>
                  </div>
                  <div class="flex items-center gap-2">
                    <Select
                      bind:value={registerType}
                      options={[
                        { value: 'MANUFACTURING', label: 'Manufacturing' },
                        { value: 'VALIDATION', label: 'Validation' },
                      ]}
                      compact
                    />
                    <button
                      onclick={handleRegister}
                      disabled={submitting}
                      class="flex items-center gap-1 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
                    >
                      <Check size={14} />
                      {submitting ? 'Registering...' : 'Register'}
                    </button>
                    <button
                      onclick={() => registeringHostname = null}
                      class="rounded-lg px-2 py-1.5 text-xs text-text-secondary hover:bg-surface-2"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            {:else}
              <DiscoveredNodeRow node={dn} onRegister={startRegister} />
            {/if}
          {/each}
        </div>
      </div>
    {/if}

    <!-- Offline nodes warning -->
    {#if offlineNodes.length > 0}
      <div class="mb-6 rounded-lg border border-warning bg-warning-muted px-4 py-3">
        <h3 class="text-sm font-semibold text-warning">
          Offline Nodes ({offlineNodes.length})
        </h3>
        <div class="mt-1 flex flex-wrap gap-2">
          {#each offlineNodes as on}
            <span class="text-2xs text-text-secondary">{on.name} ({on.hostname})</span>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Registered Nodes Grid -->
    {#if nodes.length > 0}
      <div class="mb-3">
        <h2 class="text-sm font-semibold text-text-primary">
          Registered Nodes ({nodes.length})
        </h2>
      </div>
    {/if}

    {#if nodes.length === 0 && discoveredNodes.length === 0}
      <EmptyState message="No nodes yet. Click 'Sync from Cluster' to discover nodes." />
    {:else if nodes.length > 0}
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {#each nodes as n (n.id)}
          <NodeCard
            node={n}
            {canManage}
            onEdit={startEdit}
            onDelete={promptDelete}
            onHealthCheck={handleHealthCheck}
          />
        {/each}
      </div>
    {/if}

    <ConfirmDeleteDialog
      open={!!deleteTarget}
      entityType="node"
      entityName={deleteTarget?.name || ''}
      onConfirm={() => { handleDelete(deleteTarget!.id); deleteTarget = null; }}
      onCancel={() => (deleteTarget = null)}
    />
  {/if}
</div>
