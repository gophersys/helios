<script lang="ts">
  import { Box, Plus, Loader2, Wrench } from 'lucide-svelte';
  import { api, apiFetch } from '$lib/api';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import Modal from '$lib/components/ui/modal.svelte';
  import type { Fixture, FixtureDesign } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  interface Props {
    productId: string;
    boardRevisionId?: string;
    canManage: boolean;
    designId?: string;
  }

  let { productId, boardRevisionId, canManage, designId }: Props = $props();

  let fixtures = $state<Fixture[]>([]);
  let designs = $state<FixtureDesign[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Create form
  let showCreate = $state(false);
  let formName = $state('');
  let formDesignId = $state('');
  let submitting = $state(false);
  let createError = $state<string | null>(null);

  async function fetchFixtures(): Promise<void> {
    loading = true;
    error = null;
    try {
      let url = `/v2/fixtures?productId=${productId}&type=MANUFACTURING&limit=50`;
      if (boardRevisionId) {
        url += `&boardRevisionId=${boardRevisionId}`;
      }
      const res = await apiFetch<ApiResponse<{ data: Fixture[] }>>(url);
      const payload = res.data;
      fixtures = Array.isArray(payload) ? payload : (payload as any)?.data || [];
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load fixtures';
    } finally {
      loading = false;
    }
  }

  async function fetchDesigns(): Promise<void> {
    try {
      let url = `/v2/fixtures/designs?type=MANUFACTURING&limit=100`;
      if (boardRevisionId) {
        url += `&boardRevisionId=${boardRevisionId}`;
      }
      const res = await api.get<ApiResponse<{ data: FixtureDesign[] }>>(url);
      designs = (res.data as any).data ?? res.data;
    } catch {
      designs = [];
    }
  }

  function openCreate(): void {
    formName = '';
    formDesignId = designId ?? '';
    createError = null;
    showCreate = true;
  }

  async function handleCreate(): Promise<void> {
    if (!formName.trim()) { createError = 'Name is required'; return; }
    if (!formDesignId) { createError = 'Select a fixture design'; return; }
    submitting = true;
    createError = null;
    try {
      await api.post('/v2/fixtures', {
        name: formName.trim(),
        productId,
        boardRevisionId: boardRevisionId || null,
        designId: formDesignId,
        type: 'MANUFACTURING',
        description: null,
      });
      showCreate = false;
      await fetchFixtures();
    } catch (err) {
      createError = err instanceof Error ? err.message : 'Failed to create fixture';
    } finally {
      submitting = false;
    }
  }

  $effect(() => {
    productId;
    boardRevisionId;
    fetchFixtures();
    fetchDesigns();
  });
</script>

<div>
  <div class="flex items-center justify-between mb-3">
    <h4 class="text-xs font-semibold text-text-secondary flex items-center gap-1.5">
      <Box size={13} class="text-text-tertiary" />
      Fixture Instances
    </h4>
    {#if canManage && designs.length > 0}
      <button onclick={openCreate} class="btn btn-sm btn-secondary text-2xs">
        <Plus size={12} />
        Create Fixture
      </button>
    {/if}
  </div>

  {#if loading}
    <p class="text-2xs text-text-tertiary py-3">Loading...</p>
  {:else if error}
    <ErrorAlert message={error} />
  {:else if designs.length === 0}
    <div class="rounded-lg border border-dashed border-border bg-surface-0 px-4 py-5 text-center">
      <Wrench size={20} class="mx-auto text-text-tertiary mb-2 opacity-40" />
      <p class="text-xs text-text-secondary">Publish a fixture design first.</p>
      <p class="text-2xs text-text-tertiary mt-1">Release a test app to auto-generate fixture designs.</p>
    </div>
  {:else if fixtures.length === 0}
    <div class="rounded-lg border border-dashed border-border bg-surface-0 px-4 py-5 text-center">
      <Box size={20} class="mx-auto text-text-tertiary mb-2 opacity-40" />
      <p class="text-xs text-text-secondary">No fixture instances yet.</p>
      <p class="text-2xs text-text-tertiary mt-1">Create a fixture instance from a published design.</p>
    </div>
  {:else}
    <div class="rounded-lg border border-border bg-surface-0 overflow-hidden">
      <table class="table">
        <thead>
          <tr class="border-b border-border">
            <th class="table-header">Name</th>
            <th class="table-header">Design</th>
            <th class="table-header">Slots</th>
            <th class="table-header">Status</th>
          </tr>
        </thead>
        <tbody>
          {#each fixtures as fixture (fixture.id)}
            <tr class="table-row">
              <td class="table-cell">
                <a
                  href="/fixtures?fixtureId={fixture.id}"
                  class="text-sm font-medium text-accent hover:text-accent-hover transition-colors"
                >
                  {fixture.name}
                </a>
              </td>
              <td class="table-cell text-2xs text-text-secondary">
                {#if fixture.design}
                  {fixture.design.name} v{fixture.design.revision}
                {:else}
                  <span class="text-text-tertiary">-</span>
                {/if}
              </td>
              <td class="table-cell text-2xs text-text-secondary">
                {fixture.slotCount ?? 0}
              </td>
              <td class="table-cell">
                <StatusBadge status={fixture.active ? 'AVAILABLE' : 'INACTIVE'} />
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

{#if showCreate}
  <Modal open={true} title="Create Fixture Instance" onclose={() => showCreate = false} size="sm">
    <div class="space-y-4">
      {#if createError}
        <div class="rounded-lg bg-error-muted px-3 py-2 text-sm text-error">{createError}</div>
      {/if}

      <div class="form-group">
        <label for="fixture-name" class="form-label">Name</label>
        <input
          id="fixture-name"
          type="text"
          bind:value={formName}
          placeholder="e.g. MFG-Fixture-01"
          class="input input-md"
        />
      </div>

      <div class="form-group">
        <label for="fixture-design" class="form-label">Fixture Design</label>
        <select id="fixture-design" bind:value={formDesignId} class="input input-md">
          <option value="">Select a design...</option>
          {#each designs as design}
            <option value={design.id}>{design.name} v{design.revision}</option>
          {/each}
        </select>
      </div>
    </div>

    {#snippet footer()}
      <button onclick={() => showCreate = false} disabled={submitting} class="btn btn-sm btn-ghost">
        Cancel
      </button>
      <button onclick={handleCreate} disabled={submitting} class="btn btn-sm btn-primary">
        {#if submitting}
          <Loader2 size={14} class="animate-spin" />
          Creating...
        {:else}
          <Plus size={14} />
          Create
        {/if}
      </button>
    {/snippet}
  </Modal>
{/if}
