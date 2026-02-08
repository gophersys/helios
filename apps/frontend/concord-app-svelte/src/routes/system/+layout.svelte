<script lang="ts">
  import type { Snippet } from 'svelte';
  import { page } from '$app/stores';
  import {
    Activity,
    HardDrive,
    Box,
    Layers,
    Network,
    Clock,
    FileText,
    Shield,
    Bell
  } from 'lucide-svelte';

  interface Props {
    children: Snippet;
  }

  let { children }: Props = $props();

  const tabs = [
    { href: '/system', label: 'Overview', icon: Activity, exact: true },
    { href: '/system/nodes', label: 'Nodes', icon: HardDrive },
    { href: '/system/pods', label: 'Pods', icon: Box },
    { href: '/system/deployments', label: 'Deployments', icon: Layers },
    { href: '/system/services', label: 'Services', icon: Network },
    { href: '/system/jobs', label: 'Jobs', icon: Clock },
    { href: '/system/config', label: 'Config', icon: FileText },
    { href: '/system/rbac', label: 'RBAC', icon: Shield },
    { href: '/system/events', label: 'Events', icon: Bell },
  ];

  const currentPath = $derived($page.url.pathname);

  function isActive(href: string, exact: boolean = false): boolean {
    if (exact) {
      return currentPath === href;
    }
    return currentPath.startsWith(href);
  }
</script>

<div class="space-y-4">
  <div class="flex items-center justify-between">
    <h1 class="text-2xl font-bold text-primary">System</h1>
  </div>

  <!-- Tab Navigation -->
  <div class="border-b border-border">
    <nav class="flex gap-1 overflow-x-auto pb-px">
      {#each tabs as tab}
        <a
          href={tab.href}
          class="flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-t whitespace-nowrap transition-colors
            {isActive(tab.href, tab.exact)
              ? 'text-accent border-b-2 border-accent bg-accent/5'
              : 'text-secondary hover:text-primary hover:bg-surface-2'}"
        >
          <tab.icon class="w-4 h-4" />
          {tab.label}
        </a>
      {/each}
    </nav>
  </div>

  <!-- Page Content -->
  <div>
    {@render children()}
  </div>
</div>
