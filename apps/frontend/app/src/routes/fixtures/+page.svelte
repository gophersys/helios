<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Plus, Check, Wrench, Ruler } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import { PageHeader, ErrorAlert, EmptyState, LoadingState, ConfirmDeleteDialog, Select, FormCard, Tabs } from '$lib/components/ui';
  import FixtureCard from '$lib/components/fixtures/fixture-card.svelte';
  import FixtureDetail from '$lib/components/fixtures/fixture-detail.svelte';
  import FixtureDesigns from '$lib/components/fixtures/fixture-designs.svelte';
  import type { Fixture, Product, Board, FixtureDesign } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import type { Tab } from '$lib/components/ui/types';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('fixtures:manage'));

  // Tab state
  const tabs: Tab[] = [
    { id: 'fixtures', label: 'Fixtures', icon: Wrench },
    { id: 'designs', label: 'Designs', icon: Ruler },
  ];
  let activeTab = $state('fixtures');

  let fixtures = $state<Fixture[]>([]);
  let products = $state<Product[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Board revisions for the selected product
  let boards = $state<Board[]>([]);
  // Available designs for the selected board revision
  let availableDesigns = $state<FixtureDesign[]>([]);

  // Form state
  let showForm = $state(false);
  let editingId = $state<string | null>(null);
  let formName = $state('');
  let formProductId = $state('');
  let formBoardRevisionId = $state('');
  let formDesignId = $state('');
  let formType = $state('MANUFACTURING');
  let formDescription = $state('');
  let formSlotCount = $state(1);
  let submitting = $state(false);

  // Delete confirmation
  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  // Detail state
  let selectedFixture = $state<Fixture | null>(null);

  // Board revisions derived from fetched boards
  const boardRevisions = $derived.by(() => {
    const revisions: { id: string; label: string }[] = [];
    for (const board of boards) {
      for (const rev of board.revisions ?? []) {
        revisions.push({
          id: rev.id,
          label: `${board.name} ${rev.version}${rev.ckBoardsName ? ` (${rev.ckBoardsName})` : ''}`
        });
      }
    }
    return revisions;
  });

  // Design options derived from available designs
  const designOptions = $derived(
    availableDesigns.map(d => ({ value: d.id, label: `${d.name} (${d.revision})` }))
  );

  async function fetchFixtures() {
    try {
      const res = await apiFetch<ApiResponse<{ data: Fixture[] }>>('/v2/fixtures');
      const payload = res.data;
      fixtures = Array.isArray(payload) ? payload : (payload as { data: Fixture[] }).data || [];
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load fixtures';
    } finally {
      loading = false;
    }
  }

  async function fetchProducts() {
    try {
      const res = await apiFetch<ApiResponse<{ data: Product[] }>>('/v2/products');
      const payload = res.data;
      products = Array.isArray(payload) ? payload : (payload as { data: Product[] }).data || [];
    } catch {
      // Non-critical
    }
  }

  async function fetchBoardsForProduct(productId: string) {
    if (!productId) {
      boards = [];
      return;
    }
    try {
      const res = await apiFetch<ApiResponse<Product>>(`/v2/products/${productId}`);
      boards = res.data.boards ?? [];
    } catch {
      boards = [];
    }
  }

  async function fetchDesignsForRevision(boardRevisionId: string) {
    if (!boardRevisionId) {
      availableDesigns = [];
      return;
    }
    try {
      const res = await apiFetch<ApiResponse<{ data: FixtureDesign[] }>>(`/v2/fixtures/designs?boardRevisionId=${boardRevisionId}`);
      const payload = res.data;
      availableDesigns = Array.isArray(payload) ? payload : (payload as { data: FixtureDesign[] }).data || [];
    } catch {
      availableDesigns = [];
    }
  }

  // Fetch boards when product changes in the form
  $effect(() => {
    if (formProductId) {
      fetchBoardsForProduct(formProductId);
    } else {
      boards = [];
    }
  });

  // Reset board revision if it's no longer valid after boards change
  $effect(() => {
    if (formBoardRevisionId && boardRevisions.length > 0) {
      const stillValid = boardRevisions.some(r => r.id === formBoardRevisionId);
      if (!stillValid) {
        formBoardRevisionId = '';
        formDesignId = '';
      }
    }
  });

  // Fetch designs when board revision changes
  $effect(() => {
    if (formBoardRevisionId) {
      fetchDesignsForRevision(formBoardRevisionId);
    } else {
      availableDesigns = [];
      formDesignId = '';
    }
  });

  async function fetchDetail(id: string) {
    try {
      const res = await apiFetch<ApiResponse<Fixture>>(`/v2/fixtures/${id}`);
      selectedFixture = res.data;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load fixture';
    }
  }

  onMount(() => {
    if (!auth.hasPermission('fixtures:view')) {
      goto('/');
      return;
    }
    fetchFixtures();
    fetchProducts();
  });

  function resetForm() {
    formName = '';
    formProductId = '';
    formBoardRevisionId = '';
    formDesignId = '';
    formType = 'MANUFACTURING';
    formDescription = '';
    formSlotCount = 1;
    editingId = null;
    showForm = false;
  }

  function startEdit(f: Fixture) {
    formName = f.name;
    formProductId = f.productId;
    formBoardRevisionId = f.boardRevisionId ?? '';
    formDesignId = f.designId ?? '';
    formType = f.type;
    formDescription = f.description || '';
    formSlotCount = f.slotCount ?? f.slots?.length ?? 1;
    editingId = f.id;
    showForm = true;
    selectedFixture = null;
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    error = null;
    submitting = true;

    const body: Record<string, unknown> = {
      name: formName,
      productId: formProductId,
      boardRevisionId: formBoardRevisionId || null,
      designId: formDesignId || null,
      type: formType,
      description: formDescription || null,
    };

    if (!editingId) {
      body.slotCount = formSlotCount;
    }

    try {
      if (editingId) {
        await api.put(`/v2/fixtures/${editingId}`, body);
      } else {
        await api.post('/v2/fixtures', body);
      }
      resetForm();
      fetchFixtures();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to save fixture';
    } finally {
      submitting = false;
    }
  }

  function promptDelete(id: string) {
    const target = fixtures.find((f) => f.id === id);
    deleteTarget = { id, name: target?.name || '' };
  }

  async function handleDelete(id: string) {
    error = null;
    try {
      await api.delete(`/v2/fixtures/${id}`);
      if (selectedFixture?.id === id) selectedFixture = null;
      fetchFixtures();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete fixture';
    }
  }
</script>

<svelte:head>
  <title>Fixtures — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="Fixtures"
      description="Manage test fixtures, slot assignments, and fixture designs."
    >
      {#snippet actions()}
        {#if canManage && !showForm && !selectedFixture && activeTab === 'fixtures'}
          <button
            onclick={() => { resetForm(); showForm = true; }}
            class="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
          >
            <Plus size={16} />
            Create Fixture
          </button>
        {/if}
      {/snippet}
    </PageHeader>
  </div>

  {#if !selectedFixture}
    <div class="mb-6">
      <Tabs {tabs} bind:activeTab size="sm" />
    </div>
  {/if}

  {#if loading && activeTab === 'fixtures'}
    <LoadingState message="Loading fixtures..." />
  {:else if selectedFixture}
    <FixtureDetail
      fixture={selectedFixture}
      {canManage}
      onBack={() => { selectedFixture = null; fetchFixtures(); }}
      onRefresh={() => fetchDetail(selectedFixture!.id)}
    />
  {:else if activeTab === 'fixtures'}
    <ErrorAlert message={error} />

    {#if showForm && canManage}
      <FormCard title={editingId ? 'Edit fixture' : 'New fixture'} onClose={resetForm}>
        <form onsubmit={handleSubmit}>
          <div class="mb-3 grid grid-cols-2 gap-3">
            <label>
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Name</span>
              <input
                type="text"
                required
                bind:value={formName}
                placeholder="e.g. MFG-Fixture-01"
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </label>
            <Select
              bind:value={formProductId}
              label="Product"
              placeholder="Select product..."
              options={products.map(p => ({ value: p.id, label: p.name }))}
              required
            />
            <Select
              bind:value={formBoardRevisionId}
              label="Board Revision"
              placeholder={formProductId ? 'Select board revision...' : 'Select product first'}
              options={boardRevisions.map(r => ({ value: r.id, label: r.label }))}
              disabled={!formProductId}
            />
            <Select
              bind:value={formDesignId}
              label="Fixture Design"
              placeholder={formBoardRevisionId ? 'Select design...' : 'Select board revision first'}
              options={designOptions}
              disabled={!formBoardRevisionId}
            />
            <Select
              bind:value={formType}
              label="Type"
              options={[
                { value: 'MANUFACTURING', label: 'Manufacturing' },
                { value: 'VALIDATION', label: 'Validation' },
              ]}
            />
            <label>
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Description</span>
              <input
                type="text"
                bind:value={formDescription}
                placeholder="Optional description"
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </label>
            {#if !editingId}
              <label>
                <span class="mb-1 block text-2xs font-medium text-text-tertiary">Initial Slots</span>
                <input
                  type="number"
                  min="1"
                  max="32"
                  bind:value={formSlotCount}
                  class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
                />
              </label>
            {/if}
          </div>
          <div class="flex gap-2">
            <button
              type="submit"
              disabled={submitting}
              class="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              <Check size={16} />
              {submitting ? 'Saving...' : editingId ? 'Save changes' : 'Create'}
            </button>
            <button
              type="button"
              onclick={resetForm}
              class="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2"
            >
              Cancel
            </button>
          </div>
        </form>
      </FormCard>
    {/if}

    <!-- Grid -->
    {#if fixtures.length === 0}
      <EmptyState message="No fixtures yet" />
    {:else}
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {#each fixtures as f (f.id)}
          <FixtureCard
            fixture={f}
            {canManage}
            onEdit={startEdit}
            onDelete={promptDelete}
            onSelect={(fixture) => fetchDetail(fixture.id)}
          />
        {/each}
      </div>
    {/if}

    <ConfirmDeleteDialog
      open={!!deleteTarget}
      entityType="fixture"
      entityName={deleteTarget?.name || ''}
      onConfirm={() => { handleDelete(deleteTarget!.id); deleteTarget = null; }}
      onCancel={() => (deleteTarget = null)}
    />
  {:else if activeTab === 'designs'}
    <FixtureDesigns {canManage} />
  {/if}
</div>
