<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { Check, RefreshCw, Activity, Loader2, Cpu, Pencil, Trash2, Plus, ExternalLink, Wrench } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import { PageHeader, ErrorAlert, EmptyState, LoadingState, ConfirmDeleteDialog, Select, FormCard } from '$lib/components/ui';
  import DiscoveredNodeRow from '$lib/components/nodes/discovered-node-row.svelte';
  import type { ConcordNode, DiscoveredNode, NodeSyncResult } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  const auth = getAuth();

  /** Format raw revision string (e.g. "REV_1_2") → "1.2" */
  function fmtRev(raw: string | null | undefined): string | null {
    if (!raw) return null;
    const m = raw.match(/(\d+)[_.](\d+)/);
    return m ? `${m[1]}.${m[2]}` : raw;
  }
  const canManage = $derived(auth.hasPermission('Concord.Admin.Nodes.Manage'));

  interface NodeMetrics { cpu: number; mem: number; disk: number; hwRev: string | null }

  let nodes = $state<ConcordNode[]>([]);
  let discoveredNodes = $state<DiscoveredNode[]>([]);
  let offlineNodes = $state<ConcordNode[]>([]);
  let nodeMetrics = $state<Record<string, NodeMetrics>>({});
  let loading = $state(true);
  let syncing = $state(false);
  let error = $state<string | null>(null);
  let submitting = $state(false);

  // Sorted nodes: online first, deploying next, offline last
  const sortedNodes = $derived(
    [...nodes].sort((a, b) => {
      const order = { online: 0, deploying: 1, none: 2 };
      const diff = order[getDeployState(a)] - order[getDeployState(b)];
      if (diff !== 0) return diff;
      return (a.hostname || '').localeCompare(b.hostname || '');
    })
  );

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
  let registeringIp = $state<string | null>(null);
  let registerType = $state('MANUFACTURING');

  // Delete confirmation
  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  // Auto-refresh — fast poll (3s) when any node is deploying, slow poll (30s) otherwise
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let fastPolling = $state(false);
  const SLOW_POLL_MS = 30_000;
  const FAST_POLL_MS = 3_000;

  const hasDeployingNodes = $derived(
    nodes.some(n => {
      const ds = n.deploymentStatus;
      if (!ds) return false;
      return (ds.readyReplicas ?? 0) === 0;
    })
  );

  function startPolling(fast: boolean) {
    if (pollTimer) clearInterval(pollTimer);
    fastPolling = fast;
    pollTimer = setInterval(() => {
      if (!syncing) {
        fetchNodes();
        fetchFleetObs();
      }
    }, fast ? FAST_POLL_MS : SLOW_POLL_MS);
  }

  // Auto-switch poll speed when deploy state changes
  $effect(() => {
    if (hasDeployingNodes && !fastPolling) {
      startPolling(true);
    } else if (!hasDeployingNodes && fastPolling) {
      startPolling(false);
    }
  });

  async function fetchNodes() {
    try {
      const res = await apiFetch<ApiResponse<{ data: ConcordNode[] }>>('/v2/mtibs');
      const payload = res.data;
      nodes = Array.isArray(payload) ? payload : (payload as { data: ConcordNode[] }).data || [];
    } catch (err) {
      if (nodes.length === 0) {
        error = err instanceof Error ? err.message : 'Failed to load MTIBs';
      }
    }
  }

  async function fetchFleetObs() {
    try {
      const res = await apiFetch<ApiResponse<{ nodes: any[]; summary: any }>>('/v2/mtibs/observability');
      const payload = res.data;
      const fleetNodes = (payload as any)?.nodes || payload || [];
      if (!Array.isArray(fleetNodes)) return;
      const m: Record<string, NodeMetrics> = {};
      for (const n of fleetNodes) {
        const sys = n.snapshot?.system_metrics;
        if (sys && n.id) {
          m[n.id] = {
            cpu: sys.cpu_percent ?? 0,
            mem: sys.memory_percent ?? 0,
            disk: sys.disk_percent ?? 0,
            hwRev: sys.hardware_revision || null,
          };
        }
      }
      nodeMetrics = m;
    } catch {
      // Non-critical — metrics just won't show
    }
  }

  async function handleSync() {
    error = null;
    syncing = true;
    try {
      const res = await api.post<ApiResponse<NodeSyncResult>>('/v2/mtibs/discover');
      const result = res.data;
      discoveredNodes = result.discovered || [];
      offlineNodes = result.offline || [];
      await fetchNodes();
    } catch {
      if (!nodes.length) await fetchNodes();
    } finally {
      syncing = false;
    }
  }

  async function initialLoad() {
    await fetchNodes();
    loading = false;
    fetchFleetObs();
    await handleSync();
  }

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.Nodes.View')) {
      goto('/');
      return;
    }
    initialLoad();
    startPolling(false);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
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
      await api.put(`/v2/mtibs/${editingId}`, {
        name: formName,
        hostname: formHostname,
        type: formType,
        ipAddress: formIpAddress || null,
        hardwareRevision: formHardwareRevision || null,
      });
      resetEditForm();
      await fetchNodes();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to save MTIB';
    } finally {
      submitting = false;
    }
  }

  // -- Register from discovered --

  function startRegister(hostname: string) {
    const dn = discoveredNodes.find(n => n.hostname === hostname);
    registeringHostname = hostname;
    registeringIp = dn?.ip || null;
    registerType = 'MANUFACTURING';
  }

  async function handleRegister() {
    if (!registeringHostname) return;
    error = null;
    submitting = true;
    try {
      await api.post('/v2/mtibs', {
        name: registeringHostname,
        hostname: registeringHostname,
        type: registerType,
        ipAddress: registeringIp,
      });
      discoveredNodes = discoveredNodes.filter(n => n.hostname !== registeringHostname);
      registeringHostname = null;
      registeringIp = null;
      await fetchNodes();
      // Start fast polling immediately to track deployment progress
      startPolling(true);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to register MTIB';
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
      await api.delete(`/v2/mtibs/${id}`);
      await fetchNodes();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete MTIB';
    }
  }

  // -- Health check --

  async function handleHealthCheck(id: string) {
    error = null;
    try {
      await api.post(`/v2/mtibs/${id}/health`);
      await fetchNodes();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Health check failed';
    }
  }

  // -- Deploy state helper --

  function getDeployState(n: ConcordNode): 'online' | 'deploying' | 'none' {
    const ds = n.deploymentStatus;
    if (!ds) return 'none';
    if ((ds.readyReplicas ?? 0) > 0) return 'online';
    if (ds.pods?.some(p => p.status === 'Running')) return 'online';
    return 'deploying';
  }

  function handleRowClick(n: ConcordNode) {
    const state = getDeployState(n);
    if (state === 'online') {
      goto(`/mtib/${n.id}`);
    } else if (state === 'deploying') {
      // Go straight to K8s — pod if available, otherwise deployment
      const pod = n.deploymentStatus?.pods?.[0];
      if (pod?.name) {
        goto(`/system/pods/default/${pod.name}`);
      } else {
        const deployName = (n as any).metadata?.deployment_name || n.deploymentStatus?.name;
        if (deployName) {
          goto(`/system/deployments/default/${deployName}`);
        }
      }
    }
  }
