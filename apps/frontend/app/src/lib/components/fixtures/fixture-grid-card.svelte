<script lang="ts">
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
      const status = slot.node?.status;
      if (status === 'ONLINE') return { color: 'bg-success', label: 'Online' };
      if (status === 'ERROR') return { color: 'bg-error', label: 'Error' };
      return { color: 'bg-warning', label: 'Offline' };
    });
  });

  const healthSummary = $derived.by(() => {
    if (slots.length === 0) return `${slotCount} slot${slotCount !== 1 ? 's' : ''}`;
    const online = slots.filter(s => s.node?.status === 'ONLINE').length;
    const empty = slots.filter(s => !s.nodeId).length;
    const parts: string[] = [];
    if (online > 0) parts.push(`${online} online`);
    if (empty > 0) parts.push(`${empty} empty`);
    const other = slots.length - online - empty;
    if (other > 0) parts.push(`${other} offline`);
    return parts.join(' · ') || `${slots.length} slots`;
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
    <span class="badge {fixture.type === 'MANUFACTURING' ? 'badge-warning' : 'badge-accent'} shrink-0">
      {fixture.type}
    </span>
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
