<script lang="ts">
  import { onMount } from 'svelte';
  import { Loader2, Wrench, Zap, CircuitBoard, Trash2, Box } from 'lucide-svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import ConfirmDeleteDialog from '$lib/components/ui/confirm-delete-dialog.svelte';
  import { api, apiFetch } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { Product, FixtureDesign } from '$lib/types/models';

  interface Props {
    product: Product;
    canManage: boolean;
    onRefresh?: () => void;
  }

  let { product, canManage, onRefresh }: Props = $props();

  let designs = $state<FixtureDesign[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let selectedRevId = $state<string | null>(null);

  // Delete state
  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  const revisions = $derived(
    (product.boards || []).flatMap((b) => b.revisions || []).filter((r) => r.status === 'ACTIVE')
  );

  const selectedRevision = $derived(
    revisions.find((r) => r.id === selectedRevId) ?? revisions[0] ?? null
  );

  function designsForRevision(revId: string): FixtureDesign[] {
    return designs.filter((d) => d.boardRevisionId === revId);
  }

  async function loadDesigns() {
    loading = true;
    error = null;
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

  async function handleDeleteDesign(id: string) {
    error = null;
    try {
      await api.delete(`/v2/fixtures/designs/${id}`);
      await loadDesigns();
      onRefresh?.();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to delete fixture design';
    }
  }

  // Re-fetch designs when product data changes (e.g., new revision added)
  $effect(() => {
    if (product?.id) loadDesigns();
  });

  onMount(() => {
    if (revisions.length > 0 && !selectedRevId) selectedRevId = revisions[0].id;
  });
</script>

<ErrorAlert message={error} />

{#if loading}
  <div class="flex items-center gap-2 justify-center py-8 text-sm text-text-tertiary">
    <Loader2 size={16} class="animate-spin" /> Loading...
  </div>
{:else if revisions.length === 0}
  <div class="text-center py-8">
    <CircuitBoard size={32} class="mx-auto text-text-tertiary mb-3 opacity-50" />
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
    {@const revDesigns = designsForRevision(selectedRevision.id)}

    {#if revDesigns.length === 0}
      <div class="text-center py-8">
        <Wrench size={32} class="mx-auto text-text-tertiary mb-3 opacity-50" />
        <p class="text-sm text-text-secondary">No fixture designs for {selectedRevision.version}</p>
        <p class="text-2xs text-text-tertiary mt-1">Fixture designs are auto-extracted when a test package is uploaded via corectl.</p>
      </div>
    {:else}
      <div class="grid gap-3 sm:grid-cols-2">
        {#each revDesigns as design}
          <div class="rounded-lg border border-border bg-surface-1 p-4">
            <div class="flex items-center gap-2 mb-2">
              <Wrench size={14} class="text-accent" />
              <span class="text-sm font-semibold text-text-primary">{design.name}</span>
              <span class="rounded-full bg-surface-2 px-2 py-0.5 text-2xs font-medium text-text-secondary">rev {design.revision}</span>
              {#if canManage}
                <div class="ml-auto">
                  <button
                    onclick={() => deleteTarget = { id: design.id, name: design.name }}
                    class="flex items-center justify-center rounded-lg p-1.5 text-text-tertiary hover:bg-error-muted hover:text-error transition-colors"
                    title="Delete fixture design"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              {/if}
            </div>

            {#if design.capabilities?.length}
              <div class="flex flex-wrap gap-1 mb-2">
                {#each design.capabilities as cap}
                  <span class="rounded-full bg-accent-muted px-2 py-0.5 text-2xs font-medium text-accent">{cap}</span>
                {/each}
              </div>
            {/if}

            <div class="flex items-center gap-3 text-2xs text-text-tertiary">
              {#if (design as any).fixtureCount != null}
                <span class="flex items-center gap-1">
                  <Box size={10} />
                  {(design as any).fixtureCount} instance{(design as any).fixtureCount === 1 ? '' : 's'}
                </span>
              {/if}

              {#if design.profileTemplate && (design.profileTemplate as any)?.power}
                {@const power = (design.profileTemplate as any).power}
                <span class="flex items-center gap-1">
                  <Zap size={10} class="text-warning" />
                  {power.dut_voltage}V · {power.battery_installed ? 'Battery' : 'No battery'}
                </span>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  {/if}
{/if}

<ConfirmDeleteDialog
  open={!!deleteTarget}
  entityType="fixture design"
  entityName={deleteTarget?.name || ''}
  onConfirm={() => { handleDeleteDesign(deleteTarget!.id); deleteTarget = null; }}
  onCancel={() => (deleteTarget = null)}
/>
