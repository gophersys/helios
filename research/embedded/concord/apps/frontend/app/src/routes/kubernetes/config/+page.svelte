<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import { getAuth } from '$lib/stores/auth.svelte';
  import ResourceAge from '$lib/components/system/resource-age.svelte';
  import NamespaceSelector from '$lib/components/system/namespace-selector.svelte';
  import PlanesLoader from '$lib/components/ui/planes-loader.svelte';

  interface ConfigMapSummary {
    name: string;
    namespace: string;
    dataKeys: string[];
    dataCount: number;
    createdAt: string;
  }

  interface SecretSummary {
    name: string;
    namespace: string;
    type: string;
    dataKeys: string[];
    dataCount: number;
    createdAt: string;
  }

  let tab = $state<'configmaps' | 'secrets'>('configmaps');
  let namespace = $state('');
  let configMaps = $state<ConfigMapSummary[]>([]);
  let secrets = $state<SecretSummary[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  const auth = getAuth();
  let pollInterval: ReturnType<typeof setInterval>;

  async function fetchConfigMaps() {
    try {
      const url = namespace ? `/v2/kubernetes/configmaps?namespace=${namespace}` : '/v2/kubernetes/configmaps';
      const res = await api.get<{ data: ConfigMapSummary[] }>(url);
      if (res?.data) configMaps = res.data;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load configmaps';
    }
  }

  async function fetchSecrets() {
    try {
      const url = namespace ? `/v2/kubernetes/secrets?namespace=${namespace}` : '/v2/kubernetes/secrets';
      const res = await api.get<{ data: SecretSummary[] }>(url);
      if (res?.data) secrets = res.data;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load secrets';
    }
  }

  async function fetchData() {
    loading = true;
    error = null;
    if (tab === 'configmaps') {
      await fetchConfigMaps();
    } else {
      await fetchSecrets();
    }
    loading = false;
  }

  onMount(() => {
    if (!auth.hasPermission('system:view')) {
      goto('/');
      return;
    }
    fetchData();
    pollInterval = setInterval(fetchData, 15000);
  });

  onDestroy(() => {
    if (pollInterval) clearInterval(pollInterval);
  });

  $effect(() => {
    tab;
    namespace;
    fetchData();
  });

  const items = $derived(tab === 'configmaps' ? configMaps : secrets);
</script>

<div class="space-y-4">
  <!-- Tab Selector -->
  <div class="flex items-center gap-3">
    <div class="flex rounded-lg bg-surface-2 p-1">
      <button
        onclick={() => tab = 'configmaps'}
        class="px-3 py-1 text-sm font-medium rounded {tab === 'configmaps' ? 'bg-surface-1 text-primary' : 'text-secondary hover:text-primary'}"
      >
        ConfigMaps
      </button>
      <button
        onclick={() => tab = 'secrets'}
        class="px-3 py-1 text-sm font-medium rounded {tab === 'secrets' ? 'bg-surface-1 text-primary' : 'text-secondary hover:text-primary'}"
      >
        Secrets
      </button>
    </div>
    <NamespaceSelector value={namespace} onchange={(ns) => namespace = ns} />
    <span class="text-sm text-secondary ml-auto">{items.length} {tab}</span>
  </div>

  {#if loading}
    <PlanesLoader message="Loading {tab}..." />
  {:else if error}
    <div class="rounded-lg border border-error/20 bg-error/10 p-4 text-error">{error}</div>
  {:else}
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr class="border-b border-border">
            <th class="table-header">Name</th>
            <th class="table-header">Namespace</th>
            {#if tab === 'secrets'}
              <th class="table-header">Type</th>
            {/if}
            <th class="table-header">Keys</th>
            <th class="table-header">Age</th>
          </tr>
        </thead>
        <tbody>
          {#if tab === 'configmaps'}
            {#each configMaps as cm}
              <tr class="table-row">
                <td class="table-cell font-medium text-text-primary">{cm.name}</td>
                <td class="table-cell text-text-secondary">{cm.namespace}</td>
                <td class="table-cell text-text-secondary" title={cm.dataKeys.join(', ')}>
                  {cm.dataCount} {cm.dataCount === 1 ? 'key' : 'keys'}
                </td>
                <td class="table-cell">
                  <ResourceAge timestamp={cm.createdAt} />
                </td>
              </tr>
            {:else}
              <tr>
                <td colspan="4" class="table-empty">No configmaps found</td>
              </tr>
            {/each}
          {:else}
            {#each secrets as secret}
              <tr class="table-row">
                <td class="table-cell font-medium text-text-primary">{secret.name}</td>
                <td class="table-cell text-text-secondary">{secret.namespace}</td>
                <td class="table-cell text-text-secondary">{secret.type}</td>
                <td class="table-cell text-text-secondary" title={secret.dataKeys.join(', ')}>
                  {secret.dataCount} {secret.dataCount === 1 ? 'key' : 'keys'}
                </td>
                <td class="table-cell">
                  <ResourceAge timestamp={secret.createdAt} />
                </td>
              </tr>
            {:else}
              <tr>
                <td colspan="5" class="table-empty">No secrets found</td>
              </tr>
            {/each}
          {/if}
        </tbody>
      </table>
    </div>
  {/if}
</div>
