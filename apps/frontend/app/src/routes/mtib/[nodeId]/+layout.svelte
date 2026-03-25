<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { Home, Server, Cpu, Activity } from 'lucide-svelte';
  import { apiFetch } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { ConcordNode } from '$lib/types/models';
  import { onMount } from 'svelte';
  import { getAuth } from '$lib/stores/auth.svelte';

  const auth = getAuth();
  const nodeId = $derived($page.params.nodeId);

  let nodeInfo = $state<ConcordNode | null>(null);
  let loading = $state(true);

  // Fetch basic node info for header
  async function fetchNodeInfo() {
    try {
      const res = await apiFetch<ApiResponse<ConcordNode>>(`/v2/devices/mtibs/${nodeId}`);
      nodeInfo = res.data;
    } catch {
      // Silently fail - child pages will handle errors
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    // Permission guard
    if (!auth.hasPermission('devices:view')) {
      goto('/');
      return;
    }
    fetchNodeInfo();
  });

  interface Tab {
    path: string;
    label: string;
    exact?: boolean;
  }

  const tabs: Tab[] = [
    { path: `/mtib/${nodeId}`, label: 'Overview', exact: true },
    { path: `/mtib/${nodeId}/analyzer`, label: 'Analyzer' },
  ];

  const isActive = $derived((tab: Tab) => {
    const currentPath = $page.url.pathname;
    if (tab.exact) {
      return currentPath === tab.path;
    }
    return currentPath.startsWith(tab.path);
  });

  const isOnline = $derived((nodeInfo?.deploymentStatus?.readyReplicas ?? 0) > 0);
  const lastSeen = $derived(nodeInfo?.lastSeenAt ? new Date(nodeInfo.lastSeenAt).toLocaleString() : null);
</script>

<svelte:head>
  <title>{nodeInfo?.name || 'MTIB'} — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <!-- Breadcrumb Navigation -->
  <nav class="mb-4 flex items-center gap-2 text-xs text-text-tertiary" aria-label="Breadcrumb">
    <a href="/" class="hover:text-text-primary transition-colors flex items-center gap-1">
      <Home size={12} />
      Home
    </a>
    <span>/</span>
    <a href="/kubernetes" class="hover:text-text-primary transition-colors flex items-center gap-1">
      <Server size={12} />
      Kubernetes
    </a>
    <span>/</span>
    <a href="/kubernetes/nodes" class="hover:text-text-primary transition-colors">Nodes</a>
    <span>/</span>
    {#if nodeInfo}
      <span class="text-text-secondary">{nodeInfo.name}</span>
      <span>/</span>
      <span class="text-text-primary font-medium">MTIB</span>
    {:else}
      <span class="text-text-secondary">MTIB</span>
    {/if}
  </nav>

  <!-- Node Status Header -->
  {#if !loading && nodeInfo}
    <div class="mb-6 rounded-lg border border-border bg-surface-1 p-4">
      <div class="flex items-center justify-between gap-4">
        <div class="flex items-center gap-3 min-w-0">
          <div class="p-2 rounded-lg bg-accent-muted">
            <Cpu size={20} class="text-accent" />
          </div>
          <div class="min-w-0">
            <h1 class="text-xl font-semibold text-text-primary truncate">{nodeInfo.name}</h1>
            <div class="flex items-center gap-3 mt-1 text-xs">
              {#if nodeInfo.hostname}
                <span class="font-mono text-text-tertiary">{nodeInfo.hostname}</span>
              {/if}
              {#if nodeInfo.ipAddress}
                <span class="font-mono text-text-tertiary">{nodeInfo.ipAddress}</span>
              {/if}
              {#if nodeInfo.hardwareRevision}
                <span class="rounded bg-surface-2 px-2 py-0.5 text-xs font-medium text-text-secondary">
                  {nodeInfo.hardwareRevision.replace(/_/g, '.')}
                </span>
              {/if}
            </div>
          </div>
        </div>

        <div class="flex flex-col items-end gap-2 shrink-0">
          <div class="flex items-center gap-2">
            <span class="relative flex h-2.5 w-2.5">
              <span class="h-2.5 w-2.5 rounded-full {isOnline ? 'bg-success' : 'bg-text-tertiary'}"></span>
              {#if isOnline}
                <span class="absolute inset-0 rounded-full bg-success animate-ping opacity-40"></span>
              {/if}
            </span>
            <span class="text-sm font-medium {isOnline ? 'text-success' : 'text-text-tertiary'}">
              {isOnline ? 'Online' : 'Offline'}
            </span>
          </div>
          {#if lastSeen}
            <span class="text-xs text-text-tertiary">
              Last seen: {lastSeen}
            </span>
          {/if}
        </div>
      </div>
    </div>
  {/if}

  <!-- Tab Navigation -->
  <div class="mb-6 border-b border-border">
    <nav class="flex gap-6" aria-label="MTIB sections">
      {#each tabs as tab}
        <a
          href={tab.path}
          class="relative pb-3 text-sm font-medium transition-colors {isActive(tab) ? 'text-accent' : 'text-text-tertiary hover:text-text-primary'}"
          aria-current={isActive(tab) ? 'page' : undefined}
        >
          {tab.label}
          {#if isActive(tab)}
            <span class="absolute bottom-0 left-0 right-0 h-0.5 bg-accent"></span>
          {/if}
        </a>
      {/each}
    </nav>
  </div>

  <!-- Page Content -->
  <slot />
</div>
