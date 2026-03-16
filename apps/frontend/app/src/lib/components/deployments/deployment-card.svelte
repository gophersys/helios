<script lang="ts">
  import { Play, Square, RotateCcw, Trash2, ChevronDown, ChevronUp } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import type { ConcordDeployment } from '$lib/types/models';

  let { deployment, canManage, onDeploy, onStop, onRestart, onDelete }: {
    deployment: ConcordDeployment;
    canManage: boolean;
    onDeploy: (id: string) => void;
    onStop: (id: string) => void;
    onRestart: (id: string) => void;
    onDelete: (id: string) => void;
  } = $props();

  let expanded = $state(false);

  const k8sDeployments = $derived(deployment.k8sStatus?.deployments || []);
  const allPods = $derived(k8sDeployments.flatMap(d => d.pods));
</script>

<div class="card card-sm">
  <div class="flex items-center justify-between">
    <div class="flex items-center gap-3">
      <StatusBadge status={deployment.status} />
      <div>
        <h3 class="text-sm font-semibold text-text-primary">{deployment.name}</h3>
        <div class="flex gap-3 text-2xs text-text-tertiary">
          {#if deployment.fixtureName}
            <span>Fixture: <span class="text-text-secondary">{deployment.fixtureName}</span></span>
          {/if}
          {#if deployment.productName}
            <span>Product: <span class="text-text-secondary">{deployment.productName}</span></span>
          {/if}
          {#if deployment.version}
            <span>v{deployment.version}</span>
          {/if}
        </div>
      </div>
    </div>

    <div class="flex items-center gap-2">
      {#if canManage}
        {#if deployment.status === 'PENDING' || deployment.status === 'STOPPED' || deployment.status === 'FAILED'}
          <button
            onclick={() => onDeploy(deployment.id)}
            class="flex items-center gap-1.5 rounded-lg bg-success px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
            title={deployment.status === 'FAILED' ? 'Retry' : 'Deploy'}
          >
            <Play size={14} />
            {deployment.status === 'FAILED' ? 'Retry' : 'Deploy'}
          </button>
        {/if}

        {#if deployment.status === 'RUNNING'}
          <button
            onclick={() => onRestart(deployment.id)}
            class="flex items-center gap-1.5 rounded-lg bg-warning px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
            title="Restart"
          >
            <RotateCcw size={14} />
            Restart
          </button>
          <button
            onclick={() => onStop(deployment.id)}
            class="flex items-center gap-1.5 rounded-lg bg-error px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
            title="Stop"
          >
            <Square size={14} />
            Stop
          </button>
        {/if}

        {#if deployment.status !== 'RUNNING'}
          <button
            onclick={() => onDelete(deployment.id)}
            class="rounded-lg p-1.5 text-text-tertiary hover:text-error"
            title="Delete"
            aria-label="Delete"
          >
            <Trash2 size={16} />
          </button>
        {/if}
      {/if}

      {#if deployment.status === 'RUNNING' && allPods.length > 0}
        <button
          onclick={() => expanded = !expanded}
          class="rounded-lg p-1.5 text-text-tertiary hover:text-text-primary"
          title={expanded ? 'Collapse' : 'Expand'}
        >
          {#if expanded}
            <ChevronUp size={16} />
          {:else}
            <ChevronDown size={16} />
          {/if}
        </button>
      {/if}
    </div>
  </div>

  <!-- Expanded pod status -->
  {#if expanded && allPods.length > 0}
    <div class="mt-3 border-t border-border pt-3">
      <div class="table-wrapper">
        <table class="table">
          <thead>
            <tr>
              <th class="table-header">Pod</th>
              <th class="table-header">Node</th>
              <th class="table-header">Status</th>
              <th class="table-header">Ready</th>
              <th class="table-header">Restarts</th>
            </tr>
          </thead>
          <tbody>
            {#each allPods as pod}
              <tr class="table-row">
                <td class="table-cell font-mono text-2xs text-text-primary">{pod.name}</td>
                <td class="table-cell text-2xs text-text-secondary">{pod.nodeName}</td>
                <td class="table-cell">
                  <StatusBadge status={pod.status} />
                </td>
                <td class="table-cell">
                  <span class={pod.ready ? 'text-success' : 'text-error'}>
                    {pod.ready ? 'Yes' : 'No'}
                  </span>
                </td>
                <td class="table-cell text-text-secondary">{pod.restarts}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}
</div>
