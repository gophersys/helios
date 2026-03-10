<script lang="ts">
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import type { DashboardFixture } from '$lib/types/models';

  let { fixture, onclick }: {
    fixture: DashboardFixture;
    onclick: () => void;
  } = $props();

  const HEALTH_DOT: Record<string, string> = {
    HEALTHY: 'bg-success',
    DEGRADED: 'bg-warning',
    ERROR: 'bg-error',
    UNASSIGNED: 'bg-surface-2 border border-border',
    EMPTY: 'bg-surface-2 border border-border',
    UNKNOWN: 'bg-surface-2 border border-border',
  };

  const healthDot = $derived(HEALTH_DOT[fixture.health] || 'bg-surface-2 border border-border');

  // Build slot dots array
  const slotDots = $derived.by(() => {
    const dots: { color: string; title: string }[] = [];
    // Online nodes
    for (let i = 0; i < fixture.nodesOnline; i++) {
      dots.push({ color: 'bg-success', title: 'Online' });
    }
    // Error nodes
    for (let i = 0; i < fixture.nodesError; i++) {
      dots.push({ color: 'bg-error', title: 'Error' });
    }
    // Offline nodes
    for (let i = 0; i < fixture.nodesOffline; i++) {
      dots.push({ color: 'bg-warning', title: 'Offline' });
    }
    // Unassigned slots
    const unassigned = fixture.slotCount - fixture.assignedCount;
    for (let i = 0; i < unassigned; i++) {
      dots.push({ color: 'border border-border bg-transparent', title: 'Empty' });
    }
    return dots;
  });

  const statusLine = $derived.by(() => {
    const parts: string[] = [];
    if (fixture.assignedCount > 0) {
      parts.push(`${fixture.nodesOnline}/${fixture.assignedCount} online`);
    }
    const empty = fixture.slotCount - fixture.assignedCount;
    if (empty > 0) {
      parts.push(`${empty} empty`);
    }
    return parts.join(' · ') || 'No slots';
  });
</script>

<button
  {onclick}
  class="card card-md card-interactive w-full text-left"
>
  <!-- Top row: type badge + health dot -->
  <div class="flex items-center justify-between">
    <StatusBadge status={fixture.type} />
    <div class="flex items-center gap-2">
      {#if fixture.hasActiveDeployment}
        <StatusBadge status={fixture.activeDeploymentStatus || 'PENDING'} />
      {/if}
      <div class="h-2.5 w-2.5 rounded-full {healthDot}" title={fixture.health}></div>
    </div>
  </div>

  <!-- Fixture name + product -->
  <div class="mt-3">
    <h3 class="text-sm font-semibold text-text-primary">{fixture.name}</h3>
    {#if fixture.productName}
      <p class="mt-0.5 text-2xs text-text-tertiary">{fixture.productName}</p>
    {/if}
  </div>

  <!-- Slot dots -->
  {#if fixture.slotCount > 0}
    <div class="mt-3 flex flex-wrap gap-1.5">
      {#each slotDots as dot}
        <div class="h-3 w-3 rounded-full {dot.color}" title={dot.title}></div>
      {/each}
    </div>
    <p class="mt-1.5 text-2xs text-text-tertiary">{statusLine}</p>
  {:else}
    <p class="mt-3 text-2xs text-text-tertiary">No slots configured</p>
  {/if}

  <!-- Deployment status -->
  {#if fixture.hasActiveDeployment}
    <div class="mt-2 text-2xs text-text-secondary">
      MTIB: {fixture.activeDeploymentStatus}
    </div>
  {/if}
</button>
