<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { Play, Square, RotateCcw, Rocket, ChevronDown, ChevronUp, Trash2, Pencil, X, Check, Loader2 } from 'lucide-svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import SlotAssignment from './slot-assignment.svelte';
  import { apiFetch, api } from '$lib/api';
  import type { Fixture, ConcordNode, ConcordDeployment } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  let { fixture, canManage, onRefresh, onDeleted }: {
    fixture: Fixture;
    canManage: boolean;
    onRefresh: () => void;
    onDeleted?: () => void;
  } = $props();

  let error = $state<string | null>(null);
  let availableNodes = $state<ConcordNode[]>([]);
  let deploying = $state(false);

  // Deployment state
  let deployment = $state<ConcordDeployment | null>(null);
  let deploymentLoading = $state(true);
  let k8sStatus = $state<{ name: string; slotIndex: number | null; status: { pods: { name: string; nodeName: string; status: string; ready: boolean; restarts: number }[] } | null }[]>([]);
  let podExpanded = $state(false);
  let actionInProgress = $state(false);
  let deploymentPollTimer: ReturnType<typeof setInterval> | undefined;

  async function fetchAvailableNodes() {
    try {
      const res = await apiFetch<ApiResponse<{ data: ConcordNode[] }>>('/v2/devices/mtibs');
      const allNodes = res.data.data || res.data;
      availableNodes = (allNodes as ConcordNode[]).filter(
        n => n.type === fixture.type && !n.fixtureSlot
      );
    } catch {
      // Non-critical
    }
  }

  async function fetchDeployment() {
    try {
      const res = await apiFetch<ApiResponse<{ data: ConcordDeployment[] }>>(`/v2/kubernetes/managed-deployments?fixtureId=${fixture.id}&limit=1`);
      const deployments = res.data.data || res.data;
      const list = deployments as ConcordDeployment[];
      deployment = list.length > 0 ? list[0] : null;

      // Fetch K8s status if running
      if (deployment && deployment.status === 'RUNNING') {
        try {
          const statusRes = await apiFetch<ApiResponse<ConcordDeployment & { k8sStatus?: typeof k8sStatus }>>(`/v2/kubernetes/managed-deployments/${deployment.id}/status`);
          k8sStatus = statusRes.data.k8sStatus || [];
        } catch {
          k8sStatus = [];
        }
      } else {
        k8sStatus = [];
      }
    } catch {
      deployment = null;
    } finally {
      deploymentLoading = false;
    }
  }

  onMount(() => {
    if (canManage) fetchAvailableNodes();
    fetchDeployment();
    // Poll deployment status every 10s when running
    deploymentPollTimer = setInterval(() => {
      if (deployment?.status === 'RUNNING') {
        fetchDeployment();
      }
    }, 10000);
  });

  onDestroy(() => {
    if (deploymentPollTimer) clearInterval(deploymentPollTimer);
  });

  async function handleAssign(slotId: string, nodeId: string) {
    error = null;
    try {
      await api.post(`/v2/fixtures/${fixture.id}/slots/${slotId}/assign`, { nodeId });
      onRefresh();
      fetchAvailableNodes();
    } catch (err: any) {
      error = err?.data?.errors?.[0]?.message || (err instanceof Error ? err.message : 'Failed to assign node');
    }
  }

  async function handleUnassign(slotId: string) {
    error = null;
    try {
      await api.post(`/v2/fixtures/${fixture.id}/slots/${slotId}/assign`, { nodeId: null });
      onRefresh();
      fetchAvailableNodes();
    } catch (err: any) {
      error = err?.data?.errors?.[0]?.message || (err instanceof Error ? err.message : 'Failed to unassign node');
    }
  }

  // ── Edit ──
  let editing = $state(false);
  let editName = $state('');
  let editDescription = $state('');
  let editActive = $state(true);
  let saving = $state(false);

  function startEdit() {
    editName = fixture.name;
    editDescription = fixture.description || '';
    editActive = fixture.active;
    editing = true;
  }

  async function saveEdit() {
    saving = true;
    error = null;
    try {
      await api.put(`/v2/fixtures/${fixture.id}`, {
        name: editName.trim(),
        description: editDescription.trim() || null,
        active: editActive,
      });
      editing = false;
      onRefresh();
    } catch (err: any) {
      error = err?.data?.errors?.[0]?.message || (err instanceof Error ? err.message : 'Failed to update fixture');
    } finally {
      saving = false;
    }
  }

  // ── Delete ──
  let showDeleteConfirm = $state(false);
  let deleting = $state(false);

  async function handleDelete() {
    deleting = true;
    error = null;
    try {
      await api.delete(`/v2/fixtures/${fixture.id}`);
      showDeleteConfirm = false;
      onDeleted?.();
    } catch (err: any) {
      const msg = err?.data?.errors?.[0]?.message || (err instanceof Error ? err.message : 'Failed to delete fixture');
      error = msg;
      showDeleteConfirm = false;
    } finally {
      deleting = false;
    }
  }

  async function handleCreateAndDeploy() {
    error = null;
    deploying = true;
    try {
      const createRes = await api.post<ApiResponse<ConcordDeployment>>('/v2/kubernetes/managed-deployments', {
        name: `${fixture.name}-deploy`,
        fixtureId: fixture.id,
        productId: fixture.productId,
      });
      const newDep = createRes.data;
      // Now deploy it
      await api.post(`/v2/kubernetes/managed-deployments/${newDep.id}/deploy`);
      fetchDeployment();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to deploy';
    } finally {
      deploying = false;
    }
  }

  async function handleDeploy() {
    if (!deployment) return;
    error = null;
    actionInProgress = true;
    try {
      await api.post(`/v2/kubernetes/managed-deployments/${deployment.id}/deploy`);
      fetchDeployment();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to deploy';
    } finally {
      actionInProgress = false;
    }
  }

  async function handleStop() {
    if (!deployment) return;
    error = null;
    actionInProgress = true;
    try {
      await api.post(`/v2/kubernetes/managed-deployments/${deployment.id}/stop`);
      fetchDeployment();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to stop';
    } finally {
      actionInProgress = false;
    }
  }

  async function handleRestart() {
    if (!deployment) return;
    error = null;
    actionInProgress = true;
    try {
      await api.post(`/v2/kubernetes/managed-deployments/${deployment.id}/restart`);
      fetchDeployment();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to restart';
    } finally {
      actionInProgress = false;
    }
  }

  const slots = $derived(fixture.slots || []);
  const allPods = $derived(k8sStatus.flatMap(d => d.status?.pods || []));

  const NODE_STATUS_DOT: Record<string, string> = {
    ONLINE: 'bg-success',
    ERROR: 'bg-error',
    OFFLINE: 'bg-surface-2 border border-border',
  };
  const NODE_STATUS_DOT_DEFAULT = 'bg-warning';
  function nodeStatusDot(status: string): string {
    return NODE_STATUS_DOT[status] ?? NODE_STATUS_DOT_DEFAULT;
  }
