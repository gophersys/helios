<script lang="ts">
  import { onMount } from 'svelte';
  import { Loader2, Wrench, Cpu, Zap, CircuitBoard } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import { apiFetch } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { Product, BoardRevision, FixtureDesign } from '$lib/types/models';

  interface Props {
    product: Product;
    canManage: boolean;
  }

  let { product }: Props = $props();

  let designs = $state<FixtureDesign[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  const revisions = $derived(
    (product.boards || []).flatMap((b) => b.revisions || []).filter((r) => r.status === 'ACTIVE')
  );

  function designsForRevision(revId: string): FixtureDesign[] {
    return designs.filter((d) => d.boardRevisionId === revId);
  }

  async function loadDesigns() {
    loading = true;
    try {
      const res = await apiFetch<ApiResponse<{ data: FixtureDesign[] }>>(
        `/v2/fixtures/designs?limit=100`
      );
      const data = res.data;
      const all: FixtureDesign[] = Array.isArray(data) ? data : (data as any)?.data ?? [];
      // Filter to designs for this product's board revisions
      const revIds = new Set(revisions.map((r) => r.id));
      designs = all.filter((d) => revIds.has(d.boardRevisionId));
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load fixture designs';
    } finally {
      loading = false;
    }
  }

  onMount(() => { loadDesigns(); });
</script>

{#if loading}
  <div class="flex items-center gap-2 justify-center py-8 text-sm text-text-tertiary">
    <Loader2 size={16} class="animate-spin" /> Loading...
  </div>
{:else if error}
  <div class="rounded-lg border border-error/20 bg-error-muted px-4 py-2.5 text-sm text-error">{error}</div>
{:else if designs.length === 0}
  <div class="text-center py-8">
    <p class="text-sm text-text-secondary">No fixture designs found</p>
    <p class="text-2xs text-text-tertiary mt-1">Fixture designs are auto-extracted when a test package is uploaded via corectl.</p>
  </div>
{:else}
  <div class="space-y-6">
    {#each revisions as rev}
      {@const revDesigns = designsForRevision(rev.id)}
      {#if revDesigns.length > 0}
        <div>
          <div class="flex items-center gap-2 mb-3">
            <CircuitBoard size={14} class="text-text-tertiary" />
            <span class="text-sm font-semibold text-text-primary">{rev.version}</span>
            <span class="font-mono text-2xs text-text-tertiary">{rev.ckBoardsName}</span>
          </div>

          <div class="space-y-3">
            {#each revDesigns as design}
              <div class="rounded-lg border border-border overflow-hidden">
                <div class="flex items-center gap-3 px-4 py-3 bg-surface-0/50">
                  <Wrench size={16} class="text-text-tertiary" />
                  <span class="text-sm font-semibold text-text-primary">{design.name}</span>
                  <span class="text-2xs text-text-tertiary">rev {design.revision}</span>
                  <StatusBadge status={(design as any).type || 'VALIDATION'} />
                </div>

                <div class="px-4 py-3 border-t border-border-subtle space-y-3">
                  <!-- Capabilities -->
                  {#if design.capabilities?.length}
                    <div>
                      <span class="text-2xs font-medium text-text-tertiary uppercase tracking-wider">Capabilities</span>
                      <div class="flex flex-wrap gap-1 mt-1">
                        {#each design.capabilities as cap}
                          <span class="rounded-full bg-accent-muted px-2 py-0.5 text-2xs font-medium text-accent">{cap}</span>
                        {/each}
                      </div>
                    </div>
                  {/if}

                  <!-- Slot definitions -->
                  {#if (design as any).slotDefinitions?.length}
                    <div>
                      <span class="text-2xs font-medium text-text-tertiary uppercase tracking-wider">
                        {(design as any).slotDefinitions.length} slot{(design as any).slotDefinitions.length === 1 ? '' : 's'}
                      </span>
                      <div class="mt-1 grid gap-2 sm:grid-cols-2">
                        {#each (design as any).slotDefinitions as slot}
                          <div class="rounded border border-border-subtle bg-surface-0 px-3 py-2 text-2xs">
                            <div class="font-medium text-text-primary">Slot {slot.index}{#if slot.label}: {slot.label}{/if}</div>
                            {#if slot.jlink_app_serial}
                              <div class="text-text-tertiary mt-0.5">J-Link app: <span class="font-mono">{slot.jlink_app_serial}</span></div>
                            {/if}
                            {#if slot.jlink_comms_serial}
                              <div class="text-text-tertiary">J-Link comms: <span class="font-mono">{slot.jlink_comms_serial}</span></div>
                            {/if}
                          </div>
                        {/each}
                      </div>
                    </div>
                  {/if}

                  <!-- Power config -->
                  {#if design.profileTemplate}
                    {@const power = (design.profileTemplate as any)?.power}
                    {#if power}
                      <div class="flex items-center gap-4 text-2xs text-text-tertiary">
                        <Zap size={12} class="text-warning" />
                        <span>DUT {power.dut_voltage}V</span>
                        {#if power.charger_voltage}<span>Charger {power.charger_voltage}V</span>{/if}
                        <span>{power.battery_installed ? 'Battery' : 'No battery'}</span>
                        <span>Boot settle {power.boot_settle_s}s</span>
                      </div>
                    {/if}
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    {/each}
  </div>
{/if}
