<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { ArrowLeft, RefreshCw, FileCode } from 'lucide-svelte';
  import { api } from '$lib/api';
  import { getAuth } from '$lib/stores/auth.svelte';
  import StatusIndicator from '$lib/components/system/status-indicator.svelte';
  import ResourceAge from '$lib/components/system/resource-age.svelte';
  import LabelList from '$lib/components/system/label-list.svelte';
  import MetricCard from '$lib/components/system/metric-card.svelte';
  import CollapsibleSection from '$lib/components/system/collapsible-section.svelte';
  import ActionButton from '$lib/components/system/action-button.svelte';
  import ResourceYamlDialog from '$lib/components/system/resource-yaml-dialog.svelte';
  import PlanesLoader from '$lib/components/ui/planes-loader.svelte';

  interface DeploymentCondition {
    type: string;
    status: string;
    reason: string;
    message: string;
  }

  interface DeploymentPod {
    name: string;
    namespace: string;
    status: string;
    ready: boolean;
    restarts: number;
    nodeName: string;
  }

  interface ContainerSpec {
    name: string;
    image: string;
  }

  interface DeploymentDetailData {
    name: string;
    namespace: string;
    replicas: {
      desired: number;
      ready: number;
      available: number;
      updated: number;
    };
    strategy: string;
    createdAt: string;
    containers: ContainerSpec[];
    conditions: DeploymentCondition[];
    selector: Record<string, string>;
    labels: Record<string, string>;
    pods: DeploymentPod[];
  }

  const namespace = $derived($page.params.namespace);
  const deploymentName = $derived($page.params.name);

  let deployment = $state<DeploymentDetailData | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let showYaml = $state(false);
  let scaleValue = $state(0);
  let scaling = $state(false);
  let restarting = $state(false);
  let mutationError = $state<string | null>(null);

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('system:manage'));

  async function fetchDeployment() {
    loading = true;
    try {
      const res = await api.get<{ data: DeploymentDetailData }>(`/v2/kubernetes/deployments/${namespace}/${deploymentName}`);
      if (res?.data) {
        deployment = res.data;
        scaleValue = res.data.replicas.desired;
      }
      error = null;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load deployment';
    } finally {
      loading = false;
    }
  }

  async function scaleDeployment() {
    scaling = true;
    mutationError = null;
    try {
      await api.post(`/v2/kubernetes/deployments/${namespace}/${deploymentName}/scale`, { replicas: scaleValue });
      await fetchDeployment();
    } catch (e) {
      mutationError = e instanceof Error ? e.message : 'Failed to scale deployment';
    } finally {
      scaling = false;
    }
  }

  async function restartDeployment() {
    restarting = true;
    mutationError = null;
    try {
      await api.post(`/v2/kubernetes/deployments/${namespace}/${deploymentName}/restart`);
      await fetchDeployment();
    } catch (e) {
      mutationError = e instanceof Error ? e.message : 'Failed to restart deployment';
    } finally {
      restarting = false;
    }
  }

  let pollInterval: ReturnType<typeof setInterval>;

  onMount(() => {
    if (!auth.hasPermission('system:view')) {
      goto('/');
      return;
    }
    fetchDeployment();
    pollInterval = setInterval(fetchDeployment, 5000);
  });

  onDestroy(() => {
    if (pollInterval) clearInterval(pollInterval);
  });

  const status = $derived.by(() => {
    if (!deployment) return 'Unknown';
    if (deployment.replicas.available === deployment.replicas.desired && deployment.replicas.desired > 0) return 'Ready';
    if (deployment.replicas.available > 0) return 'Pending';
    return 'NotReady';
  });

  const canScale = $derived(
    canManage && deployment && scaleValue !== deployment.replicas.desired && !scaling
  );
</script>