</script>

<div class="animate-fade-in">
  <ErrorAlert message={error} />

  <div class="card card-md">
    <!-- Header -->
    <div class="flex items-start justify-between">
      <div class="flex-1">
        {#if editing}
          <div class="space-y-3">
            <input type="text" bind:value={editName} class="input input-md w-full" placeholder="Fixture name" />
            <input type="text" bind:value={editDescription} class="input input-sm w-full" placeholder="Description (optional)" />
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" bind:checked={editActive} class="h-4 w-4 rounded border-border text-accent" />
              <span class="text-sm text-text-secondary">Active</span>
            </label>
            <div class="flex items-center gap-2">
              <button onclick={saveEdit} disabled={saving || !editName.trim()} class="btn btn-sm btn-primary">
                {#if saving}<Loader2 size={14} class="animate-spin" />{:else}<Check size={14} />{/if} Save
              </button>
              <button onclick={() => editing = false} class="btn btn-sm btn-ghost">Cancel</button>
            </div>
          </div>
        {:else}
          <div class="flex items-center gap-2">
            <h2 class="text-lg font-semibold text-text-primary">{fixture.name}</h2>
            <StatusBadge status={fixture.type} />
            <StatusBadge status={fixture.active ? 'ACTIVE' : 'INACTIVE'} />
            {#if fixture.status === 'LOCKED'}
              <StatusBadge status="LOCKED" />
            {/if}
          </div>
          {#if fixture.description}
            <p class="mt-1 text-sm text-text-secondary">{fixture.description}</p>
          {/if}
          {#if fixture.productName}
            <p class="mt-1 text-2xs text-text-tertiary">Product: <span class="text-text-secondary">{fixture.productName}</span></p>
          {/if}
        {/if}
      </div>
      {#if canManage && !editing}
        <div class="flex items-center gap-1">
          <button onclick={startEdit} class="btn btn-sm btn-ghost" title="Edit fixture">
            <Pencil size={14} />
          </button>
          <button onclick={() => showDeleteConfirm = true} class="btn btn-sm btn-ghost text-error" title="Delete fixture" disabled={fixture.status === 'LOCKED'}>
            <Trash2 size={14} />
          </button>
        </div>
      {/if}
    </div>

    <!-- Delete confirmation -->
    {#if showDeleteConfirm}
      <div class="mt-3 rounded-lg border border-error/30 bg-error-muted p-4">
        <p class="text-sm font-medium text-error">Delete "{fixture.name}"?</p>
        <p class="mt-1 text-2xs text-text-secondary">This will undeploy all MTIB servers and free assigned nodes. This cannot be undone.</p>
        <div class="mt-3 flex items-center gap-2">
          <button onclick={handleDelete} disabled={deleting} class="btn btn-sm btn-danger">
            {#if deleting}<Loader2 size={14} class="animate-spin" />{:else}<Trash2 size={14} />{/if} Delete
          </button>
          <button onclick={() => showDeleteConfirm = false} class="btn btn-sm btn-ghost">Cancel</button>
        </div>
      </div>
    {/if}

    <!-- Deployment section -->
    <div class="mt-6 border-t border-border pt-6">
      <h3 class="mb-3 text-sm font-semibold text-text-primary">Deployment</h3>

      {#if deploymentLoading}
        <p class="text-2xs text-text-tertiary">Loading deployment status...</p>
      {:else if !deployment}
        <!-- No deployment exists yet -->
        {#if canManage}
          <div class="flex items-center gap-3">
            <p class="text-2xs text-text-tertiary">No deployment configured.</p>
            <button
              onclick={handleCreateAndDeploy}
              disabled={deploying}
              class="btn btn-sm btn-primary"
            >
              <Rocket size={16} />
              {deploying ? 'Deploying...' : 'Deploy'}
            </button>
          </div>
        {:else}
          <p class="text-2xs text-text-tertiary">No deployment configured.</p>
        {/if}
      {:else}
        <!-- Existing deployment -->
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <StatusBadge status={deployment.status} />
            <span class="text-sm text-text-secondary">{deployment.name}</span>
            {#if deployment.version}
              <span class="text-2xs text-text-tertiary">v{deployment.version}</span>
            {/if}
          </div>

          {#if canManage}
            <div class="flex items-center gap-2">
              {#if deployment.status === 'PENDING' || deployment.status === 'STOPPED' || deployment.status === 'FAILED'}
                <button
                  onclick={handleDeploy}
                  disabled={actionInProgress}
                  class="btn btn-sm btn-primary"
                >
                  <Play size={14} />
                  {deployment.status === 'FAILED' ? 'Retry' : 'Deploy'}
                </button>
              {/if}
              {#if deployment.status === 'RUNNING'}
                <button
                  onclick={handleRestart}
                  disabled={actionInProgress}
                  class="btn btn-sm btn-secondary"
                >
                  <RotateCcw size={14} />
                  Restart
                </button>
                <button
                  onclick={handleStop}
                  disabled={actionInProgress}
                  class="btn btn-sm btn-danger"
                >
                  <Square size={14} />
                  Stop
                </button>
              {/if}
            </div>
          {/if}
        </div>

        <!-- Pod status table -->
        {#if deployment.status === 'RUNNING' && allPods.length > 0}
          <div class="mt-3">
            <button
              onclick={() => podExpanded = !podExpanded}
              class="flex items-center gap-1 text-2xs text-text-tertiary hover:text-text-secondary"
            >
              {#if podExpanded}
                <ChevronUp size={14} />
              {:else}
                <ChevronDown size={14} />
              {/if}
              {allPods.length} pod{allPods.length !== 1 ? 's' : ''}
            </button>

            {#if podExpanded}
              <div class="mt-2 table-wrapper">
                <table class="table">
                  <thead>
                    <tr>
                      <th class="table-header">Pod</th>
                      <th class="table-header">Node</th>
                      <th class="table-header">Status</th>
                      <th class="table-header">Ready</th>
                      <th class="table-header">Restarts</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each allPods as pod}
                      <tr class="table-row">
                        <td class="table-cell font-mono text-2xs text-text-primary">{pod.name}</td>
                        <td class="table-cell text-2xs text-text-secondary">{pod.nodeName}</td>
                        <td class="table-cell">
                          <StatusBadge status={pod.status} />
                        </td>
                        <td class="table-cell">
                          <span class={pod.ready ? 'text-success' : 'text-error'}>
                            {pod.ready ? 'Yes' : 'No'}
                          </span>
                        </td>
                        <td class="table-cell text-text-secondary">{pod.restarts}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            {/if}
          </div>
        {/if}
      {/if}
    </div>

    <!-- Slots table -->
    <div class="mt-6 border-t border-border pt-6">
      <h3 class="mb-3 text-sm font-semibold text-text-primary">
        Slots ({slots.length})
      </h3>

      {#if slots.length === 0}
        <p class="py-6 text-center text-sm text-text-tertiary">No slots configured</p>
      {:else}
        <div class="table-wrapper">
          <table class="table">
            <thead>
              <tr>
                <th class="table-header w-16">Index</th>
                <th class="table-header w-32">Label</th>
                <th class="table-header">Node</th>
                <th class="table-header w-24">Status</th>
              </tr>
            </thead>
            <tbody>
              {#each slots as slot (slot.id)}
                <tr class="table-row">
                  <td class="table-cell">
                    <div class="flex items-center gap-2">
                      {#if slot.node}
                        <div class="h-2 w-2 rounded-full {nodeStatusDot(slot.node.status)}" title={slot.node.status}></div>
                      {/if}
                      <span class="text-text-primary">{slot.slotIndex}</span>
                    </div>
                  </td>
                  <td class="table-cell text-text-secondary">{slot.label || '—'}</td>
                  <td class="table-cell">
                    {#if slot.node}
                      <div>
                        <span class="text-text-primary">{slot.node.name}</span>
                        <span class="ml-2 font-mono text-2xs text-text-tertiary">{slot.node.hostname}</span>
                      </div>
                    {:else}
                      <span class="text-text-tertiary">Unassigned</span>
                    {/if}
                  </td>
                  <td class="table-cell">
                    {#if slot.node}
                      <StatusBadge status={slot.node.status} />
                    {:else}
                      <span class="text-2xs text-text-tertiary">—</span>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>

        <!-- Keep slot assignment functionality for manage permissions -->
        {#if canManage}
          <div class="mt-3 border-t border-border pt-3">
            <details class="group">
              <summary class="cursor-pointer text-2xs text-text-tertiary hover:text-text-secondary">
                Manage slot assignments
              </summary>
              <div class="mt-3 table-wrapper">
                <table class="table">
                  <thead>
                    <tr>
                      <th class="table-header w-16">Index</th>
                      <th class="table-header w-32">Label</th>
                      <th class="table-header">Node</th>
                      <th class="table-header w-24">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each slots as slot (slot.id)}
                      <SlotAssignment
                        {slot}
                        {availableNodes}
                        {canManage}
                        onAssign={handleAssign}
                        onUnassign={handleUnassign}
                      />
                    {/each}
                  </tbody>
                </table>
              </div>
            </details>
          </div>
        {/if}
      {/if}
    </div>
  </div>
</div>
