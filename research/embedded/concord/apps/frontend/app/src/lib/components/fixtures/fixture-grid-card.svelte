<script lang="ts">
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import type { Fixture } from '$lib/types/models';

  let { fixture, onclick }: { fixture: Fixture; onclick: () => void } = $props();

  const slots = $derived(fixture.slots || []);
  const slotCount = $derived(fixture.slotCount ?? slots.length);
  const assignedCount = $derived(
    fixture.assignedCount ?? slots.filter(s => s.nodeId).length
  );

  const slotDots = $derived.by(() => {
    if (slots.length === 0) {
      const dots: Array<{ color: string; label: string }> = [];
      for (let i = 0; i < (slotCount || 0); i++) {
        dots.push({ color: 'border border-border-subtle', label: 'Unknown' });
      }
      return dots;
    }
    return slots.map(slot => {
      if (!slot.nodeId) return { color: 'border border-border-subtle', label: 'Empty' };
      // Same vocabulary as the panel grid + slot modal — single source
      // of truth across the UI.
      const m = slot.mtibStatus?.state;
      if (m === 'READY') return { color: 'bg-success', label: 'Ready' };
      if (m === 'DEPLOYING') return { color: 'bg-warning', label: 'Deploying' };
      if (m === 'PROBE_FAILED' || m === 'NOT_DEPLOYED')
        return { color: 'bg-error', label: 'Not ready' };
      if (m === 'DISABLED') return { color: 'border border-border', label: 'Disabled' };
      return { color: 'bg-warning', label: 'Unknown' };
    });
  });

  const healthSummary = $derived.by(() => {
    const details = fixture.healthDetails;
    const health = fixture.health;
    // Prefer the canonical backend-computed counts when available.
    if (details && health) {
      if (health === 'UNASSIGNED') {
        return slotCount > 0
          ? `${slotCount} slot${slotCount !== 1 ? 's' : ''} · unassigned`
          : 'No slots';
      }
      const parts: string[] = [
        `${details.nodesReady}/${details.nodesTotal} nodes ready`,
      ];
      if (details.mtibsTotal > 0) {
        parts.push(`${details.mtibsReady}/${details.mtibsTotal} MTIBs ready`);
      }
      return parts.join(' · ');
    }
    // Fallback for older payloads without health info.
    if (slots.length === 0) return `${slotCount} slot${slotCount !== 1 ? 's' : ''}`;
    return `${assignedCount}/${slots.length} assigned`;
  });
</script>

<button
  onclick={onclick}
  class="card card-md card-interactive text-left w-full"
>
  <div class="flex items-start justify-between gap-2">
    <div class="min-w-0">
      <div class="flex items-center gap-2">
        <h3 class="text-sm font-semibold text-text-primary truncate">{fixture.name}</h3>
      </div>
      {#if fixture.productName}
        <p class="text-2xs text-text-tertiary mt-0.5">{fixture.productName}</p>
      {/if}
    </div>
    <div class="shrink-0">
      <StatusBadge status={fixture.type} />
    </div>
  </div>

  {#if slotDots.length > 0}
    <div class="mt-3 flex flex-wrap gap-1.5">
      {#each slotDots as dot}
        <div
          class="h-4 w-4 rounded-full {dot.color}"
          title={dot.label}
        ></div>
      {/each}
    </div>
  {/if}

  <div class="mt-2 flex items-center justify-between">
    <span class="text-2xs text-text-tertiary">{healthSummary}</span>
    {#if fixture.design}
      <span class="text-2xs text-text-tertiary font-mono">{fixture.design.name}</span>
    {/if}
  </div>
</button>
