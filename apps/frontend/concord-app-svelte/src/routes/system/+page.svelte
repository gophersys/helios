<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { fade } from 'svelte/transition';
  import { loaderOut, contentIn, errorIn } from '$lib/utils/transitions';
  import { Server, AlertTriangle } from 'lucide-svelte';
  import { api } from '$lib/api';
  import ProgressRing from '$lib/components/system/progress-ring.svelte';
  import StatusIndicator from '$lib/components/system/status-indicator.svelte';
  import ResourceAge from '$lib/components/system/resource-age.svelte';
  import { formatCpu, formatMem, parseCpuMillis, parseMemoryMi } from '$lib/components/system/k8s-resources';
  import PlanesLoader from '$lib/components/ui/planes-loader.svelte';

  interface ClusterInfo {
    name: string;
    version: string;
    platform: string;
    nodeCount: number;
    podCount: number;
    namespaceCount: number;
  }

  // Matches backend: apps/backend/http-api/src/services/kubernetes/serializers.py
  interface NodeSummary {
    name: string;
    status: string;
    roles: string[];
    capacity: { cpu: string; memory: string; pods: string };
    allocatable: { cpu: string; memory: string; pods: string };
    allocated: { cpuRequests: string; memoryRequests: string; podCount: number };
  }

  interface K8sEvent {
    type: string;
    reason: string;
    message: string;
    object: string;
    namespace: string;
    count: number;
    lastSeen: string;
  }

  let cluster = $state<ClusterInfo | null>(null);
  let nodes = $state<NodeSummary[]>([]);
  let events = $state<K8sEvent[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let pollInterval: ReturnType<typeof setInterval>;

  async function fetchData() {
    try {
      // Fetch cluster info
      const clusterRes = await api.get<{ data: ClusterInfo }>('/v2/system/cluster');
      console.log('cluster response:', clusterRes);
      if (clusterRes?.data) {
        cluster = clusterRes.data;
      }

      // Fetch nodes (may fail if not available)
      try {
        const nodesRes = await api.get<{ data: NodeSummary[] }>('/v2/system/nodes');
        console.log('nodes response:', nodesRes);
        if (nodesRes?.data) {
          nodes = nodesRes.data;
        }
      } catch (e) {
        console.warn('Failed to load nodes:', e);
      }

      // Fetch events (may fail if not available)
      try {
        const eventsRes = await api.get<{ data: K8sEvent[] }>('/v2/system/events?limit=10');
        console.log('events response:', eventsRes);
        if (eventsRes?.data) {
          events = eventsRes.data;
        }
      } catch (e) {
        console.warn('Failed to load events:', e);
      }

      error = null;
    } catch (e) {
      console.error('Failed to load cluster data:', e);
      error = e instanceof Error ? e.message : 'Failed to load cluster data';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    fetchData();
    pollInterval = setInterval(fetchData, 15000);
  });

  onDestroy(() => {
    if (pollInterval) clearInterval(pollInterval);
  });

  // Parse string values from backend into numbers (millicores for CPU, Mi for memory)
  const totalCpu = $derived(nodes.reduce((sum, n) => sum + parseCpuMillis(n.capacity?.cpu ?? '0'), 0));
  const usedCpu = $derived(nodes.reduce((sum, n) => sum + parseCpuMillis(n.allocated?.cpuRequests ?? '0'), 0));
  const totalMem = $derived(nodes.reduce((sum, n) => sum + parseMemoryMi(n.capacity?.memory ?? '0'), 0));
  const usedMem = $derived(nodes.reduce((sum, n) => sum + parseMemoryMi(n.allocated?.memoryRequests ?? '0'), 0));
  const totalPods = $derived(nodes.reduce((sum, n) => sum + parseInt(n.capacity?.pods ?? '0', 10), 0));
  const usedPods = $derived(nodes.reduce((sum, n) => sum + (n.allocated?.podCount ?? 0), 0));
</script>

{#if loading}
  <div class="flex items-center justify-center py-12" out:fade={loaderOut}>
    <PlanesLoader size="md" planeCount={5} message="Loading cluster information..." />
  </div>
{:else if error}
  <div class="rounded-lg border border-error/20 bg-error/10 p-4" in:fade={errorIn}>
    <div class="flex items-center gap-2 text-error">
      <AlertTriangle class="w-5 h-5" />
      <span>{error}</span>
    </div>
  </div>
{:else}
  <div class="space-y-6" in:fade={contentIn}>
    <!-- Cluster Info Card -->
    {#if cluster}
      <div class="card card-md">
        <div class="flex items-start gap-4">
          <div class="p-3 rounded-lg bg-accent/10">
            <Server class="w-6 h-6 text-accent" />
          </div>
          <div class="flex-1">
            <h2 class="text-lg font-semibold text-primary">{cluster.name}</h2>
            <div class="mt-2 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span class="text-secondary">Version:</span>
                <span class="ml-1 text-primary font-mono">{cluster.version}</span>
              </div>
              <div>
                <span class="text-secondary">Platform:</span>
                <span class="ml-1 text-primary">{cluster.platform}</span>
              </div>
              <div>
                <span class="text-secondary">Nodes:</span>
                <span class="ml-1 text-primary font-semibold">{cluster.nodeCount}</span>
              </div>
              <div>
                <span class="text-secondary">Namespaces:</span>
                <span class="ml-1 text-primary font-semibold">{cluster.namespaceCount}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    {/if}

    <!-- Resource Usage -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div class="card card-sm">
        <div class="flex items-center gap-4">
          <ProgressRing value={usedCpu} max={totalCpu} label="CPU" />
          <div class="flex-1">
            <div class="text-sm text-secondary">Allocated</div>
            <div class="text-lg font-semibold text-primary">{formatCpu(usedCpu)}</div>
            <div class="text-xs text-tertiary">of {formatCpu(totalCpu)}</div>
          </div>
        </div>
      </div>

      <div class="card card-sm">
        <div class="flex items-center gap-4">
          <ProgressRing value={usedMem} max={totalMem} label="Memory" />
          <div class="flex-1">
            <div class="text-sm text-secondary">Allocated</div>
            <div class="text-lg font-semibold text-primary">{formatMem(usedMem)}</div>
            <div class="text-xs text-tertiary">of {formatMem(totalMem)}</div>
          </div>
        </div>
      </div>

      <div class="card card-sm">
        <div class="flex items-center gap-4">
          <ProgressRing value={usedPods} max={totalPods} label="Pods" centerText={`${usedPods}`} />
          <div class="flex-1">
            <div class="text-sm text-secondary">Running</div>
            <div class="text-lg font-semibold text-primary">{usedPods}</div>
            <div class="text-xs text-tertiary">of {totalPods} capacity</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Nodes Grid -->
    <div>
      <h3 class="text-lg font-semibold text-primary mb-3">Nodes</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {#each nodes as node}
          <button
            onclick={() => goto(`/system/nodes/${node.name}`)}
            class="text-left card card-sm card-interactive"
          >
            <div class="flex items-center justify-between mb-2">
              <span class="font-medium text-primary">{node.name}</span>
              <StatusIndicator status={node.status ?? 'Unknown'} />
            </div>
            {#if node.roles?.length}
              <div class="flex flex-wrap gap-1 mb-3">
                {#each node.roles as role}
                  <span class="px-1.5 py-0.5 rounded text-2xs bg-accent/10 text-accent">{role}</span>
                {/each}
              </div>
            {/if}
            {#if node.capacity || node.allocated}
              {@const cpuCapacity = parseCpuMillis(node.capacity?.cpu ?? '0')}
              {@const cpuUsed = parseCpuMillis(node.allocated?.cpuRequests ?? '0')}
              {@const memCapacity = parseMemoryMi(node.capacity?.memory ?? '0')}
              {@const memUsed = parseMemoryMi(node.allocated?.memoryRequests ?? '0')}
              <div class="space-y-2 text-xs">
                {#if node.capacity?.cpu}
                  <div class="flex justify-between">
                    <span class="text-secondary">CPU</span>
                    <span class="text-primary">{formatCpu(cpuUsed)} / {formatCpu(cpuCapacity)}</span>
                  </div>
                  <div class="h-1 bg-surface-2 rounded-full overflow-hidden">
                    <div
                      class="h-full bg-accent rounded-full"
                      style="width: {cpuCapacity > 0 ? (cpuUsed / cpuCapacity) * 100 : 0}%"
                    ></div>
                  </div>
                {/if}
                {#if node.capacity?.memory}
                  <div class="flex justify-between">
                    <span class="text-secondary">Memory</span>
                    <span class="text-primary">{formatMem(memUsed)} / {formatMem(memCapacity)}</span>
                  </div>
                  <div class="h-1 bg-surface-2 rounded-full overflow-hidden">
                    <div
                      class="h-full bg-accent rounded-full"
                      style="width: {memCapacity > 0 ? (memUsed / memCapacity) * 100 : 0}%"
                    ></div>
                  </div>
                {/if}
              </div>
            {/if}
          </button>
        {/each}
      </div>
    </div>

    <!-- Recent Events -->
    <div>
      <div class="flex items-center justify-between mb-4">
        <h3 class="section-title">Recent Events</h3>
        <a href="/system/events" class="text-sm text-accent hover:underline">View all</a>
      </div>
      <div class="table-wrapper">
        <table class="table">
          <thead>
            <tr class="border-b border-border">
              <th class="table-header">Type</th>
              <th class="table-header">Reason</th>
              <th class="table-header">Object</th>
              <th class="table-header">Message</th>
              <th class="table-header">Age</th>
            </tr>
          </thead>
          <tbody>
            {#each events as event}
              <tr class="table-row">
                <td class="table-cell">
                  <StatusIndicator status={event.type} />
                </td>
                <td class="table-cell font-medium text-text-primary">{event.reason}</td>
                <td class="table-cell font-mono text-text-secondary">{event.object}</td>
                <td class="table-cell text-text-secondary truncate max-w-xs" title={event.message}>
                  {event.message}
                </td>
                <td class="table-cell">
                  <ResourceAge timestamp={event.lastSeen} />
                </td>
              </tr>
            {:else}
              <tr>
                <td colspan="5" class="table-empty">No recent events</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  </div>
{/if}
