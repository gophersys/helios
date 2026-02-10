<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { browser } from '$app/environment';
  import { fade } from 'svelte/transition';
  import { loaderOut, contentIn, errorIn } from '$lib/utils/transitions';
  import { api } from '$lib/api';
  import { getAuth } from '$lib/stores/auth.svelte';
  import StatusIndicator from '$lib/components/system/status-indicator.svelte';
  import ResourceAge from '$lib/components/system/resource-age.svelte';
  import NamespaceSelector from '$lib/components/system/namespace-selector.svelte';
  import PlanesLoader from '$lib/components/ui/planes-loader.svelte';

  interface PodSummary {
    name: string;
    namespace: string;
    status: string;
    ready: string;
    restarts: number;
    nodeName: string;
    createdAt: string;
  }

  let pods = $state<PodSummary[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let namespace = $state('');
  const auth = getAuth();
  let pollInterval: ReturnType<typeof setInterval> | null = null;

  async function fetchPods() {
    try {
      const url = namespace ? `/v2/kubernetes/pods?namespace=${namespace}` : '/v2/kubernetes/pods';
      const res = await api.get<{ data: PodSummary[] }>(url);
      if (res?.data) pods = res.data;
      error = null;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load pods';
    } finally {
      loading = false;
    }
  }

  function startPolling() {
    if (!pollInterval) {
      pollInterval = setInterval(fetchPods, 5000);
    }
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  function handleVisibilityChange() {
    if (document.hidden) {
      stopPolling();
    } else {
      fetchPods(); // Refresh immediately when tab becomes visible
      startPolling();
    }
  }

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.System.View')) {
      goto('/');
      return;
    }
    fetchPods();
    startPolling();
    if (browser) {
      document.addEventListener('visibilitychange', handleVisibilityChange);
    }
  });

  onDestroy(() => {
    stopPolling();
    if (browser) {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    }
  });

  $effect(() => {
    namespace; // Track namespace changes
    fetchPods();
  });
</script>

<div class="space-y-4">
  <!-- Filters -->
  <div class="flex items-center gap-3">
    <NamespaceSelector value={namespace} onchange={(ns) => namespace = ns} />
    <span class="text-sm text-secondary ml-auto">{pods.length} pods</span>
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-8" out:fade={loaderOut}>
      <PlanesLoader size="sm" planeCount={4} message="Loading pods..." />
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
            <th class="table-header">Restarts</th>
            <th class="table-header">Node</th>
            <th class="table-header">Age</th>
          </tr>
        </thead>
        <tbody>
          {#each pods as pod}
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
              <td class="table-cell font-mono text-text-secondary">{pod.ready}</td>
              <td class="table-cell {pod.restarts > 0 ? 'font-bold text-warning' : 'text-text-secondary'}">
                {pod.restarts}
              </td>
              <td class="table-cell text-text-secondary">{pod.nodeName}</td>
              <td class="table-cell">
                <ResourceAge timestamp={pod.createdAt} />
              </td>
            </tr>
          {:else}
            <tr>
              <td colspan="7" class="table-empty">No pods found</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
