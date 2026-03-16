<script lang="ts">
  import { goto } from '$app/navigation';
  import { Cpu, Pencil, Trash2, HeartPulse, Wrench, Activity, Loader2 } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import type { ConcordNode } from '$lib/types/models';

  let { node, canManage, onEdit, onDelete, onHealthCheck }: {
    node: ConcordNode;
    canManage: boolean;
    onEdit: (node: ConcordNode) => void;
    onDelete: (id: string) => void;
    onHealthCheck: (id: string) => void;
  } = $props();

  const isAssigned = $derived(!!node.fixtureSlot);

  const deployState = $derived.by(() => {
    const ds = node.deploymentStatus;
    if (!ds) return 'none';
    if ((ds.readyReplicas ?? 0) > 0) return 'running';
    if (ds.pods?.some(p => p.status === 'Running')) return 'running';
    return 'deploying';
  });

  const isServerOnline = $derived(deployState === 'running');

  const statusColor = $derived(
    isServerOnline ? 'bg-success' :
    deployState === 'deploying' ? 'bg-warning' :
    node.status === 'ERROR' ? 'bg-error' :
    'bg-text-tertiary'
  );

  function handleCardClick() {
    if (isServerOnline || deployState === 'deploying') {
      goto(`/mtib/${node.id}`);
    }
  }
</script>

<div
  onclick={handleCardClick}
  class="card group relative flex flex-col overflow-hidden text-left w-full transition-all duration-200
    {isServerOnline ? 'hover:ring-2 hover:ring-accent/50 cursor-pointer' : deployState === 'deploying' ? 'hover:ring-2 hover:ring-warning/50 cursor-pointer' : ''}"
>
  <!-- Status stripe -->
  <div class="h-1 w-full {statusColor} {deployState === 'deploying' ? 'animate-pulse' : ''}"></div>

  <div class="flex flex-1 flex-col p-4">
    <!-- Row 1: Status dot + name + badges -->
    <div class="flex items-center gap-2.5 mb-2">
      <span class="relative flex h-2.5 w-2.5 shrink-0">
        <span class="h-2.5 w-2.5 rounded-full {statusColor}"></span>
        {#if deployState === 'deploying'}
          <span class="absolute inset-0 rounded-full {statusColor} animate-ping opacity-75"></span>
        {/if}
      </span>
      <h3 class="truncate text-sm font-semibold text-text-primary flex-1">{node.name}</h3>
      <div class="flex items-center gap-1.5 shrink-0">
        <StatusBadge status={node.type} />
        {#if isAssigned}
          <span class="inline-flex items-center gap-1 rounded-full bg-success-muted px-1.5 py-0.5 text-2xs font-medium text-success">
            <Wrench size={10} />
            {node.fixtureSlot?.fixtureName || 'Fixture'}
          </span>
        {/if}
      </div>
    </div>

    <!-- Row 2: Meta info -->
    <div class="grid grid-cols-2 gap-x-4 gap-y-0.5 text-2xs text-text-tertiary mb-3">
      <p class="truncate">Host: <span class="text-text-secondary">{node.hostname}</span></p>
      {#if node.ipAddress}
        <p>IP: <span class="text-text-secondary">{node.ipAddress}</span></p>
      {/if}
      {#if node.hardwareRevision}
        <p>HW: <span class="text-text-secondary">REV {node.hardwareRevision}</span></p>
      {/if}
    </div>

    <!-- Row 3: Deploy status -->
    <div class="flex items-center justify-between">
      {#if deployState === 'running'}
        <div class="flex items-center gap-1.5 text-2xs text-success">
          <Activity size={12} />
          <span class="font-medium">Server Online</span>
        </div>
      {:else if deployState === 'deploying'}
        <div class="flex items-center gap-1.5 text-2xs text-warning">
          <Loader2 size={12} class="animate-spin" />
          <span class="font-medium">Deploying...</span>
        </div>
      {:else}
        <div class="flex items-center gap-1.5 text-2xs text-text-tertiary">
          <Cpu size={12} />
          <span>Not Deployed</span>
        </div>
      {/if}

      {#if isServerOnline}
        <span class="text-2xs text-accent font-medium">View details &rarr;</span>
      {/if}
    </div>
  </div>

  <!-- Hover actions (stop propagation so they don't navigate) -->
  {#if canManage}
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div
      role="group"
      class="absolute right-2 top-3 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
    >
      <div
        onclick={() => onHealthCheck(node.id)}
        class="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-success"
        title="Health check"
        aria-label="Health check"
      >
        <HeartPulse size={14} />
      </button>
      <div
        onclick={() => onEdit(node)}
        class="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-text-primary"
        title="Edit"
        aria-label="Edit"
      >
        <Pencil size={14} />
      </button>
      <div
        onclick={() => onDelete(node.id)}
        class="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-error"
        title="Delete"
        aria-label="Delete"
      >
        <Trash2 size={14} />
      </button>
    </div>
  {/if}
</button>
