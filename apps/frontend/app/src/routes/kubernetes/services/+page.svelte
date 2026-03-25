<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { fade } from 'svelte/transition';
  import { loaderOut, contentIn, errorIn } from '$lib/utils/transitions';
  import { api } from '$lib/api';
  import { getAuth } from '$lib/stores/auth.svelte';
  import ResourceAge from '$lib/components/system/resource-age.svelte';
  import NamespaceSelector from '$lib/components/system/namespace-selector.svelte';
  import PlanesLoader from '$lib/components/ui/planes-loader.svelte';

  interface ServicePort {
    port: number;
    targetPort: number | string;
    protocol: string;
    nodePort?: number;
  }

  interface ServiceSummary {
    name: string;
    namespace: string;
    type: string;
    clusterIp: string;
    ports: ServicePort[];
    createdAt: string;
  }

  let services = $state<ServiceSummary[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let namespace = $state('');
  const auth = getAuth();
  let pollInterval: ReturnType<typeof setInterval>;

  async function fetchServices() {
    try {
      const url = namespace ? `/v2/kubernetes/services?namespace=${namespace}` : '/v2/kubernetes/services';
      const res = await api.get<{ data: ServiceSummary[] }>(url);
      if (res?.data) services = res.data;
      error = null;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load services';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('system:view')) {
      goto('/');
      return;
    }
    fetchServices();
    pollInterval = setInterval(fetchServices, 15000);
  });

  onDestroy(() => {
    if (pollInterval) clearInterval(pollInterval);
  });

  $effect(() => {
    namespace;
    fetchServices();
  });

  function formatPorts(ports: ServicePort[]): string {
    return ports.map(p => `${p.port}/${p.protocol}`).join(', ');
  }
</script>

<div class="space-y-4">
  <!-- Filters -->
  <div class="flex items-center gap-3">
    <NamespaceSelector value={namespace} onchange={(ns) => namespace = ns} />
    <span class="text-sm text-secondary ml-auto">{services.length} services</span>
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-8" out:fade={loaderOut}>
      <PlanesLoader size="sm" planeCount={4} message="Loading services..." />
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
            <th class="table-header">Type</th>
            <th class="table-header">Cluster IP</th>
            <th class="table-header">Ports</th>
            <th class="table-header">Age</th>
          </tr>
        </thead>
        <tbody>
          {#each services as svc}
            <tr
              class="table-row table-row-interactive"
              onclick={() => goto(`/kubernetes/services/${svc.namespace}/${svc.name}`)}
              role="button"
              tabindex="0"
              onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && goto(`/kubernetes/services/${svc.namespace}/${svc.name}`)}
            >
              <td class="table-cell font-medium text-text-primary">{svc.name}</td>
              <td class="table-cell text-text-secondary">{svc.namespace}</td>
              <td class="table-cell text-text-secondary">{svc.type}</td>
              <td class="table-cell font-mono text-text-secondary">{svc.clusterIp || '-'}</td>
              <td class="table-cell font-mono text-text-secondary">{formatPorts(svc.ports)}</td>
              <td class="table-cell">
                <ResourceAge timestamp={svc.createdAt} />
              </td>
            </tr>
          {:else}
            <tr>
              <td colspan="6" class="table-empty">No services found</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
