<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Plus, Check } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import { PageHeader, ErrorAlert, EmptyState, LoadingState, ConfirmDeleteDialog, Select, FormCard } from '$lib/components/ui';
  import FixtureCard from '$lib/components/fixtures/fixture-card.svelte';
  import FixtureDetail from '$lib/components/fixtures/fixture-detail.svelte';
  import type { Fixture, Product } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('Concord.Admin.Fixtures.Manage'));

  let fixtures = $state<Fixture[]>([]);
  let products = $state<Product[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Form state
  let showForm = $state(false);
  let editingId = $state<string | null>(null);
  let formName = $state('');
  let formProductId = $state('');
  let formType = $state('MANUFACTURING');
  let formDescription = $state('');
  let formSlotCount = $state(1);
  let submitting = $state(false);

  // Delete confirmation
  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  // Detail state
  let selectedFixture = $state<Fixture | null>(null);

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
      const res = await apiFetch<ApiResponse<{ data: Product[] }>>('/v2/catalog');
      const payload = res.data;
      products = Array.isArray(payload) ? payload : (payload as { data: Product[] }).data || [];
    } catch {
      // Non-critical
    }
  }

  async function fetchDetail(id: string) {
    try {
      const res = await apiFetch<ApiResponse<Fixture>>(`/v2/fixtures/${id}`);
      selectedFixture = res.data;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load fixture';
    }
  }

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.Fixtures.View')) {
      goto('/');
      return;
    }
    fetchFixtures();
    fetchProducts();
  });

  function resetForm() {
    formName = '';
    formProductId = '';
    formType = 'MANUFACTURING';
    formDescription = '';
    formSlotCount = 1;
    editingId = null;
    showForm = false;
  }

  function startEdit(f: Fixture) {
    formName = f.name;
    formProductId = f.productId;
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
      description="Manage test fixtures and node slot assignments."
    >
      {#snippet actions()}
        {#if canManage && !showForm && !selectedFixture}
          <button
            onclick={() => { resetForm(); showForm = true; }}
            class="flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover"
          >
            <Plus size={16} />
            Create Fixture
          </button>
        {/if}
      {/snippet}
    </PageHeader>
  </div>

  {#if loading}
    <LoadingState message="Loading fixtures..." />
  {:else if selectedFixture}
    <FixtureDetail
      fixture={selectedFixture}
      {canManage}
      onBack={() => { selectedFixture = null; fetchFixtures(); }}
      onRefresh={() => fetchDetail(selectedFixture!.id)}
    />
  {:else}
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
  {/if}
</div>