</script>

<svelte:head>
  <title>MTIB — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="MTIB"
      description="Manage MTIB test bench nodes."
    >
      {#snippet actions()}
        {#if canManage}
          <button
            onclick={handleSync}
            disabled={syncing}
            class="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm font-medium text-text-primary hover:bg-surface-3 disabled:opacity-50"
          >
            <RefreshCw size={16} class={syncing ? 'animate-spin' : ''} />
            {syncing ? 'Syncing...' : 'Sync Cluster'}
          </button>
        {/if}
      {/snippet}
    </PageHeader>
  </div>

  {#if loading}
    <LoadingState message="Loading MTIBs..." />
  {:else}
    <ErrorAlert message={error} />

    {#if showEditForm && canManage}
      <FormCard title="Edit MTIB" onClose={resetEditForm}>
        <form onsubmit={handleEditSubmit}>
          <div class="mb-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label>
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Name</span>
              <input type="text" required bind:value={formName} placeholder="e.g. mfg-node-01"
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none" />
            </label>
            <label>
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Hostname</span>
              <input type="text" required bind:value={formHostname} placeholder="e.g. node-01.local"
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none" />
            </label>
            <Select bind:value={formType} label="Type"
              options={[{ value: 'MANUFACTURING', label: 'Manufacturing' }, { value: 'VALIDATION', label: 'Validation' }]} />
            <label>
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">IP Address</span>
              <input type="text" bind:value={formIpAddress} placeholder="Optional"
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none" />
            </label>
          </div>
          <div class="flex gap-2">
            <button type="submit" disabled={submitting}
              class="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
              <Check size={16} />
              {submitting ? 'Saving...' : 'Save changes'}
            </button>
            <button type="button" onclick={resetEditForm}
              class="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2">Cancel</button>
          </div>
        </form>
      </FormCard>
    {/if}

    <!-- Offline warning -->
    {#if offlineNodes.length > 0}
      <div class="mb-4 rounded-lg border border-warning bg-warning-muted px-4 py-2.5">
        <span class="text-xs font-semibold text-warning">Offline ({offlineNodes.length})</span>
        <span class="ml-2 text-2xs text-text-tertiary">
          {offlineNodes.map(n => n.hostname).join(', ')}
        </span>
      </div>
    {/if}

    <!-- Discovered nodes (unregistered) -->
    {#if discoveredNodes.length > 0}
      <div class="mb-6">
        <div class="mb-2 flex items-center gap-2">
          <span class="h-2 w-2 rounded-full bg-accent animate-pulse"></span>
          <h2 class="text-xs font-semibold text-text-primary uppercase tracking-wider">Discovered</h2>
          <span class="rounded-full bg-accent-muted px-1.5 py-0.5 text-[10px] font-medium text-accent">{discoveredNodes.length}</span>
        </div>
        <div class="space-y-1.5">
          {#each discoveredNodes as dn (dn.hostname)}
            {#if registeringHostname === dn.hostname}
              <div class="rounded-lg border border-accent bg-accent-muted px-4 py-2.5">
                <div class="flex items-center justify-between gap-3">
                  <div>
                    <p class="text-xs font-medium text-text-primary font-mono">{dn.hostname}</p>
                    <p class="text-[10px] text-text-tertiary">{dn.ip}</p>
                  </div>
                  <div class="flex items-center gap-2">
                    <Select bind:value={registerType}
                      options={[{ value: 'MANUFACTURING', label: 'Manufacturing' }, { value: 'VALIDATION', label: 'Validation' }]} compact />
                    <button onclick={handleRegister} disabled={submitting}
                      class="flex items-center gap-1 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50">
                      <Check size={12} /> {submitting ? '...' : 'Register'}
                    </button>
                    <button onclick={() => registeringHostname = null}
                      class="rounded-lg px-2 py-1.5 text-xs text-text-secondary hover:bg-surface-2">Cancel</button>
                  </div>
                </div>
              </div>
            {:else}
              <button onclick={() => startRegister(dn.hostname)}
                class="flex w-full items-center justify-between rounded-lg border border-border bg-surface-1 px-4 py-2 text-left hover:bg-surface-2 transition-colors">
                <div class="flex items-center gap-3">
                  <Cpu size={14} class="text-text-tertiary" />
                  <span class="text-xs font-medium text-text-primary font-mono">{dn.hostname}</span>
                  <span class="text-[10px] text-text-tertiary">{dn.ip}</span>
                </div>
                <div class="flex items-center gap-1 text-[10px] font-medium text-accent">
                  <Plus size={12} /> Register
                </div>
              </button>
            {/if}
          {/each}
        </div>
      </div>
    {/if}

    <!-- Registered MTIBs Table -->
    {#if nodes.length > 0}
      <div class="rounded-lg border border-border overflow-hidden">
        <table class="w-full">
          <thead>
            <tr class="bg-surface-1 text-left text-2xs font-semibold uppercase tracking-wider text-text-tertiary">
              <th class="pl-4 pr-1 py-2.5 w-8"></th>
              <th class="px-3 py-2.5">Node</th>
              <th class="px-3 py-2.5">Revision</th>
              <th class="px-3 py-2.5">State</th>
              <th class="px-3 py-2.5 hidden lg:table-cell">Resources</th>
              <th class="px-3 py-2.5 hidden md:table-cell">Fixture</th>
              {#if canManage}
                <th class="px-3 py-2.5 w-24"></th>
              {/if}
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each sortedNodes as n (n.id)}
              {@const state = getDeployState(n)}
              {@const clickable = state === 'online' || state === 'deploying'}
              {@const metrics = nodeMetrics[n.id]}
              <tr
                onclick={() => handleRowClick(n)}
                class="group transition-colors
                  {clickable ? 'cursor-pointer hover:bg-surface-1' : ''}"
              >
                <!-- Status dot -->
                <td class="pl-4 pr-1 py-3 align-middle">
                  <span class="relative flex h-2.5 w-2.5">
                    <span class="h-2.5 w-2.5 rounded-full
                      {state === 'online' ? 'bg-success' : state === 'deploying' ? 'bg-warning' : 'bg-text-tertiary opacity-40'}"></span>
                    {#if state === 'deploying'}
                      <span class="absolute inset-0 rounded-full bg-warning animate-ping opacity-75"></span>
                    {/if}
                  </span>
                </td>

                <!-- Node: hostname + IP + type badge -->
                <td class="px-3 py-3 align-middle">
                  <p class="text-xs font-medium text-text-primary font-mono">{n.hostname}</p>
                  <div class="mt-0.5 flex items-center gap-2">
                    <span class="text-2xs text-text-tertiary font-mono">{n.ipAddress || '—'}</span>
                    <span class="inline-flex rounded-full px-1.5 py-px text-2xs font-semibold leading-tight
                      {n.type === 'MANUFACTURING' ? 'bg-accent-muted text-accent' : 'bg-info-muted text-info'}">
                      {n.type === 'MANUFACTURING' ? 'Manufacturing' : 'Validation'}
                    </span>
                  </div>
                </td>

                <!-- Revision -->
                <td class="px-3 py-3 align-middle">
                  {#if metrics?.hwRev || n.hardwareRevision}
                    {@const rev = fmtRev(metrics?.hwRev || n.hardwareRevision)}
                    <span class="rounded bg-surface-2 px-1.5 py-0.5 text-2xs font-medium text-text-secondary">REV {rev}</span>
                  {:else}
                    <span class="text-xs text-text-tertiary">—</span>
                  {/if}
                </td>

                <!-- State -->
                <td class="px-3 py-3 align-middle">
                  {#if state === 'online'}
                    <span class="inline-flex items-center gap-1.5 text-xs font-medium text-success">
                      <Activity size={12} /> Online
                    </span>
                  {:else if state === 'deploying'}
                    <span class="inline-flex items-center gap-1.5 text-xs font-medium text-warning">
                      <Loader2 size={12} class="animate-spin" /> Deploying
                    </span>
                  {:else}
                    <span class="text-xs text-text-tertiary">—</span>
                  {/if}
                </td>

                <!-- Resources (CPU / MEM / DISK mini bars) -->
                <td class="px-3 py-3 align-middle hidden lg:table-cell">
                  {#if metrics}
                    <div class="flex items-center gap-3">
                      {#each [
                        { label: 'CPU', value: metrics.cpu },
                        { label: 'MEM', value: metrics.mem },
                        { label: 'DSK', value: metrics.disk },
                      ] as bar}
                        <div class="flex items-center gap-1.5 min-w-0">
                          <span class="text-2xs text-text-tertiary w-7 shrink-0">{bar.label}</span>
                          <div class="relative h-1.5 w-10 rounded-full bg-surface-2 overflow-hidden">
                            <div
                              class="absolute inset-y-0 left-0 rounded-full transition-all
                                {bar.value > 80 ? 'bg-error' : bar.value > 60 ? 'bg-warning' : 'bg-success'}"
                              style:width="{Math.min(100, bar.value)}%"
                            ></div>
                          </div>
                          <span class="text-2xs text-text-tertiary w-7 text-right tabular-nums">{Math.round(bar.value)}%</span>
                        </div>
                      {/each}
                    </div>
                  {:else if state === 'online'}
                    <span class="text-xs text-text-tertiary">…</span>
                  {:else}
                    <span class="text-xs text-text-tertiary">—</span>
                  {/if}
                </td>

                <!-- Fixture -->
                <td class="px-3 py-3 align-middle hidden md:table-cell">
                  {#if n.fixtureSlot}
                    <span class="inline-flex items-center gap-1.5 text-xs font-medium text-text-secondary">
                      <Wrench size={12} class="text-text-tertiary" /> {n.fixtureSlot.fixtureName || 'Assigned'}
                    </span>
                  {:else}
                    <span class="text-xs text-text-tertiary">—</span>
                  {/if}
                </td>

                <!-- Actions -->
                {#if canManage}
                  <td class="px-3 py-3 align-middle">
                    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
                    <div class="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
                      onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()} role="group">
                      {#if clickable}
                        <button onclick={() => goto(`/mtib/${n.id}`)} title="View details"
                          class="rounded p-1 text-text-tertiary hover:text-accent hover:bg-surface-2">
                          <ExternalLink size={14} />
                        </button>
                      {/if}
                      <button onclick={() => startEdit(n)} title="Edit"
                        class="rounded p-1 text-text-tertiary hover:text-text-primary hover:bg-surface-2">
                        <Pencil size={14} />
                      </button>
                      <button onclick={() => promptDelete(n.id)} title="Delete"
                        class="rounded p-1 text-text-tertiary hover:text-error hover:bg-surface-2">
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
    {:else if discoveredNodes.length === 0}
      <EmptyState message="No MTIBs found. Sync from the cluster to discover nodes." />
    {/if}

    <ConfirmDeleteDialog
      open={!!deleteTarget}
      entityType="MTIB"
      entityName={deleteTarget?.name || ''}
      onConfirm={() => { handleDelete(deleteTarget!.id); deleteTarget = null; }}
      onCancel={() => (deleteTarget = null)}
    />
  {/if}
</div>
