<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { fade } from 'svelte/transition';
  import { loaderOut, contentIn, errorIn } from '$lib/utils/transitions';
  import { api } from '$lib/api';
  import { getAuth } from '$lib/stores/auth.svelte';
  import StatusIndicator from '$lib/components/system/status-indicator.svelte';
  import ResourceAge from '$lib/components/system/resource-age.svelte';
  import NamespaceSelector from '$lib/components/system/namespace-selector.svelte';
  import PlanesLoader from '$lib/components/ui/planes-loader.svelte';

  interface DeploymentSummary {
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
  }

  let deployments = $state<DeploymentSummary[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let namespace = $state('');
  const auth = getAuth();
  let pollInterval: ReturnType<typeof setInterval>;

  async function fetchDeployments() {
    try {
      const url = namespace ? `/v2/kubernetes/deployments?namespace=${namespace}` : '/v2/kubernetes/deployments';
      const res = await api.get<{ data: DeploymentSummary[] }>(url);
      if (res?.data) deployments = res.data;
      error = null;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load deployments';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.System.View')) {
      goto('/');
      return;
    }
    fetchDeployments();
    pollInterval = setInterval(fetchDeployments, 15000);
  });

  onDestroy(() => {
    if (pollInterval) clearInterval(pollInterval);
  });

  $effect(() => {
    namespace;
    fetchDeployments();
  });

  function getStatus(d: DeploymentSummary): string {
    if (d.replicas.available === d.replicas.desired && d.replicas.desired > 0) return 'Ready';
    if (d.replicas.available > 0) return 'Pending';
    return 'NotReady';
  }
</script>

<div class="space-y-4">
  <!-- Filters -->
  <div class="flex items-center gap-3">
    <NamespaceSelector value={namespace} onchange={(ns) => namespace = ns} />
    <span class="text-sm text-secondary ml-auto">{deployments.length} deployments</span>
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-8" out:fade={loaderOut}>
      <PlanesLoader size="sm" planeCount={4} message="Loading deployments..." />
    </div>
  {:else if error}
    <div class="rounded-lg border border-error/20 bg-error/10 p-4 text-error" in:fade={errorIn}>{error}</div>
  {:else}
    <div class="table-wrapper" in:fade={contentIn}>
      <table class="table">
        <thead>
          <tr class="border-b border-border">
            <th class="table-header">Name</th>
            <th class="table-header">Namespace</th>
            <th class="table-header">Status</th>
            <th class="table-header">Ready</th>
            <th class="table-header">Up-to-date</th>
            <th class="table-header">Available</th>
            <th class="table-header">Strategy</th>
            <th class="table-header">Age</th>
          </tr>
        </thead>
        <tbody>
          {#each deployments as deploy}
            <tr
              class="table-row table-row-interactive"
              onclick={() => goto(`/kubernetes/deployments/${deploy.namespace}/${deploy.name}`)}
              role="button"
              tabindex="0"
              onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && goto(`/kubernetes/deployments/${deploy.namespace}/${deploy.name}`)}
            >
              <td class="table-cell font-medium text-text-primary">{deploy.name}</td>
              <td class="table-cell text-text-secondary">{deploy.namespace}</td>
              <td class="table-cell">
                <StatusIndicator status={getStatus(deploy)} />
              </td>
              <td class="table-cell font-mono {deploy.replicas.ready === deploy.replicas.desired ? 'text-success' : 'text-warning'}">
                {deploy.replicas.ready}/{deploy.replicas.desired}
              </td>
              <td class="table-cell font-mono text-text-secondary">{deploy.replicas.updated}</td>
              <td class="table-cell font-mono text-text-secondary">{deploy.replicas.available}</td>
              <td class="table-cell text-text-secondary">{deploy.strategy}</td>
              <td class="table-cell">
                <ResourceAge timestamp={deploy.createdAt} />
              </td>
            </tr>
          {:else}
            <tr>
              <td colspan="8" class="table-empty">No deployments found</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
