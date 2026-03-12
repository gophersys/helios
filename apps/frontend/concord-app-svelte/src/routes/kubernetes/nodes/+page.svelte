<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import { getAuth } from '$lib/stores/auth.svelte';
  import StatusIndicator from '$lib/components/system/status-indicator.svelte';
  import ResourceAge from '$lib/components/system/resource-age.svelte';
  import { formatCpu, formatMem, parseCpuMillis, parseMemoryMi } from '$lib/components/system/k8s-resources';
  import PlanesLoader from '$lib/components/ui/planes-loader.svelte';

  // Matches backend: apps/backend/http-api/src/services/kubernetes/serializers.py
  interface NodeSummary {
    name: string;
    status: string;
    roles: string[];
    capacity: { cpu: string; memory: string; pods: string };
    allocatable: { cpu: string; memory: string; pods: string };
    allocated: { cpuRequests: string; memoryRequests: string; podCount: number };
    createdAt: string;
    labels: Record<string, string>;
  }

  let nodes = $state<NodeSummary[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let filterTag = $state('');
  const auth = getAuth();
  let pollInterval: ReturnType<typeof setInterval>;

  async function fetchNodes() {
    try {
      const res = await api.get<{ data: NodeSummary[] }>('/v2/cluster/nodes');
      if (res?.data) nodes = res.data;
      error = null;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load nodes';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('system:view')) {
      goto('/');
      return;
    }
    fetchNodes();
    pollInterval = setInterval(fetchNodes, 15000);
  });

  onDestroy(() => {
    if (pollInterval) clearInterval(pollInterval);
  });

  const filteredNodes = $derived(
    filterTag
      ? nodes.filter(n => Object.entries(n.labels ?? {}).some(
          ([k, v]) => `${k}=${v}`.toLowerCase().includes(filterTag.toLowerCase())
        ))
      : nodes
  );

  const allTags = $derived(
    [...new Set(nodes.flatMap(n => Object.entries(n.labels ?? {}).map(([k, v]) => `${k}=${v}`)))].sort()
  );

  function getUsageColor(used: number, total: number): string {
    if (total === 0) return 'bg-surface-2';
    const pct = (used / total) * 100;
    if (pct >= 90) return 'bg-error';
    if (pct >= 70) return 'bg-warning';
    return 'bg-success';
  }

  // Helper to get parsed values for a node
  function getNodeResources(node: NodeSummary) {
    return {
      cpuCapacity: parseCpuMillis(node.capacity?.cpu ?? '0'),
      cpuUsed: parseCpuMillis(node.allocated?.cpuRequests ?? '0'),
      memCapacity: parseMemoryMi(node.capacity?.memory ?? '0'),
      memUsed: parseMemoryMi(node.allocated?.memoryRequests ?? '0'),
      podsCapacity: parseInt(node.capacity?.pods ?? '0', 10),
      podsUsed: node.allocated?.podCount ?? 0
    };
  }
</script>

<div class="space-y-4">
  <!-- Filters -->
  <div class="flex items-center gap-3">
    <input
      type="text"
      placeholder="Filter by label..."
      aria-label="Filter nodes by label"
      bind:value={filterTag}
      class="px-3 py-1.5 text-sm rounded border border-border bg-surface-1 text-primary placeholder:text-tertiary focus:outline-none focus:ring-1 focus:ring-accent w-64"
    />
    {#if filterTag}
      <button
        onclick={() => filterTag = ''}
        class="text-xs text-accent hover:underline"
      >
        Clear
      </button>
    {/if}
    <span class="text-sm text-secondary ml-auto">{filteredNodes.length} nodes</span>
  </div>

  {#if loading}
    <PlanesLoader message="Loading nodes..." />
  {:else if error}
    <div class="rounded-lg border border-error/20 bg-error/10 p-4 text-error">{error}</div>
  {:else}
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr class="border-b border-border">
            <th class="table-header">Name</th>
            <th class="table-header">Status</th>
            <th class="table-header">Roles</th>
            <th class="table-header">CPU</th>
            <th class="table-header">Memory</th>
            <th class="table-header">Pods</th>
            <th class="table-header">Age</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredNodes as node}
            {@const r = getNodeResources(node)}
            <tr
              class="table-row table-row-interactive"
              onclick={() => goto(`/kubernetes/nodes/${node.name}`)}
              role="button"
              tabindex="0"
              onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && goto(`/kubernetes/nodes/${node.name}`)}
            >
              <td class="table-cell font-medium text-text-primary">{node.name}</td>
              <td class="table-cell">
                <StatusIndicator status={node.status} />
              </td>
              <td class="table-cell">
                <div class="flex flex-wrap gap-1">
                  {#each node.roles ?? [] as role}
                    <span class="badge badge-accent">{role}</span>
                  {/each}
                </div>
              </td>
              <td class="table-cell">
                <div class="w-24">
                  <div class="text-xs text-text-secondary mb-1">
                    {formatCpu(r.cpuUsed)} / {formatCpu(r.cpuCapacity)}
                  </div>
                  <div class="h-1.5 bg-surface-2 rounded-full overflow-hidden">
                    <div
                      class="h-full {getUsageColor(r.cpuUsed, r.cpuCapacity)} rounded-full"
                      style="width: {r.cpuCapacity > 0 ? (r.cpuUsed / r.cpuCapacity) * 100 : 0}%"
                    ></div>
                  </div>
                </div>
              </td>
              <td class="table-cell">
                <div class="w-24">
                  <div class="text-xs text-text-secondary mb-1">
                    {formatMem(r.memUsed)} / {formatMem(r.memCapacity)}
                  </div>
                  <div class="h-1.5 bg-surface-2 rounded-full overflow-hidden">
                    <div
                      class="h-full {getUsageColor(r.memUsed, r.memCapacity)} rounded-full"
                      style="width: {r.memCapacity > 0 ? (r.memUsed / r.memCapacity) * 100 : 0}%"
                    ></div>
                  </div>
                </div>
              </td>
              <td class="table-cell">
                <div class="w-20">
                  <div class="text-xs text-text-secondary mb-1">
                    {r.podsUsed} / {r.podsCapacity}
                  </div>
                  <div class="h-1.5 bg-surface-2 rounded-full overflow-hidden">
                    <div
                      class="h-full {getUsageColor(r.podsUsed, r.podsCapacity)} rounded-full"
                      style="width: {r.podsCapacity > 0 ? (r.podsUsed / r.podsCapacity) * 100 : 0}%"
                    ></div>
                  </div>
                </div>
              </td>
              <td class="table-cell">
                <ResourceAge timestamp={node.createdAt} />
              </td>
            </tr>
          {:else}
            <tr>
              <td colspan="7" class="table-empty">No nodes found</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
