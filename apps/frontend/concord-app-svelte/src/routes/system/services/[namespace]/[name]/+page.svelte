<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { ArrowLeft, FileCode } from 'lucide-svelte';
  import { api } from '$lib/api';
  import ResourceAge from '$lib/components/system/resource-age.svelte';
  import LabelList from '$lib/components/system/label-list.svelte';
  import ResourceYamlDialog from '$lib/components/system/resource-yaml-dialog.svelte';

  interface ServicePort {
    name: string;
    port: number;
    targetPort: number | string;
    protocol: string;
    nodePort?: number;
  }

  interface Endpoint {
    addresses: string[];
    ports: { port: number; protocol: string }[];
  }

  interface ServiceDetailData {
    name: string;
    namespace: string;
    type: string;
    clusterIp: string;
    externalIps: string[];
    loadBalancerIp: string | null;
    ports: ServicePort[];
    selector: Record<string, string>;
    endpoints: Endpoint[];
    createdAt: string;
  }

  const namespace = $derived($page.params.namespace);
  const serviceName = $derived($page.params.name);

  let service = $state<ServiceDetailData | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let showYaml = $state(false);

  async function fetchService() {
    loading = true;
    try {
      const res = await api.get<{ data: ServiceDetailData }>(`/v2/system/services/${namespace}/${serviceName}`);
      if (res?.data) service = res.data;
      error = null;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load service';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    fetchService();
  });
</script>

<div class="space-y-6">
  <!-- Back Button -->
  <button
    onclick={() => goto('/system/services')}
    class="flex items-center gap-1 text-sm text-secondary hover:text-primary"
  >
    <ArrowLeft class="w-4 h-4" />
    Back to Services
  </button>

  {#if loading}
    <div class="flex items-center justify-center py-12">
      <span class="text-secondary">Loading service details...</span>
    </div>
  {:else if error}
    <div class="rounded-lg border border-error/20 bg-error/10 p-4 text-error">{error}</div>
  {:else if service}
    <!-- Header -->
    <div class="flex items-start justify-between">
      <div>
        <h2 class="text-xl font-semibold text-primary">{service.name}</h2>
        <div class="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-sm">
          <span class="text-secondary">Namespace: <span class="text-primary">{service.namespace}</span></span>
          <span class="text-border">|</span>
          <span class="text-secondary">Type: <span class="text-primary">{service.type}</span></span>
          <span class="text-border">|</span>
          <span class="text-secondary">Cluster IP: <span class="text-primary font-mono">{service.clusterIp || 'None'}</span></span>
          {#if service.loadBalancerIp}
            <span class="text-border">|</span>
            <span class="text-secondary">LB IP: <span class="text-primary font-mono">{service.loadBalancerIp}</span></span>
          {/if}
          <span class="text-border">|</span>
          <span class="text-secondary">Age: <ResourceAge timestamp={service.createdAt} /></span>
        </div>
      </div>
      <button
        onclick={() => showYaml = true}
        class="flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded bg-surface-2 text-secondary hover:bg-surface-2/80"
      >
        <FileCode class="w-4 h-4" />
        YAML
      </button>
    </div>

    <!-- Ports -->
    <div>
      <h3 class="text-lg font-semibold text-text-primary mb-3">Ports</h3>
      <div class="table-wrapper">
        <table class="table">
          <thead>
            <tr class="border-b border-border">
              <th class="table-header">Name</th>
              <th class="table-header">Port</th>
              <th class="table-header">Target Port</th>
              <th class="table-header">Protocol</th>
              <th class="table-header">Node Port</th>
            </tr>
          </thead>
          <tbody>
            {#each service.ports as port}
              <tr class="table-row">
                <td class="table-cell text-text-primary">{port.name || '-'}</td>
                <td class="table-cell font-mono text-text-secondary">{port.port}</td>
                <td class="table-cell font-mono text-text-secondary">{port.targetPort}</td>
                <td class="table-cell text-text-secondary">{port.protocol}</td>
                <td class="table-cell font-mono text-text-secondary">{port.nodePort || '-'}</td>
              </tr>
            {:else}
              <tr>
                <td colspan="5" class="table-empty">No ports defined</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Endpoints -->
    <div>
      <h3 class="text-lg font-semibold text-primary mb-3">Endpoints</h3>
      <div class="card card-sm">
        {#if service.endpoints.length === 0}
          <span class="text-sm text-tertiary">No endpoints</span>
        {:else}
          <div class="space-y-3">
            {#each service.endpoints as endpoint, i}
              <div class="text-sm">
                <div class="text-secondary mb-1">Endpoint {i + 1}:</div>
                <div class="pl-4 space-y-1">
                  <div>
                    <span class="text-tertiary">Addresses:</span>
                    <span class="font-mono text-primary break-all">{endpoint.addresses.join(', ')}</span>
                  </div>
                  <div>
                    <span class="text-tertiary">Ports:</span>
                    <span class="font-mono text-primary">
                      {endpoint.ports.map(p => `${p.port}/${p.protocol}`).join(', ')}
                    </span>
                  </div>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </div>

    <!-- Selector -->
    <div>
      <h3 class="text-lg font-semibold text-primary mb-3">Selector</h3>
      <div class="card card-sm">
        {#if Object.keys(service.selector).length === 0}
          <span class="text-sm text-tertiary">No selector</span>
        {:else}
          <LabelList labels={service.selector} />
        {/if}
      </div>
    </div>

    <!-- YAML Dialog -->
    <ResourceYamlDialog
      kind="Service"
      {namespace}
      name={serviceName}
      open={showYaml}
      onclose={() => showYaml = false}
    />
  {/if}
</div>
