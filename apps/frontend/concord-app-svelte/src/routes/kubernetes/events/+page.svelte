<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { ChevronRight, ChevronDown } from 'lucide-svelte';
  import { fade } from 'svelte/transition';
  import { loaderOut, contentIn, errorIn } from '$lib/utils/transitions';
  import { api } from '$lib/api';
  import { getAuth } from '$lib/stores/auth.svelte';
  import StatusIndicator from '$lib/components/system/status-indicator.svelte';
  import ResourceAge from '$lib/components/system/resource-age.svelte';
  import NamespaceSelector from '$lib/components/system/namespace-selector.svelte';
  import PlanesLoader from '$lib/components/ui/planes-loader.svelte';

  interface K8sEvent {
    type: string;
    reason: string;
    message: string;
    object: string;
    namespace: string;
    count: number;
    firstSeen: string | null;
    lastSeen: string;
    source: string;
  }

  let events = $state<K8sEvent[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let namespace = $state('');
  let expandedRows = $state(new Set<number>());
  const auth = getAuth();
  let pollInterval: ReturnType<typeof setInterval>;

  async function fetchEvents() {
    try {
      const url = namespace
        ? `/v2/kubernetes/events?limit=200&namespace=${namespace}`
        : '/v2/kubernetes/events?limit=200';
      const res = await api.get<{ data: K8sEvent[] }>(url);
      if (res?.data) events = res.data;
      error = null;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load events';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.System.View')) {
      goto('/');
      return;
    }
    fetchEvents();
    pollInterval = setInterval(fetchEvents, 10000);
  });

  onDestroy(() => {
    if (pollInterval) clearInterval(pollInterval);
  });

  $effect(() => {
    namespace;
    fetchEvents();
  });

  function toggleRow(idx: number) {
    const newSet = new Set(expandedRows);
    if (newSet.has(idx)) {
      newSet.delete(idx);
    } else {
      newSet.add(idx);
    }
    expandedRows = newSet;
  }
</script>

<div class="space-y-4">
  <!-- Filters -->
  <div class="flex items-center gap-3">
    <NamespaceSelector value={namespace} onchange={(ns) => namespace = ns} />
    <span class="text-sm text-secondary ml-auto">{events.length} events</span>
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-8" out:fade={loaderOut}>
      <PlanesLoader size="sm" planeCount={4} message="Loading events..." />
    </div>
  {:else if error}
    <div class="rounded-lg border border-error/20 bg-error/10 p-4 text-error" in:fade={errorIn}>{error}</div>
  {:else}
    <div class="table-wrapper" in:fade={contentIn}>
      <table class="table">
        <thead>
          <tr class="border-b border-border">
            <th class="table-header w-8 px-2"></th>
            <th class="table-header">Type</th>
            <th class="table-header">Reason</th>
            <th class="table-header">Object</th>
            <th class="table-header">Count</th>
            <th class="table-header">Last Seen</th>
          </tr>
        </thead>
        <tbody>
          {#each events as event, idx}
            <tr
              class="table-row table-row-interactive"
              onclick={() => toggleRow(idx)}
            >
              <td class="table-cell px-2">
                {#if expandedRows.has(idx)}
                  <ChevronDown class="w-4 h-4 text-text-tertiary" />
                {:else}
                  <ChevronRight class="w-4 h-4 text-text-tertiary" />
                {/if}
              </td>
              <td class="table-cell">
                <StatusIndicator status={event.type} />
              </td>
              <td class="table-cell font-medium text-text-primary">{event.reason}</td>
              <td class="table-cell font-mono text-text-secondary">{event.object}</td>
              <td class="table-cell text-text-secondary">{event.count}</td>
              <td class="table-cell">
                <ResourceAge timestamp={event.lastSeen} />
              </td>
            </tr>
            {#if expandedRows.has(idx)}
              <tr class="bg-surface-0">
                <td colspan="6" class="px-6 py-3">
                  <div class="space-y-2 text-sm">
                    <div>
                      <span class="text-text-secondary">Message:</span>
                      <span class="ml-2 text-text-primary">{event.message}</span>
                    </div>
                    <div>
                      <span class="text-text-secondary">Source:</span>
                      <span class="ml-2 text-text-primary font-mono">{event.source}</span>
                    </div>
                    {#if event.firstSeen}
                      <div>
                        <span class="text-text-secondary">First Seen:</span>
                        <span class="ml-2 text-text-primary">
                          <ResourceAge timestamp={event.firstSeen} />
                        </span>
                      </div>
                    {/if}
                  </div>
                </td>
              </tr>
            {/if}
          {:else}
            <tr>
              <td colspan="6" class="table-empty">No events found</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
