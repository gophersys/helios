<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { ArrowLeft, Server, Cpu, MemoryStick, Box, Tag, Shield } from 'lucide-svelte';
  import { api } from '$lib/api';
  import { getAuth } from '$lib/stores/auth.svelte';
  import StatusIndicator from '$lib/components/system/status-indicator.svelte';
  import ProgressRing from '$lib/components/system/progress-ring.svelte';
  import UsageBar from '$lib/components/system/usage-bar.svelte';
  import LabelList from '$lib/components/system/label-list.svelte';
  import ResourceAge from '$lib/components/system/resource-age.svelte';
  import { formatCpu, formatMem, parseCpuMillis, parseMemoryMi } from '$lib/components/system/k8s-resources';

  interface NodeCondition {
    type: string;
    status: string;
    reason: string;
    message: string;
  }

  interface NodeTaint {
    key: string;
    value: string;
    effect: string;
  }

  interface PodOnNode {
    name: string;
    namespace: string;
    status: string;
    restarts: number;
  }

  // Matches backend: apps/backend/http-api/src/services/kubernetes/serializers.py
  interface NodeDetailData {
    name: string;
    status: string;
    roles: string[];
    internalIp: string;
    osImage: string;
    architecture: string;
    containerRuntime: string;
    kubeletVersion: string;
    unschedulable: boolean;
    createdAt: string;
    capacity: { cpu: string; memory: string; pods: string };
    allocatable: { cpu: string; memory: string; pods: string };
    allocated: { cpuRequests: string; memoryRequests: string; podCount: number };
    conditions: NodeCondition[];
    labels: Record<string, string>;
    taints: NodeTaint[];
    pods: PodOnNode[];
  }

  const auth = getAuth();
  const nodeName = $derived($page.params.name);

  let node = $state<NodeDetailData | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Computed numeric values for display
  const cpuAllocatable = $derived(node ? parseCpuMillis(node.allocatable?.cpu ?? '0') : 0);
  const cpuUsed = $derived(node ? parseCpuMillis(node.allocated?.cpuRequests ?? '0') : 0);
  const memAllocatable = $derived(node ? parseMemoryMi(node.allocatable?.memory ?? '0') : 0);
  const memUsed = $derived(node ? parseMemoryMi(node.allocated?.memoryRequests ?? '0') : 0);
  const podsAllocatable = $derived(node ? parseInt(node.allocatable?.pods ?? '0', 10) : 0);
  const podsUsed = $derived(node?.allocated?.podCount ?? 0);

  async function fetchNode() {
    loading = true;
    try {
      const res = await api.get<{ data: NodeDetailData }>(`/v2/kubernetes/nodes/${nodeName}`);
      if (res?.data) node = res.data;
      error = null;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load node';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.System.View')) {
      goto('/');
      return;
    }
    fetchNode();
  });

  function getConditionColor(condition: NodeCondition): string {
    const healthyConditions = ['Ready'];
    const unhealthyIfTrue = ['MemoryPressure', 'DiskPressure', 'PIDPressure', 'NetworkUnavailable'];

    if (healthyConditions.includes(condition.type)) {
      return condition.status === 'True' ? 'bg-success/10' : 'bg-warning/10';
    }
    if (unhealthyIfTrue.includes(condition.type)) {
      return condition.status === 'True' ? 'bg-warning/10' : 'bg-success/10';
    }
    return 'bg-surface-2';
  }
</script>

