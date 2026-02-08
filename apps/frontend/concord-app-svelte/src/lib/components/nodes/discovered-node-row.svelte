<script lang="ts">
  import { Monitor, Plus, ExternalLink } from 'lucide-svelte';
  import type { DiscoveredNode } from '$lib/types/models';

  let { node, onRegister }: {
    node: DiscoveredNode;
    onRegister: (hostname: string) => void;
  } = $props();
</script>

<div class="flex items-center justify-between rounded-lg border border-border bg-surface-1 px-4 py-3">
  <div class="flex items-center gap-3">
    <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-muted">
      <Monitor size={16} class="text-accent" />
    </div>
    <div>
      <a
        href="/system/nodes/{node.hostname}"
        class="text-sm font-medium text-accent hover:underline"
        title="View in Kubernetes"
      >
        {node.hostname}
        <ExternalLink size={12} class="ml-1 inline-block opacity-60" />
      </a>
      <div class="flex gap-3 text-2xs text-text-tertiary">
        <span>IP: {node.ip}</span>
        <span>Arch: {node.arch}</span>
        {#each Object.entries(node.labels).slice(0, 3) as [key, value]}
          <span>{key}: {value}</span>
        {/each}
      </div>
    </div>
  </div>
  <button
    onclick={() => onRegister(node.hostname)}
    class="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover"
  >
    <Plus size={14} />
    Register
  </button>
</div>
