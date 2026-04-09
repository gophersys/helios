<script lang="ts">
  import { onMount } from 'svelte';
  import { Loader2, Wrench, Zap, CircuitBoard, FlaskConical, Factory } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import { apiFetch } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { Product, FixtureDesign } from '$lib/types/models';

  interface Props {
    product: Product;
    canManage: boolean;
  }

  let { product }: Props = $props();

  let designs = $state<FixtureDesign[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let selectedRevId = $state<string | null>(null);

  const revisions = $derived(
    (product.boards || []).flatMap((b) => b.revisions || []).filter((r) => r.status === 'ACTIVE')
  );

  const selectedRevision = $derived(
    revisions.find((r) => r.id === selectedRevId) ?? revisions[0] ?? null
  );

  function designsForRevision(revId: string, type: string): FixtureDesign[] {
    return designs.filter((d) => d.boardRevisionId === revId && ((d as any).type || 'VALIDATION') === type);
  }

  async function loadDesigns() {
    loading = true;
    try {
      const res = await apiFetch<ApiResponse<{ data: FixtureDesign[] }>>('/v2/fixtures/designs?limit=100');
      const data = res.data;
      const all: FixtureDesign[] = Array.isArray(data) ? data : (data as any)?.data ?? [];
      const revIds = new Set(revisions.map((r) => r.id));
      designs = all.filter((d) => revIds.has(d.boardRevisionId));
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load fixture designs';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (revisions.length > 0 && !selectedRevId) selectedRevId = revisions[0].id;
    loadDesigns();
  });
</script>

{#if loading}
  <div class="flex items-center gap-2 justify-center py-8 text-sm text-text-tertiary">
    <Loader2 size={16} class="animate-spin" /> Loading...
  </div>
{:else if revisions.length === 0}
  <div class="text-center py-8">
    <p class="text-sm text-text-secondary">No active board revisions.</p>
    <p class="text-2xs text-text-tertiary mt-1">Add a board revision in the Hardware tab first.</p>
  </div>
{:else}
  <!-- Revision tabs (same pattern as Assets tab) -->
  <div class="flex gap-1 border-b border-border mb-4">
    {#each revisions as rev}
      <button
        onclick={() => selectedRevId = rev.id}
        class="px-3 py-2 text-sm font-medium transition-colors border-b-2 -mb-px
          {selectedRevId === rev.id ? 'border-accent text-accent' : 'border-transparent text-text-tertiary hover:text-text-secondary'}"
      >
        {rev.version}
        <span class="text-2xs text-text-tertiary ml-1">{rev.ckBoardsName}</span>
      </button>
    {/each}
  </div>

  {#if selectedRevision}
    {@const valDesigns = designsForRevision(selectedRevision.id, 'VALIDATION')}
    {@const mfgDesigns = designsForRevision(selectedRevision.id, 'MANUFACTURING')}

    {#if valDesigns.length === 0 && mfgDesigns.length === 0}
      <div class="text-center py-8">
        <p class="text-sm text-text-secondary">No fixture designs for this revision</p>
        <p class="text-2xs text-text-tertiary mt-1">Fixture designs are auto-extracted when a test package is uploaded via corectl.</p>
      </div>
    {:else}
      <div class="space-y-6">
        <!-- Validation Fixtures -->
        {#if valDesigns.length > 0}
          <div>
            <div class="flex items-center gap-2 mb-3">
              <FlaskConical size={14} class="text-accent" />
              <span class="text-sm font-semibold text-text-primary">Validation Fixtures</span>
              <span class="text-2xs text-text-tertiary">{valDesigns.length}</span>
            </div>
            <div class="grid gap-3 sm:grid-cols-2">
              {#each valDesigns as design}
                <div class="rounded-lg border border-border bg-surface-1 p-4">
                  <div class="flex items-center gap-2 mb-2">
                    <Wrench size={14} class="text-text-tertiary" />
                    <span class="text-sm font-semibold text-text-primary">{design.name}</span>
                    <span class="text-2xs text-text-tertiary">rev {design.revision}</span>
                  </div>
                  {#if design.capabilities?.length}
                    <div class="flex flex-wrap gap-1 mb-2">
                      {#each design.capabilities as cap}
                        <span class="rounded-full bg-accent-muted px-2 py-0.5 text-2xs font-medium text-accent">{cap}</span>
                      {/each}
                    </div>
                  {/if}
                  {#if (design as any).slotDefinitions?.length}
                    <div class="text-2xs text-text-tertiary">{(design as any).slotDefinitions.length} slot{(design as any).slotDefinitions.length === 1 ? '' : 's'}</div>
                  {/if}
                  {@const power = (design.profileTemplate as any)?.power}
                  {#if power}
                    <div class="flex items-center gap-3 mt-2 text-2xs text-text-tertiary">
                      <Zap size={10} class="text-warning" />
                      {power.dut_voltage}V · {power.battery_installed ? 'Battery' : 'No battery'}
                    </div>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}

        <!-- Manufacturing Fixtures -->
        {#if mfgDesigns.length > 0}
          <div>
            <div class="flex items-center gap-2 mb-3">
              <Factory size={14} class="text-accent" />
              <span class="text-sm font-semibold text-text-primary">Manufacturing Fixtures</span>
              <span class="text-2xs text-text-tertiary">{mfgDesigns.length}</span>
            </div>
            <div class="grid gap-3 sm:grid-cols-2">
              {#each mfgDesigns as design}
                <div class="rounded-lg border border-border bg-surface-1 p-4">
                  <div class="flex items-center gap-2 mb-2">
                    <Wrench size={14} class="text-text-tertiary" />
                    <span class="text-sm font-semibold text-text-primary">{design.name}</span>
                    <span class="text-2xs text-text-tertiary">rev {design.revision}</span>
                  </div>
                  {#if design.capabilities?.length}
                    <div class="flex flex-wrap gap-1 mb-2">
                      {#each design.capabilities as cap}
                        <span class="rounded-full bg-accent-muted px-2 py-0.5 text-2xs font-medium text-accent">{cap}</span>
                      {/each}
                    </div>
                  {/if}
                  {#if (design as any).slotDefinitions?.length}
                    <div class="text-2xs text-text-tertiary">{(design as any).slotDefinitions.length} slot{(design as any).slotDefinitions.length === 1 ? '' : 's'}</div>
                  {/if}
                  {@const power = (design.profileTemplate as any)?.power}
                  {#if power}
                    <div class="flex items-center gap-3 mt-2 text-2xs text-text-tertiary">
                      <Zap size={10} class="text-warning" />
                      {power.dut_voltage}V · {power.battery_installed ? 'Battery' : 'No battery'}
                    </div>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {/if}
  {/if}
{/if}