<div class="space-y-6">
  <!-- Back Button -->
  <button
    onclick={() => goto('/kubernetes/nodes')}
    class="flex items-center gap-1 text-sm text-secondary hover:text-primary"
  >
    <ArrowLeft class="w-4 h-4" />
    Back to Nodes
  </button>

  {#if loading}
    <div class="flex items-center justify-center py-12">
      <span class="text-secondary">Loading node details...</span>
    </div>
  {:else if error}
    <div class="rounded-lg border border-error/20 bg-error/10 p-4 text-error">{error}</div>
  {:else if node}
    <!-- Header Card -->
    <div class="card card-md">
      <div class="flex items-start gap-4">
        <div class="p-3 rounded-lg {node.status === 'Ready' ? 'bg-success/10' : 'bg-error/10'}">
          <Server class="w-6 h-6 {node.status === 'Ready' ? 'text-success' : 'text-error'}" />
        </div>
        <div class="flex-1">
          <div class="flex items-center gap-3 flex-wrap">
            <h2 class="text-xl font-semibold text-primary">{node.name}</h2>
            <StatusIndicator status={node.status} />
            {#if node.unschedulable}
              <span class="px-2 py-0.5 rounded text-xs bg-warning/10 text-warning">Unschedulable</span>
            {/if}
          </div>
          <div class="flex flex-wrap gap-1 mt-2">
            {#each node.roles as role}
              <span class="px-2 py-0.5 rounded text-xs bg-accent/10 text-accent">{role}</span>
            {/each}
          </div>
          <div class="mt-4 grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
            <div>
              <span class="text-secondary">Internal IP:</span>
              <span class="ml-1 text-primary font-mono">{node.internalIp}</span>
            </div>
            <div>
              <span class="text-secondary">OS Image:</span>
              <span class="ml-1 text-primary">{node.osImage}</span>
            </div>
            <div>
              <span class="text-secondary">Architecture:</span>
              <span class="ml-1 text-primary">{node.architecture}</span>
            </div>
            <div>
              <span class="text-secondary">Container Runtime:</span>
              <span class="ml-1 text-primary font-mono">{node.containerRuntime}</span>
            </div>
            <div>
              <span class="text-secondary">Kubelet:</span>
              <span class="ml-1 text-primary font-mono">{node.kubeletVersion}</span>
            </div>
            <div>
              <span class="text-secondary">Age:</span>
              <span class="ml-1"><ResourceAge timestamp={node.createdAt} /></span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Resource Usage -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div class="card card-sm">
        <div class="flex items-center gap-3 mb-3">
          <Cpu class="w-5 h-5 text-tertiary" />
          <span class="font-medium text-primary">CPU Requests</span>
        </div>
        <div class="flex items-center gap-4">
          <ProgressRing
            value={cpuUsed}
            max={cpuAllocatable}
            size={70}
          />
          <div class="flex-1">
            <UsageBar
              label="Allocated"
              used={cpuUsed}
              total={cpuAllocatable}
              formatFn={formatCpu}
            />
          </div>
        </div>
      </div>

      <div class="card card-sm">
        <div class="flex items-center gap-3 mb-3">
          <MemoryStick class="w-5 h-5 text-tertiary" />
          <span class="font-medium text-primary">Memory Requests</span>
        </div>
        <div class="flex items-center gap-4">
          <ProgressRing
            value={memUsed}
            max={memAllocatable}
            size={70}
          />
          <div class="flex-1">
            <UsageBar
              label="Allocated"
              used={memUsed}
              total={memAllocatable}
              formatFn={formatMem}
            />
          </div>
        </div>
      </div>

      <div class="card card-sm">
        <div class="flex items-center gap-3 mb-3">
          <Box class="w-5 h-5 text-tertiary" />
          <span class="font-medium text-primary">Pods</span>
        </div>
        <div class="flex items-center gap-4">
          <ProgressRing
            value={podsUsed}
            max={podsAllocatable}
            size={70}
            centerText={`${podsUsed}`}
          />
          <div class="flex-1">
            <UsageBar
              label="Running"
              used={podsUsed}
              total={podsAllocatable}
              unit=" pods"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Conditions -->
    <div>
      <h3 class="text-lg font-semibold text-primary mb-3">Conditions</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        {#each node.conditions as condition}
          <div class="rounded-lg border border-border {getConditionColor(condition)} p-3">
            <div class="flex items-center justify-between mb-1">
              <span class="font-medium text-primary">{condition.type}</span>
              <StatusIndicator status={condition.status === 'True' ? 'Ready' : 'NotReady'} />
            </div>
            <div class="text-xs text-secondary">
              {condition.reason}
            </div>
            {#if condition.message}
              <div class="text-xs text-tertiary mt-1 truncate" title={condition.message}>
                {condition.message}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    </div>

    <!-- Pods on Node -->
    <div>
      <h3 class="text-lg font-semibold text-text-primary mb-3">Pods ({node.pods.length})</h3>
      <div class="table-wrapper">
        <table class="table">
          <thead>
            <tr class="border-b border-border">
              <th class="table-header">Name</th>
              <th class="table-header">Namespace</th>
              <th class="table-header">Status</th>
              <th class="table-header">Restarts</th>
            </tr>
          </thead>
          <tbody>
            {#each node.pods as pod}
              <tr
                class="table-row table-row-interactive"
                onclick={() => goto(`/kubernetes/pods/${pod.namespace}/${pod.name}`)}
                role="button"
                tabindex="0"
                onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && goto(`/kubernetes/pods/${pod.namespace}/${pod.name}`)}
              >
                <td class="table-cell font-medium text-text-primary">{pod.name}</td>
                <td class="table-cell text-text-secondary">{pod.namespace}</td>
                <td class="table-cell">
                  <StatusIndicator status={pod.status} />
                </td>
                <td class="table-cell {pod.restarts > 0 ? 'font-bold text-warning' : 'text-text-secondary'}">
                  {pod.restarts}
                </td>
              </tr>
            {:else}
              <tr>
                <td colspan="4" class="table-empty">No pods on this node</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Labels & Taints -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <div class="flex items-center gap-2 mb-3">
          <Tag class="w-4 h-4 text-tertiary" />
          <h3 class="text-lg font-semibold text-primary">Labels</h3>
        </div>
        <div class="card card-sm max-h-48 overflow-y-auto">
          <LabelList labels={node.labels} />
        </div>
      </div>

      <div>
        <div class="flex items-center gap-2 mb-3">
          <Shield class="w-4 h-4 text-tertiary" />
          <h3 class="text-lg font-semibold text-primary">Taints</h3>
        </div>
        <div class="card card-sm">
          {#if node.taints.length === 0}
            <span class="text-sm text-tertiary">No taints</span>
          {:else}
            <div class="space-y-2">
              {#each node.taints as taint}
                <div class="flex items-center gap-2">
                  <span class="px-1.5 py-0.5 rounded text-2xs bg-warning/10 text-warning">{taint.effect}</span>
                  <span class="text-sm font-mono text-secondary">{taint.key}={taint.value || '<none>'}</span>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</div>
