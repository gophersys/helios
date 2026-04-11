<script lang="ts">
  import BackButton from '$lib/components/ui/back-button.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import ProductOverviewTab from './tabs/overview-tab.svelte';
  import ProductHardwareTab from './tabs/hardware-tab.svelte';
  import ProductStagesTab from './tabs/stages-tab.svelte';
  import ProductAssetsTab from './tabs/assets-tab.svelte';
  import ProductManufacturingTab from './tabs/manufacturing-tab.svelte';
  import {
    Pencil, Check, X, ChevronDown,
    LayoutDashboard, CircuitBoard, FlaskConical, Package, Factory,
  } from 'lucide-svelte';
  import type { Product, BoardRevision } from '$lib/types/models';
  import { api } from '$lib/api';

  type Tab = 'overview' | 'hardware' | 'assets' | 'manufacturing' | 'stages';

  interface Props {
    product: Product;
    canManage: boolean;
    onBack: () => void;
    onRefresh: () => void;
  }

  let { product, canManage, onBack, onRefresh }: Props = $props();

  let activeTab = $state<Tab>('overview');
  let error = $state<string | null>(null);

  // ── Global revision selection (persists across tabs) ────
  const allRevisions = $derived(
    (product.boards || []).flatMap((b: any) => (b.revisions || []) as BoardRevision[])
  );
  const activeRevisions = $derived(
    allRevisions.filter((r) => r.status === 'ACTIVE')
  );
  let selectedRevisionId = $state<string | null>(null);

  // Auto-select first active revision if none selected
  $effect(() => {
    if (!selectedRevisionId && activeRevisions.length > 0) {
      selectedRevisionId = activeRevisions[0].id;
    }
  });

  const selectedRevision = $derived(
    allRevisions.find((r) => r.id === selectedRevisionId) ?? activeRevisions[0] ?? null
  );

  // Tabs that use revision context
  const revisionTabs: Set<Tab> = new Set(['stages', 'assets', 'manufacturing']);

  // ── Product info editing ────────────────────────────────
  let editingProduct = $state(false);
  let editName = $state('');
  let editSlug = $state('');
  let editDescription = $state('');
  let editFwRepoSlug = $state('');
  let editMfgFwRepoSlug = $state('');
  let savingProduct = $state(false);

  function startEditProduct(): void {
    editName = product.name;
    editSlug = product.slug || '';
    editDescription = product.description || '';
    editFwRepoSlug = product.fwRepoSlug || '';
    editMfgFwRepoSlug = product.mfgFwRepoSlug || '';
    editingProduct = true;
  }

  function cancelEditProduct(): void {
    editingProduct = false;
    error = null;
  }

  async function saveProduct(): Promise<void> {
    savingProduct = true;
    error = null;
    try {
      await api.put(`/v2/products/${product.id}`, {
        name: editName.trim(),
        slug: editSlug.trim() || null,
        description: editDescription.trim() || null,
        fwRepoSlug: editFwRepoSlug.trim() || null,
        mfgFwRepoSlug: editMfgFwRepoSlug.trim() || null,
      });
      editingProduct = false;
      onRefresh();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to update product';
    } finally {
      savingProduct = false;
    }
  }

  const tabs: { key: Tab; label: string; icon: typeof Package }[] = [
    { key: 'overview', label: 'Overview', icon: LayoutDashboard },
    { key: 'hardware', label: 'Hardware', icon: CircuitBoard },
    { key: 'assets', label: 'Assets', icon: Package },
    { key: 'manufacturing', label: 'Manufacturing', icon: Factory },
    { key: 'stages', label: 'Validation', icon: FlaskConical },
  ];
</script>