<div class="space-y-6">
  <!-- Back Button -->
  <button
    onclick={() => goto('/kubernetes/deployments')}
    class="flex items-center gap-1 text-sm text-secondary hover:text-primary"
  >
    <ArrowLeft class="w-4 h-4" />
    Back to Deployments
  </button>

  {#if loading}
    <PlanesLoader message="Loading deployment details..." />
  {:else if error}
    <div class="rounded-lg border border-error/20 bg-error/10 p-4 text-error">{error}</div>
  {:else if deployment}
    <!-- Header -->
    <div class="flex items-start justify-between">
      <div>
        <div class="flex items-center gap-3">
          <h2 class="text-xl font-semibold text-primary">{deployment.name}</h2>
          <StatusIndicator status={status} />
        </div>
        <div class="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-sm">
          <span class="text-secondary">Namespace: <span class="text-primary">{deployment.namespace}</span></span>
          <span class="text-border">|</span>
          <span class="text-secondary">Strategy: <span class="text-primary">{deployment.strategy}</span></span>
          <span class="text-border">|</span>
          <span class="text-secondary">Age: <ResourceAge timestamp={deployment.createdAt} /></span>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button
          onclick={() => showYaml = true}
          class="flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded bg-surface-2 text-secondary hover:bg-surface-2/80"
        >
          <FileCode class="w-4 h-4" />
          YAML
        </button>
        {#if canManage}
          <ActionButton
            label="Restart"
            icon={RefreshCw}
            variant="warning"
            confirmMessage="Restart all pods?"
            onConfirm={restartDeployment}
            disabled={restarting}
          />
        {/if}
      </div>
    </div>

    {#if mutationError}
      <div class="rounded-lg border border-error/20 bg-error/10 p-3 text-sm text-error">{mutationError}</div>
    {/if}

    <!-- Replica Metrics -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <MetricCard
        label="Desired"
        value={deployment.replicas.desired}
        status="neutral"
      />
      <MetricCard
        label="Ready"
        value={deployment.replicas.ready}
        status={deployment.replicas.ready === deployment.replicas.desired ? 'success' : 'warning'}
      />
      <MetricCard
        label="Available"
        value={deployment.replicas.available}
        status={deployment.replicas.available === deployment.replicas.desired ? 'success' : 'warning'}
      />
      <MetricCard
        label="Updated"
        value={deployment.replicas.updated}
        status="neutral"
      />
    </div>

    <!-- Scale Control -->
    {#if canManage}
      <div class="card card-sm">
        <h3 class="text-sm font-medium text-primary mb-3">Scale Deployment</h3>
        <div class="flex items-center gap-3">
          <input
            type="number"
            bind:value={scaleValue}
            min="0"
            max="100"
            class="w-24 px-3 py-1.5 text-sm rounded border border-border bg-surface-0 text-primary focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <button
            onclick={scaleDeployment}
            disabled={!canScale}
            class="px-3 py-1.5 text-sm font-medium rounded bg-accent text-white hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {scaling ? 'Scaling...' : 'Apply'}
          </button>
        </div>
      </div>
    {/if}

    <!-- Container Images -->
    <div>
      <h3 class="text-lg font-semibold text-primary mb-3">Container Images</h3>
      <div class="space-y-2">
        {#each deployment.containers as container}
          <div class="flex items-center gap-2 text-sm">
            <span class="text-secondary">{container.name}:</span>
            <span class="font-mono text-primary truncate" title={container.image}>{container.image}</span>
          </div>
        {/each}
      </div>
    </div>

    <!-- Pods -->
    <div>
      <h3 class="text-lg font-semibold text-text-primary mb-3">Pods ({deployment.pods.length})</h3>
      <div class="table-wrapper">
        <table class="table">
          <thead>
            <tr class="border-b border-border">
              <th class="table-header">Name</th>
              <th class="table-header">Status</th>
              <th class="table-header">Ready</th>
              <th class="table-header">Restarts</th>
              <th class="table-header">Node</th>
            </tr>
          </thead>
          <tbody>
            {#each deployment.pods as pod}
              <tr
                class="table-row table-row-interactive"
                onclick={() => goto(`/kubernetes/pods/${pod.namespace}/${pod.name}`)}
                role="button"
                tabindex="0"
                onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && goto(`/kubernetes/pods/${pod.namespace}/${pod.name}`)}
              >
                <td class="table-cell font-medium text-text-primary">{pod.name}</td>
                <td class="table-cell">
                  <StatusIndicator status={pod.status} />
                </td>
                <td class="table-cell {pod.ready ? 'text-success' : 'text-error'}">
                  {pod.ready ? 'Yes' : 'No'}
                </td>
                <td class="table-cell {pod.restarts > 0 ? 'font-bold text-warning' : 'text-text-secondary'}">
                  {pod.restarts}
                </td>
                <td class="table-cell text-text-secondary">{pod.nodeName}</td>
              </tr>
            {:else}
              <tr>
                <td colspan="5" class="table-empty">No pods</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Conditions -->
    <CollapsibleSection title="Conditions" count={deployment.conditions.length}>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-tertiary">
              <th class="px-2 py-1">Type</th>
              <th class="px-2 py-1">Status</th>
              <th class="px-2 py-1">Reason</th>
              <th class="px-2 py-1">Message</th>
            </tr>
          </thead>
          <tbody>
            {#each deployment.conditions as condition}
              <tr>
                <td class="px-2 py-1 font-medium text-primary">{condition.type}</td>
                <td class="px-2 py-1">
                  <StatusIndicator status={condition.status === 'True' ? 'Ready' : 'NotReady'} />
                </td>
                <td class="px-2 py-1 text-secondary">{condition.reason}</td>
                <td class="px-2 py-1 text-secondary truncate max-w-xs" title={condition.message}>
                  {condition.message}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </CollapsibleSection>

    <!-- Labels -->
    <CollapsibleSection title="Labels" count={Object.keys(deployment.labels).length}>
      <LabelList labels={deployment.labels} />
    </CollapsibleSection>

    <!-- YAML Dialog -->
    <ResourceYamlDialog
      kind="Deployment"
      {namespace}
      name={deploymentName}
      open={showYaml}
      onclose={() => showYaml = false}
    />
  {/if}
</div>