<div class="animate-fade-in">
  <BackButton label="Back to products" onclick={onBack} />

  <ErrorAlert message={error} />

  <div class="card card-md">
    <!-- ═══ HEADER ═══ -->
    {#if editingProduct}
      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold text-text-primary">Edit Product</h3>
          <div class="flex items-center gap-2">
            <button onclick={cancelEditProduct} class="btn btn-sm btn-ghost flex items-center gap-1">
              <X size={14} /> Cancel
            </button>
            <button
              onclick={saveProduct}
              disabled={savingProduct || !editName.trim()}
              class="btn btn-sm btn-primary flex items-center gap-1"
            >
              <Check size={14} /> {savingProduct ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="block">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Product Name *</span>
            <input type="text" bind:value={editName} class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-hidden" />
          </label>
          <label class="block">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Slug</span>
            <input type="text" bind:value={editSlug} placeholder="URL-safe identifier" class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden" />
          </label>
        </div>
        <label class="block">
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Description</span>
          <input type="text" bind:value={editDescription} placeholder="Optional description" class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden" />
        </label>
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="block">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Firmware Repo Slug</span>
            <input type="text" bind:value={editFwRepoSlug} placeholder="e.g. alpha_fw" class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden" />
          </label>
          <label class="block">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Mfg Firmware Repo Slug</span>
            <input type="text" bind:value={editMfgFwRepoSlug} placeholder="e.g. alpha_mfg_fw" class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden" />
          </label>
        </div>
      </div>
    {:else}
      <div class="flex items-start gap-4">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-3">
            <h2 class="text-xl font-semibold text-text-primary">{product.name}</h2>
            <StatusBadge status={product.active ? 'ACTIVE' : 'INACTIVE'} />
            {#if canManage}
              <button onclick={startEditProduct} title="Edit product" aria-label="Edit product" class="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary">
                <Pencil size={14} />
              </button>
            {/if}
          </div>
          {#if product.description}
            <p class="mt-1 text-sm text-text-secondary">{product.description}</p>
          {/if}
        </div>
      </div>
    {/if}

    <!-- ═══ TABS + REVISION PICKER ═══ -->
    <div class="mt-6 flex items-end justify-between border-b border-border">
      <div class="flex gap-1">
        {#each tabs as tab}
          {@const TabIcon = tab.icon}
          <button
            onclick={() => (activeTab = tab.key)}
            class="flex items-center gap-1.5 px-4 py-2 text-sm font-medium transition-colors {activeTab === tab.key ? 'border-b-2 border-accent text-accent' : 'text-text-tertiary hover:text-text-secondary'}"
          >
            <TabIcon size={14} />
            {tab.label}
          </button>
        {/each}
      </div>

      <!-- Revision picker (shown when on a revision-scoped tab) -->
      {#if revisionTabs.has(activeTab) && activeRevisions.length > 1}
        <div class="flex items-center gap-1 pb-1.5">
          <span class="text-2xs font-medium text-text-tertiary mr-1">Rev:</span>
          {#each activeRevisions as rev}
            <button
              onclick={() => selectedRevisionId = rev.id}
              class="rounded-md px-2 py-1 text-xs font-mono font-medium transition-colors
                {selectedRevisionId === rev.id
                  ? 'bg-accent text-white'
                  : 'text-text-tertiary hover:bg-surface-2 hover:text-text-secondary'}"
            >
              {rev.version}
            </button>
          {/each}
        </div>
      {/if}
    </div>

    <!-- ═══ TAB CONTENT ═══ -->
    <div class="mt-6">
      {#if activeTab === 'overview'}
        <ProductOverviewTab {product} {canManage} onSwitchTab={(tab) => (activeTab = tab as Tab)} />
      {:else if activeTab === 'hardware'}
        <ProductHardwareTab {product} {canManage} {onRefresh} />
      {:else if activeTab === 'stages'}
        <ProductStagesTab {product} {canManage} {onRefresh} selectedRevisionId={selectedRevisionId} />
      {:else if activeTab === 'assets'}
        <ProductAssetsTab {product} {canManage} {onRefresh} selectedRevisionId={selectedRevisionId} />
      {:else if activeTab === 'manufacturing'}
        <ProductManufacturingTab {product} {canManage} {onRefresh} selectedRevisionId={selectedRevisionId} />
      {/if}
    </div>
  </div>
</div>
